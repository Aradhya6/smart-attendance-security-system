"""
Dashboard API — Phase 16.

GET /dashboard/summary — real KPIs from DB (no hardcoded numbers).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.deps import get_db, require_role
from backend.app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(
    current_user: User = Depends(require_role("ADMIN", "OPERATOR")),
    db: Session = Depends(get_db),
) -> dict:
    """
    Real-time KPIs. All values come from the database.
    Attendance % = distinct students present today / active students with registered faces.
    """
    from backend.app.core.config import get_settings
    import pytz
    from datetime import datetime

    settings = get_settings()
    tz = pytz.timezone(settings.app_timezone)
    today = datetime.now(tz).date()

    row = db.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM students WHERE is_active = true) AS total_students,
                (SELECT COUNT(DISTINCT student_id) FROM attendance_records
                 WHERE attendance_date = :today) AS present_today,
                (SELECT COUNT(*) FROM students s
                 WHERE s.is_active = true
                   AND EXISTS (SELECT 1 FROM face_embeddings fe
                               WHERE fe.student_id = s.id AND fe.is_active = true)
                ) AS students_with_faces,
                (SELECT COUNT(*) FROM detection_events
                 WHERE occurred_at::date = :today AND event_type = 'UNKNOWN') AS unknown_today,
                (SELECT COUNT(*) FROM cameras WHERE enabled = true) AS active_cameras,
                (SELECT COUNT(*) FROM security_alerts WHERE resolved_at IS NULL) AS active_alerts,
                (SELECT COUNT(*) FROM detection_events
                 WHERE occurred_at::date = :today AND event_type = 'BLACKLISTED') AS blacklisted_today
        """),
        {"today": today},
    ).fetchone()

    total = row.total_students or 0
    present = row.present_today or 0
    with_faces = row.students_with_faces or 0
    attendance_pct = round((present / with_faces * 100), 1) if with_faces > 0 else 0.0

    return {
        "total_students": total,
        "present_today": present,
        "attendance_percent": attendance_pct,
        "students_with_faces": with_faces,
        "unknown_today": row.unknown_today or 0,
        "active_cameras": row.active_cameras or 0,
        "active_alerts": row.active_alerts or 0,
        "blacklisted_today": row.blacklisted_today or 0,
        "date": str(today),
    }
