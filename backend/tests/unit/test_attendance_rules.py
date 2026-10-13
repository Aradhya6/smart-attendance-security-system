"""
Tests for Phase 15: Attendance rules (pure business logic, no DB needed).
Tests for Phase 17: Unknown person detection.

Mock strategy: patch the SessionLocal class that's imported INSIDE the service
methods using the right module path.
"""
import time
import uuid
from unittest.mock import MagicMock, patch, call
import pytest


def _mock_db_ctx(execute_side_effect=None, commit_side_effect=None, get_return=None):
    """Build a context-manager-compatible mock DB session."""
    ctx = MagicMock()
    execute_mock = MagicMock()
    if execute_side_effect:
        execute_mock.side_effect = execute_side_effect
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.get = MagicMock(return_value=get_return or MagicMock(is_active=True, student_id="001"))
    ctx.execute = MagicMock(return_value=execute_mock)
    if commit_side_effect:
        ctx.commit = MagicMock(side_effect=commit_side_effect)
    else:
        ctx.commit = MagicMock()
    ctx.rollback = MagicMock()
    return ctx


def _student_face(recognized=True, kind="STUDENT", student_uuid=None, sim=0.85):
    from backend.app.vision.recognizer import FaceResult
    return FaceResult(
        recognized=recognized, kind=kind, student_id="001", name="Alice",
        similarity=sim, bbox=[10, 10, 110, 110], det_score=0.9,
        _student_uuid=student_uuid or uuid.uuid4(),
    )


def _unknown_face():
    from backend.app.vision.recognizer import FaceResult
    return FaceResult(
        recognized=False, kind="UNKNOWN", student_id=None, name=None,
        similarity=0.3, bbox=[10, 10, 110, 110], det_score=0.9,
    )


# ---------------------------------------------------------------------------
# Attendance rules
# ---------------------------------------------------------------------------

class TestAttendanceRules:
    def test_unknown_face_never_triggers_db_write(self):
        """UNKNOWN face must not create attendance record."""
        from backend.app.services.attendance_service import AttendanceService
        svc = AttendanceService()
        cam_id = uuid.uuid4()
        face = _unknown_face()
        calls = []
        db = _mock_db_ctx(commit_side_effect=lambda: calls.append(1))
        # Patch at the point-of-use inside the method
        with patch("backend.app.db.session.SessionLocal", return_value=db):
            svc.handle_confirmed("T0", face, cam_id)
        assert len(calls) == 0, "UNKNOWN face must not write to DB"

    def test_unrecognized_face_skipped(self):
        """recognized=False face skipped before any DB access."""
        from backend.app.services.attendance_service import AttendanceService
        svc = AttendanceService()
        face = _student_face(recognized=False, kind="STUDENT")
        calls = []
        db = _mock_db_ctx(commit_side_effect=lambda: calls.append(1))
        with patch("backend.app.db.session.SessionLocal", return_value=db):
            svc.handle_confirmed("T0", face, uuid.uuid4())
        assert len(calls) == 0

    def test_cooldown_prevents_second_mark(self):
        """Same student within cooldown → second call does not reach DB."""
        from backend.app.services.attendance_service import AttendanceService
        svc = AttendanceService()
        svc._cooldown = 300
        cam_id = uuid.uuid4()
        student_uuid = uuid.uuid4()
        face = _student_face(student_uuid=student_uuid)
        db_commits = []

        def make_db():
            db = _mock_db_ctx(commit_side_effect=lambda: db_commits.append(1))
            return db

        with patch("backend.app.db.session.SessionLocal", side_effect=make_db):
            svc.handle_confirmed("T0", face, cam_id)
            svc.handle_confirmed("T0", face, cam_id)  # blocked by cooldown

        assert len(db_commits) <= 1, f"Expected ≤1 DB commit, got {len(db_commits)}"

    def test_different_students_each_reach_db(self):
        """Two different students both get their own DB write."""
        from backend.app.services.attendance_service import AttendanceService
        svc = AttendanceService()
        cam_id = uuid.uuid4()
        s1, s2 = uuid.uuid4(), uuid.uuid4()
        db_commits = []

        def make_db():
            return _mock_db_ctx(commit_side_effect=lambda: db_commits.append(1))

        with patch("backend.app.db.session.SessionLocal", side_effect=make_db):
            svc.handle_confirmed("T0", _student_face(student_uuid=s1), cam_id)
            svc.handle_confirmed("T1", _student_face(student_uuid=s2), cam_id)

        assert len(db_commits) >= 2

    def test_no_crash_on_db_failure(self):
        """DB failure must not crash the worker."""
        from backend.app.services.attendance_service import AttendanceService
        svc = AttendanceService()

        def make_db():
            return _mock_db_ctx(execute_side_effect=Exception("DB down"))

        with patch("backend.app.db.session.SessionLocal", side_effect=make_db):
            svc.handle_confirmed("T0", _student_face(), uuid.uuid4())


# ---------------------------------------------------------------------------
# Unknown dedup (Phase 17)
# ---------------------------------------------------------------------------

class TestUnknownDedup:
    def test_unknown_events_throttled_by_cooldown(self):
        """Same unknown track ID within cooldown → only 1 DB commit."""
        from backend.app.services.detection_service import DetectionService
        svc = DetectionService()
        svc._unknown_cooldown = 60
        cam_id = uuid.uuid4()
        db_commits = []

        def make_db():
            return _mock_db_ctx(commit_side_effect=lambda: db_commits.append(1))

        with patch("backend.app.db.session.SessionLocal", side_effect=make_db):
            svc.handle_observation("T_UNKNOWN", _unknown_face(), cam_id)
            svc.handle_observation("T_UNKNOWN", _unknown_face(), cam_id)
            svc.handle_observation("T_UNKNOWN", _unknown_face(), cam_id)

        assert len(db_commits) == 1, f"Expected 1 DB commit, got {len(db_commits)}"

    def test_new_unknown_track_creates_new_event(self):
        """Different track IDs create separate events."""
        from backend.app.services.detection_service import DetectionService
        svc = DetectionService()
        svc._unknown_cooldown = 60
        cam_id = uuid.uuid4()
        db_commits = []

        def make_db():
            return _mock_db_ctx(commit_side_effect=lambda: db_commits.append(1))

        with patch("backend.app.db.session.SessionLocal", side_effect=make_db):
            svc.handle_observation("T_A", _unknown_face(), cam_id)
            svc.handle_observation("T_B", _unknown_face(), cam_id)

        assert len(db_commits) == 2

    def test_unknown_never_creates_attendance(self):
        """UNKNOWN face handled by attendance service → no DB write."""
        from backend.app.services.attendance_service import AttendanceService
        svc = AttendanceService()
        db_commits = []

        def make_db():
            return _mock_db_ctx(commit_side_effect=lambda: db_commits.append(1))

        with patch("backend.app.db.session.SessionLocal", side_effect=make_db):
            svc.handle_confirmed("T0", _unknown_face(), uuid.uuid4())

        assert len(db_commits) == 0

    def test_detection_service_no_crash_on_db_failure(self):
        """DB failure in detection service must not crash."""
        from backend.app.services.detection_service import DetectionService
        svc = DetectionService()

        def make_db():
            return _mock_db_ctx(execute_side_effect=Exception("DB error"))

        with patch("backend.app.db.session.SessionLocal", side_effect=make_db):
            svc.handle_observation("T0", _unknown_face(), uuid.uuid4())  # must not raise
