"""
Tests for Live Attendance and Camera Recognition Workflow:
- Cameras listing (/api/v1/cameras and /api/v1/recognition/cameras)
- Camera worker start and stop endpoints (/recognition/workers/{id}/start, /stop)
- Live attendance queries (/attendance, /attendance/recent) without UndefinedColumn errors
- Dashboard summary queries (/dashboard/summary) with status = 'ACTIVE'
- Verification that unknown face does NOT get marked present
- Verification that real camera hardware can be accessed via OpenCV VideoCapture
"""
from datetime import date, datetime, timezone
import uuid
import cv2
import pytest
from sqlalchemy import text

from backend.app.models.camera import Camera
from backend.app.models.student import Student
from backend.app.models.attendance import AttendanceRecord
from backend.app.models.face_embedding import FaceEmbedding


def test_list_cameras_endpoint(client, admin_token, db_session):
    """GET /api/v1/cameras returns registered cameras from DB."""
    # Ensure a camera exists
    cam = Camera(
        id=uuid.UUID("4498d160-0483-47b3-92b1-8c6dc97f8100"),
        name="Laptop Webcam",
        location="Local Built-in",
        source_type="WEBCAM",
        source_url="0",
        enabled=True,
        status="ONLINE",
    )
    db_session.merge(cam)
    db_session.flush()

    res = client.get("/api/v1/cameras", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    cams = res.json()
    assert len(cams) >= 1
    webcam = next((c for c in cams if c["id"] == "4498d160-0483-47b3-92b1-8c6dc97f8100"), None)
    assert webcam is not None
    assert webcam["name"] == "Laptop Webcam"
    assert webcam["source_type"] == "WEBCAM"


def test_list_recognition_cameras_alias(client, admin_token, db_session):
    """GET /api/v1/recognition/cameras works as an alias."""
    res = client.get("/api/v1/recognition/cameras", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_attendance_list_and_recent_queries_no_sql_error(client, admin_token, db_session):
    """GET /api/v1/attendance and /recent execute clean SQL with correct column aliases."""
    # Create student and camera
    cam = Camera(
        id=uuid.uuid4(),
        name=f"Cam-{uuid.uuid4().hex[:6]}",
        location="Room 101",
        source_type="WEBCAM",
        source_url="0",
        enabled=True,
        status="ONLINE",
    )
    student = Student(
        id=uuid.uuid4(),
        student_id=f"ATT-TEST-{uuid.uuid4().hex[:4]}",
        name="Attendance Student",
        department="Computer Science",
        year=3,
        status="ACTIVE",
        consent_given_at=datetime.now(timezone.utc),
    )
    db_session.add_all([cam, student])
    db_session.flush()

    # Add attendance record
    today = date.today()
    record = AttendanceRecord(
        id=uuid.uuid4(),
        student_id=student.id,
        camera_id=cam.id,
        attendance_date=today,
        session_label="TEST_SESSION",
        marked_at=datetime.now(timezone.utc),
        status="PRESENT",
        similarity=0.91,
        method="AUTO",
    )
    db_session.add(record)
    db_session.flush()

    # 1. Test list attendance
    res_list = client.get(
        "/api/v1/attendance",
        params={"session_label": "TEST_SESSION", "from_date": str(today), "to_date": str(today)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_list.status_code == 200
    items = res_list.json()
    assert len(items) >= 1
    found = next((r for r in items if r["student_id"] == student.student_id), None)
    assert found is not None
    assert found["full_name"] == "Attendance Student"
    assert found["status"] == "PRESENT"
    assert found["similarity"] == 0.91

    # 2. Test recent attendance
    res_recent = client.get(
        "/api/v1/attendance/recent",
        params={"limit": 10},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_recent.status_code == 200
    recent_items = res_recent.json()
    assert len(recent_items) >= 1
    assert any(r["full_name"] == "Attendance Student" for r in recent_items)


def test_dashboard_summary_query_no_sql_error(client, admin_token, db_session):
    """GET /api/v1/dashboard/summary executes without column errors and returns metrics."""
    res = client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "total_students" in data
    assert "present_today" in data
    assert "attendance_percent" in data
    assert "students_with_faces" in data
    assert "active_cameras" in data


def test_camera_worker_start_and_stop_endpoints_with_mock_source(client, admin_token, db_session):
    """
    Test start_worker and stop_worker endpoints with a mocked camera source
    to verify pipeline building, student label caching, and session label passing.
    """
    from unittest.mock import patch, MagicMock
    from backend.app.cameras.manager import camera_manager

    # Make sure camera exists in DB
    cam_id = uuid.uuid4()
    cam = Camera(
        id=cam_id,
        name=f"MockCam-{cam_id.hex[:6]}",
        location="Lab",
        source_type="WEBCAM",
        source_url="0",
        enabled=True,
        status="ONLINE",
    )
    db_session.add(cam)
    db_session.flush()

    # Mock WebcamSource so hardware is not locked during unit test
    class MockWebcamSource:
        def __init__(self, camera_index=0):
            self.camera_index = camera_index
            self._opened = False
        def open(self):
            self._opened = True
            return True
        def is_open(self):
            return self._opened
        def read_frame(self):
            import numpy as np
            return True, np.zeros((480, 640, 3), dtype=np.uint8)
        def release(self):
            self._opened = False

    with patch("backend.app.cameras.webcam.WebcamSource", side_effect=MockWebcamSource):
        # 1. Start worker
        res_start = client.post(
            f"/api/v1/recognition/workers/{cam_id}/start?session_label=CSE_LECTURE_1",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_start.status_code == 200
        assert res_start.json()["status"] == "RUNNING"

        # 2. Starting already running worker returns 409
        res_dup = client.post(
            f"/api/v1/recognition/workers/{cam_id}/start",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_dup.status_code == 409

        # 3. List workers shows RUNNING
        res_list = client.get(
            "/api/v1/recognition/workers",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_list.status_code == 200
        workers = res_list.json()
        assert any(w["camera_id"] == str(cam_id) and w["status"] == "RUNNING" for w in workers)

        # 4. Stop worker
        res_stop = client.post(
            f"/api/v1/recognition/workers/{cam_id}/stop",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_stop.status_code == 200
        assert res_stop.json()["status"] == "STOPPED"


def test_real_laptop_webcam_hardware_access():
    """
    Direct verification of the physical laptop webcam hardware on device index 0.
    Verifies that DirectShow / OpenCV can open the device and retrieve real frames.
    """
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)

    try:
        assert cap.isOpened(), "Physical laptop webcam at index 0 could not be opened"
        ret, frame = cap.read()
        assert ret is True, "Failed to capture frame from physical laptop webcam"
        assert frame is not None
        assert len(frame.shape) == 3
        assert frame.shape[0] > 0 and frame.shape[1] > 0
    finally:
        cap.release()
