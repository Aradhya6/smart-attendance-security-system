import os
import pytest
import numpy as np
import cv2
from fastapi.testclient import TestClient

# Configure test database before loading application modules
os.environ["DATABASE_URL"] = "sqlite:///./test_security.db"

from backend.app.db.session import (
    init_db,
    get_registered_persons,
    get_blacklist,
    add_blacklist_entry,
    deactivate_blacklist_entry,
    log_detection_event,
    upsert_security_alert,
    get_alerts,
    acknowledge_alert,
    resolve_alert,
    get_security_summary,
    get_db
)
from backend.app.vision.detector import FaceDetector
from backend.app.vision.recognizer import FaceRecognizer, cosine_similarity
from backend.app.vision.tracker import SimpleTracker
from backend.app.vision.pipeline import vision_pipeline
from backend.app.services.security_service import security_service
from backend.app.main import app

@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM security_alerts")
        cursor.execute("DELETE FROM detection_events")
        cursor.execute("DELETE FROM blacklist_entries WHERE id LIKE 'test-%'")

def test_cosine_similarity():
    v1 = np.array([1.0, 0.0, 0.0])
    v2 = np.array([1.0, 0.0, 0.0])
    assert abs(cosine_similarity(v1, v2) - 1.0) < 1e-5

    v3 = np.array([0.0, 1.0, 0.0])
    assert abs(cosine_similarity(v1, v3) - 0.0) < 1e-5

def test_unknown_person_classification():
    recognizer = FaceRecognizer(threshold=0.50)
    # Synthetic random face chip
    dummy_chip = np.zeros((112, 112, 3), dtype=np.uint8)
    res = recognizer.identify(dummy_chip)
    assert res["kind"] == "UNKNOWN"
    assert res["is_suspicious"] is True
    assert res["person_name"] == "Unknown Person"

def test_blacklist_classification():
    recognizer = FaceRecognizer(threshold=0.50)
    chip = np.full((112, 112, 3), 128, dtype=np.uint8)
    emb = recognizer.extract_embedding(chip)

    # Add to blacklist
    add_blacklist_entry(
        full_name="Threat Person Alpha",
        reason="Trespassing incident",
        severity="CRITICAL",
        embedding=emb
    )

    res = recognizer.identify(chip)
    assert res["kind"] == "BLACKLISTED"
    assert res["person_name"] == "Threat Person Alpha"
    assert res["is_suspicious"] is True

def test_blacklist_lifecycle():
    entry = add_blacklist_entry(
        full_name="Subject X",
        reason="Repeated violations",
        severity="CRITICAL"
    )
    assert entry["status"] == "ACTIVE"
    assert entry["full_name"] == "Subject X"

    # Deactivate
    success = deactivate_blacklist_entry(entry["id"])
    assert success is True

    items = get_blacklist(status="ACTIVE")
    active_ids = [item["id"] for item in items]
    assert entry["id"] not in active_ids

def test_security_alert_deduplication_and_lifecycle():
    # 1. Create alert
    alert1 = upsert_security_alert(
        alert_type="UNKNOWN_PERSON",
        severity="MEDIUM",
        camera_id="cam-01",
        camera_location="Gate 1",
        person_name="Unknown Person",
        dedup_key="UNKNOWN_PERSON:cam-01:Unknown Person"
    )
    assert alert1["status"] == "NEW"
    assert alert1["occurrence_count"] == 1

    # 2. Duplicate detection within window -> updates count
    alert2 = upsert_security_alert(
        alert_type="UNKNOWN_PERSON",
        severity="MEDIUM",
        camera_id="cam-01",
        camera_location="Gate 1",
        person_name="Unknown Person",
        dedup_key="UNKNOWN_PERSON:cam-01:Unknown Person"
    )
    assert alert2["id"] == alert1["id"]
    assert alert2["occurrence_count"] == 2

    # 3. Acknowledge
    ack = acknowledge_alert(alert1["id"])
    assert ack["status"] == "ACKNOWLEDGED"

    # 4. Resolve
    resolved = resolve_alert(alert1["id"], "Verified visitor by staff")
    assert resolved["status"] == "RESOLVED"
    assert resolved["resolution_note"] == "Verified visitor by staff"

def test_person_movement_tracking():
    # Log sightings across cameras
    log_detection_event("cam-01", "Campus Gate", "STUDENT", "Rahul Sharma", 0.95)
    log_detection_event("cam-02", "Library Hall", "STUDENT", "Rahul Sharma", 0.92)

    history = security_service.get_person_tracking_history("Rahul Sharma")
    assert len(history) >= 2
    cams = [h["camera_id"] for h in history]
    assert "cam-01" in cams
    assert "cam-02" in cams

def test_vision_pipeline_processing():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    annotated, alerts = vision_pipeline.process_frame(frame, camera_id="cam-01")
    assert annotated.shape == (480, 640, 3)
    assert isinstance(alerts, list)

def test_api_endpoints():
    client = TestClient(app)

    # Health
    r_health = client.get("/api/v1/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"

    # Summary
    r_sum = client.get("/api/v1/security/summary")
    assert r_sum.status_code == 200
    assert "active_alerts" in r_sum.json()

    # Create Blacklist via API
    r_bl = client.post("/api/v1/blacklist", json={
        "full_name": "API Test Threat",
        "reason": "Test incident",
        "severity": "CRITICAL"
    })
    assert r_bl.status_code == 200
    bl_id = r_bl.json()["id"]

    # Deactivate Blacklist via API
    r_deact = client.post(f"/api/v1/blacklist/{bl_id}/deactivate")
    assert r_deact.status_code == 200
    assert r_deact.json()["status"] == "deactivated"

    # Seed Demo Data API
    r_seed = client.post("/api/v1/security/seed-demo")
    assert r_seed.status_code == 200
    assert r_seed.json()["status"] == "success"
