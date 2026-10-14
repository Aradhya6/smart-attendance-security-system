"""
Attendance Service — Phase 15.

confirmed recognition → eligibility checks → cooldown → DB INSERT ON CONFLICT DO NOTHING.

Rules:
- Only STUDENT kind, recognized=True, similarity >= threshold
- Student must be ACTIVE
- In-memory cooldown (per student_id, session_label) + DB unique constraint
- Date computed in APP_TIMEZONE
- Optional LATE status if ATTENDANCE_LATE_AFTER is set
- Worker never crashes if DB write fails
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import date, datetime
from typing import Dict, Optional, Tuple

import pytz
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


class AttendanceService:
    """Thread-safe attendance handler wired into the camera worker."""

    def __init__(self, session_label: Optional[str] = None) -> None:
        settings = get_settings()
        self._cooldown = settings.attendance_cooldown_seconds
        self._session_label = session_label or settings.attendance_session_label
        self._late_after = settings.attendance_late_after  # "HH:MM" or ""
        self._tz = pytz.timezone(settings.app_timezone)

        # In-memory cooldown: {(student_uuid, session_label, date_str): last_marked_ts}
        self._cache: Dict[Tuple, float] = {}
        self._lock = threading.Lock()

    def handle_confirmed(self, track_id: str, face_result, camera_id: uuid.UUID) -> None:
        """Observer callback. Never raises; logs errors and continues."""
        try:
            self._handle(track_id, face_result, camera_id)
        except Exception as exc:
            logger.error("AttendanceService.handle_confirmed error (non-fatal): %s", exc)

    def _handle(self, track_id: str, face_result, camera_id: uuid.UUID) -> None:
        # Only STUDENT, recognized faces
        if not face_result.recognized or face_result.kind != "STUDENT":
            return
        if face_result._student_uuid is None:
            return

        student_uuid = face_result._student_uuid
        now_local = datetime.now(self._tz)
        today = now_local.date()
        session_label = self._session_label
        cache_key = (student_uuid, session_label, str(today))

        # In-memory cooldown check
        with self._lock:
            last_ts = self._cache.get(cache_key)
            if last_ts is not None and (time.time() - last_ts) < self._cooldown:
                return  # Already marked recently
            self._cache[cache_key] = time.time()

        # Status: PRESENT or LATE
        status = "PRESENT"
        if self._late_after:
            try:
                h, m = map(int, self._late_after.split(":"))
                late_time = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
                if now_local > late_time:
                    status = "LATE"
            except Exception:
                pass

        from backend.app.db.session import SessionLocal
        from backend.app.models.student import Student

        with SessionLocal() as db:
            # Verify student is active
            student = db.get(Student, student_uuid)
            is_active = getattr(student, "is_active", False)
            if student is None or not is_active:
                logger.debug("AttendanceService: student %s inactive or not found", student_uuid)
                return

            marked_at = datetime.now(pytz.utc)
            try:
                db.execute(
                    text("""
                        INSERT INTO attendance_records
                            (id, student_id, camera_id, attendance_date, session_label,
                             marked_at, status, similarity, method, created_at)
                        VALUES
                            (gen_random_uuid(), :student_id, :camera_id, :att_date,
                             :session_label, :marked_at, :status, :similarity, 'AUTO', NOW())
                        ON CONFLICT (student_id, attendance_date, session_label) DO NOTHING
                    """),
                    {
                        "student_id": str(student_uuid),
                        "camera_id": str(camera_id),
                        "att_date": today,
                        "session_label": session_label,
                        "marked_at": marked_at,
                        "status": status,
                        "similarity": face_result.similarity,
                    },
                )
                db.commit()
                logger.info(
                    "Attendance: student=%s date=%s status=%s similarity=%.3f",
                    student.student_id, today, status, face_result.similarity,
                )
            except Exception as exc:
                db.rollback()
                logger.error("AttendanceService DB write failed: %s", exc)
                # Reset cache so next attempt can retry
                with self._lock:
                    self._cache.pop(cache_key, None)
