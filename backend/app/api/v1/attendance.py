"""
Attendance API — Phase 15 + 16.

GET  /attendance          — paginated list with filters
GET  /attendance/recent   — last N records (for live panel)
POST /attendance/manual   — ADMIN manual mark with reason (audited)
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.deps import get_db, require_role
from backend.app.models.user import User
from backend.app.schemas.attendance import (
    AttendanceRecordSchema,
    ManualAttendanceRequest,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("", response_model=List[AttendanceRecordSchema])
def list_attendance(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    student_id: Optional[str] = Query(None, description="Business student_id string"),
    department: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    camera_id: Optional[uuid.UUID] = Query(None),
    session_label: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR")),
    db: Session = Depends(get_db),
) -> List[AttendanceRecordSchema]:
    """Paginated attendance records with optional filters."""
    if from_date and to_date:
        delta = (to_date - from_date).days
        if delta > 366:
            raise HTTPException(status_code=400, detail="Date range must not exceed 366 days")

    conditions = ["1=1"]
    params: dict = {}

    if from_date:
        conditions.append("ar.attendance_date >= :from_date")
        params["from_date"] = from_date
    if to_date:
        conditions.append("ar.attendance_date <= :to_date")
        params["to_date"] = to_date
    if student_id:
        conditions.append("s.student_id = :student_id")
        params["student_id"] = student_id
    if department:
        conditions.append("s.department = :department")
        params["department"] = department
    if year:
        conditions.append("s.year = :year")
        params["year"] = year
    if camera_id:
        conditions.append("ar.camera_id = :camera_id")
        params["camera_id"] = str(camera_id)
    if session_label:
        conditions.append("ar.session_label = :session_label")
        params["session_label"] = session_label

    offset = (page - 1) * size
    params["limit"] = size
    params["offset"] = offset

    where = " AND ".join(conditions)
    rows = db.execute(
        text(f"""
            SELECT ar.id, ar.student_id, s.student_id as sid, s.name as full_name,
                   ar.attendance_date, ar.session_label, ar.marked_at,
                   ar.status, ar.similarity, ar.method, ar.camera_id
            FROM attendance_records ar
            JOIN students s ON s.id = ar.student_id
            WHERE {where}
            ORDER BY ar.marked_at DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).fetchall()

    return [
        AttendanceRecordSchema(
            id=str(r.id),
            student_uuid=str(r.student_id),
            student_id=r.sid,
            full_name=r.full_name,
            attendance_date=r.attendance_date,
            session_label=r.session_label,
            marked_at=r.marked_at,
            status=r.status,
            similarity=float(r.similarity),
            method=r.method,
            camera_id=str(r.camera_id),
        )
        for r in rows
    ]


@router.get("/recent", response_model=List[AttendanceRecordSchema])
def recent_attendance(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR")),
    db: Session = Depends(get_db),
):
    """Most recent attendance marks (for live panel)."""
    rows = db.execute(
        text("""
            SELECT ar.id, ar.student_id, s.student_id as sid, s.name as full_name,
                   ar.attendance_date, ar.session_label, ar.marked_at,
                   ar.status, ar.similarity, ar.method, ar.camera_id
            FROM attendance_records ar
            JOIN students s ON s.id = ar.student_id
            ORDER BY ar.marked_at DESC
            LIMIT :limit
        """),
        {"limit": limit},
    ).fetchall()

    return [
        AttendanceRecordSchema(
            id=str(r.id),
            student_uuid=str(r.student_id),
            student_id=r.sid,
            full_name=r.full_name,
            attendance_date=r.attendance_date,
            session_label=r.session_label,
            marked_at=r.marked_at,
            status=r.status,
            similarity=float(r.similarity),
            method=r.method,
            camera_id=str(r.camera_id),
        )
        for r in rows
    ]


@router.post("/manual", status_code=status.HTTP_201_CREATED)
def manual_attendance(
    request: Request,
    payload: ManualAttendanceRequest,
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
) -> dict:
    """Manually mark attendance. Requires reason. Writes audit log."""
    from backend.app.models.student import Student
    from backend.app.services.audit_service import create_audit_log
    import pytz
    from backend.app.core.config import get_settings

    settings = get_settings()
    tz = pytz.timezone(settings.app_timezone)

    student = db.query(Student).filter(Student.student_id == payload.student_id).first()
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    today = datetime.now(tz).date()
    att_date = payload.attendance_date or today

    try:
        result = db.execute(
            text("""
                INSERT INTO attendance_records
                    (id, student_id, camera_id, attendance_date, session_label,
                     marked_at, status, similarity, method, created_at)
                VALUES
                    (gen_random_uuid(), :student_id,
                     (SELECT id FROM cameras LIMIT 1),
                     :att_date, :session_label, NOW(), :status, 1.0, 'MANUAL', NOW())
                ON CONFLICT (student_id, attendance_date, session_label) DO NOTHING
                RETURNING id
            """),
            {
                "student_id": str(student.id),
                "att_date": att_date,
                "session_label": payload.session_label or settings.attendance_session_label,
                "status": "PRESENT",
            },
        )
        returned = result.fetchone()
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    client_ip = request.client.host if request.client else "unknown"
    create_audit_log(
        db=db,
        action="MANUAL_ATTENDANCE",
        entity_type="STUDENT",
        actor_user_id=current_user.id,
        entity_id=payload.student_id,
        ip=client_ip,
        details={"reason": payload.reason, "date": str(att_date)},
    )

    return {
        "marked": returned is not None,
        "already_marked": returned is None,
        "attendance_date": str(att_date),
    }
