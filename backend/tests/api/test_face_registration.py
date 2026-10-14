"""
Comprehensive test suite for Face Registration:
1. RegistrationSession frame retrieval (fixing get_frames bug)
2. Webcam registration commit workflow
3. Photo-upload face registration workflow
   - Valid photo with single face
   - Missing consent enforcement
   - Inactive student check
   - Non-existent student check
   - Missing file check
   - Unsupported file type
   - Oversized image (>5 MB)
   - Corrupted image bytes
   - Image quality check failure
   - No face detected
   - Multiple faces detected
   - Re-registration deactivates old embeddings
   - Database rollback on exception
   - Role-based authorization
4. Nearest neighbor search & recognition of registered student vs unknown
"""
from datetime import datetime, timezone
import io
import time
import uuid
from unittest.mock import MagicMock, patch
import cv2
import numpy as np
import pytest
from sqlalchemy import select

from backend.app.models.face_embedding import FaceEmbedding
from backend.app.models.student import Student
from backend.app.services.registration_session import RegistrationSession, session_manager
from backend.app.vision.embedder import EMBEDDING_DIM, EmbeddingResult
from backend.app.vision.detector import DetectedFace


def _create_sample_jpeg(width: int = 300, height: int = 300) -> bytes:
    """Create a synthetic clear JPEG image in memory."""
    img = np.full((height, width, 3), 128, dtype=np.uint8)
    # Draw contrast so Laplacian variance / blur test passes
    cv2.circle(img, (width // 2, height // 2), 60, (220, 220, 220), -1)
    cv2.circle(img, (width // 2 - 20, height // 2 - 10), 8, (30, 30, 30), -1)
    cv2.circle(img, (width // 2 + 20, height // 2 - 10), 8, (30, 30, 30), -1)
    cv2.line(img, (width // 2 - 20, height // 2 + 25), (width // 2 + 20, height // 2 + 25), (40, 40, 40), 3)
    success, encoded = cv2.imencode(".jpg", img)
    assert success
    return encoded.tobytes()


def _create_student_via_api(client, admin_token, student_id: str, consent: bool = True) -> str:
    """Helper to create a student via the API."""
    res = client.post(
        "/api/v1/students",
        json={
            "student_id": student_id,
            "name": f"Student {student_id}",
            "department": "Computer Science",
            "year": 2,
            "consent": consent,
            "consent_version": "v1.0" if consent else None,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 201
    return res.json()["id"]


@pytest.fixture(autouse=True)
def clean_sessions():
    """Ensure in-memory sessions are wiped clean between tests."""
    with session_manager._lock:
        session_manager._sessions.clear()
        session_manager._tickets.clear()
        session_manager._active_cameras.clear()
    yield
    with session_manager._lock:
        session_manager._sessions.clear()
        session_manager._tickets.clear()
        session_manager._active_cameras.clear()


# ===========================================================================
# 1. RegistrationSession frame retrieval
# ===========================================================================

def test_registration_session_get_frames():
    """RegistrationSession provides thread-safe get_frames() returning list copy."""
    sess = RegistrationSession(
        session_id="test-sess-1",
        student_uuid=uuid.uuid4(),
        student_id="STU001",
        camera_id="0",
        target_samples=10,
        ttl_seconds=60,
    )
    frame1 = np.zeros((100, 100, 3), dtype=np.uint8)
    frame2 = np.ones((100, 100, 3), dtype=np.uint8)

    sess.add_frame(frame1)
    sess.add_frame(frame2)

    frames = sess.get_frames()
    assert len(frames) == 2
    assert np.array_equal(frames[0], frame1)
    assert np.array_equal(frames[1], frame2)

    # Modifying returned list must not alter internal session frames
    frames.clear()
    assert len(sess.get_frames()) == 2

    # sess.clear() empties frames
    sess.clear()
    assert len(sess.get_frames()) == 0


# ===========================================================================
# 2. Webcam registration commit
# ===========================================================================

def test_webcam_commit_success(client, admin_token, db_session):
    """Webcam session commits frames to DB via get_frames and cleans session."""
    student_id_str = _create_student_via_api(client, admin_token, "WEBCAM-01", consent=True)
    student_uuid = uuid.UUID(student_id_str)

    # Create session
    sess = session_manager.create_session(
        student_uuid=student_uuid,
        student_id="WEBCAM-01",
        camera_id="0",
        target_samples=10,
    )
    # Add dummy frames
    for _ in range(10):
        sess.add_frame(np.zeros((300, 300, 3), dtype=np.uint8))

    norm_vec = np.random.randn(512).astype(np.float32)
    norm_vec = (norm_vec / np.linalg.norm(norm_vec)).astype(np.float32)
    mock_detected = DetectedFace(bbox=[10, 10, 100, 100], landmarks=None, det_score=0.98)
    mock_emb = EmbeddingResult(vector=norm_vec, det_score=0.98, quality_score=0.85)

    with patch("backend.app.vision.detector.detect_faces", return_value=[mock_detected]), \
         patch("backend.app.vision.embedder.embed_face", return_value=mock_emb):
        res = client.post(
            f"/api/v1/students/{student_uuid}/face/commit",
            json={"session_id": sess.session_id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["stored_count"] == 10
        assert data["rejected_count"] == 0

    # Session must be deleted from session_manager
    assert session_manager.get_session(sess.session_id) is None

    # Embeddings must exist in DB
    embs = db_session.execute(
        select(FaceEmbedding).where(FaceEmbedding.student_id == student_uuid, FaceEmbedding.is_active.is_(True))
    ).scalars().all()
    assert len(embs) == 10
    assert len(embs[0].embedding) == 512


def test_webcam_commit_mismatched_student_returns_400(client, admin_token):
    """Commit with session belonging to a different student returns 400 Bad Request."""
    s1 = _create_student_via_api(client, admin_token, "STU-A", consent=True)
    s2 = _create_student_via_api(client, admin_token, "STU-B", consent=True)

    sess = session_manager.create_session(
        student_uuid=uuid.UUID(s1),
        student_id="STU-A",
        camera_id="0",
        target_samples=5,
    )

    res = client.post(
        f"/api/v1/students/{s2}/face/commit",
        json={"session_id": sess.session_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400
    assert "belong" in res.json()["error"]["message"].lower()


def test_webcam_commit_expired_session_returns_400(client, admin_token):
    """Commit with expired session returns 400."""
    s1 = _create_student_via_api(client, admin_token, "STU-EXP", consent=True)

    sess = session_manager.create_session(
        student_uuid=uuid.UUID(s1),
        student_id="STU-EXP",
        camera_id="0",
        target_samples=5,
    )
    sess.expires_at = time.time() - 10  # Expire

    res = client.post(
        f"/api/v1/students/{s1}/face/commit",
        json={"session_id": sess.session_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400
    assert "expired" in res.json()["error"]["message"].lower()


# ===========================================================================
# 3. Photo-upload face registration
# ===========================================================================

def test_upload_photo_without_consent_returns_400(client, admin_token):
    """Upload photo registration requires biometric consent, returning 400 if missing."""
    s1 = _create_student_via_api(client, admin_token, "NO-CONSENT-UPL", consent=False)

    img_bytes = _create_sample_jpeg()
    res = client.post(
        f"/api/v1/students/{s1}/face/upload",
        files={"photo": ("photo.jpg", img_bytes, "image/jpeg")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400
    assert "consent" in res.json()["error"]["message"].lower()


def test_upload_photo_inactive_student_returns_400(client, admin_token):
    """Upload photo registration for an INACTIVE student returns 400."""
    s1 = _create_student_via_api(client, admin_token, "INACTIVE-STU", consent=True)
    # Deactivate
    client.delete(f"/api/v1/students/{s1}", headers={"Authorization": f"Bearer {admin_token}"})

    img_bytes = _create_sample_jpeg()
    res = client.post(
        f"/api/v1/students/{s1}/face/upload",
        files={"photo": ("photo.jpg", img_bytes, "image/jpeg")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400
    assert "active" in res.json()["error"]["message"].lower()


def test_upload_photo_unauthorized_returns_401_or_403(client, admin_token, operator_token):
    """Non-admin user (e.g. OPERATOR) receives 403 Forbidden."""
    s1 = _create_student_via_api(client, admin_token, "AUTH-TEST", consent=True)

    img_bytes = _create_sample_jpeg()
    # 1. No token -> 401
    res_no_auth = client.post(
        f"/api/v1/students/{s1}/face/upload",
        files={"photo": ("photo.jpg", img_bytes, "image/jpeg")},
    )
    assert res_no_auth.status_code == 401

    # 2. Operator token -> 403
    res_op = client.post(
        f"/api/v1/students/{s1}/face/upload",
        files={"photo": ("photo.jpg", img_bytes, "image/jpeg")},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert res_op.status_code == 403


def test_upload_photo_missing_file_returns_400(client, admin_token):
    """POST /face/upload without any file returns 400."""
    s1 = _create_student_via_api(client, admin_token, "EMPTY-FILE", consent=True)

    res = client.post(
        f"/api/v1/students/{s1}/face/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400


def test_upload_photo_unsupported_type_returns_400(client, admin_token):
    """Uploading a text or pdf file returns 400 Bad Request."""
    s1 = _create_student_via_api(client, admin_token, "BAD-EXT", consent=True)

    res = client.post(
        f"/api/v1/students/{s1}/face/upload",
        files={"photo": ("document.pdf", b"%PDF-1.4...", "application/pdf")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400
    assert "unsupported" in res.json()["error"]["message"].lower() or "invalid" in res.json()["error"]["message"].lower()


def test_upload_photo_corrupted_image_returns_400(client, admin_token):
    """Uploading random corrupted bytes disguised as image/jpeg returns 400."""
    s1 = _create_student_via_api(client, admin_token, "CORRUPT-IMG", consent=True)

    res = client.post(
        f"/api/v1/students/{s1}/face/upload",
        files={"photo": ("corrupt.jpg", b"\xff\xd8\xffcorrupted content", "image/jpeg")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400
    assert "corrupted" in res.json()["error"]["message"].lower() or "invalid" in res.json()["error"]["message"].lower()


def test_upload_photo_oversized_returns_400(client, admin_token):
    """Uploading an image larger than 5 MB returns 400."""
    s1 = _create_student_via_api(client, admin_token, "OVERSIZED", consent=True)

    oversized_data = b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024 + 10)
    res = client.post(
        f"/api/v1/students/{s1}/face/upload",
        files={"photo": ("large.jpg", oversized_data, "image/jpeg")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400
    assert "large" in res.json()["error"]["message"].lower() or "exceeds" in res.json()["error"]["message"].lower()


def test_upload_photo_poor_quality_returns_422(client, admin_token):
    """Uploading an image that is too small (< 240px) fails quality check with 422."""
    s1 = _create_student_via_api(client, admin_token, "TINY-IMG", consent=True)

    # Create 100x100 image (less than MIN_IMAGE_SIDE 240)
    small_img = _create_sample_jpeg(width=100, height=100)
    res = client.post(
        f"/api/v1/students/{s1}/face/upload",
        files={"photo": ("small.jpg", small_img, "image/jpeg")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 422
    assert "quality" in res.json()["error"]["message"].lower() or "too_small" in res.json()["error"]["message"].lower()


def test_upload_photo_no_face_detected_returns_422(client, admin_token):
    """If image passes quality checks but detector finds 0 faces, return 422."""
    s1 = _create_student_via_api(client, admin_token, "NO-FACE-STU", consent=True)

    img_bytes = _create_sample_jpeg(width=320, height=320)

    with patch("backend.app.vision.detector.detect_single_face", return_value=(None, "NO_FACE")):
        res = client.post(
            f"/api/v1/students/{s1}/face/upload",
            files={"photo": ("photo.jpg", img_bytes, "image/jpeg")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 422
        assert "no face" in res.json()["error"]["message"].lower()


def test_upload_photo_multiple_faces_detected_returns_422(client, admin_token):
    """If image contains multiple faces, return 422 Unprocessable Entity."""
    s1 = _create_student_via_api(client, admin_token, "MULTI-FACE-STU", consent=True)

    img_bytes = _create_sample_jpeg(width=320, height=320)

    with patch("backend.app.vision.detector.detect_single_face", return_value=(None, "MULTIPLE_FACES")):
        res = client.post(
            f"/api/v1/students/{s1}/face/upload",
            files={"photo": ("photo.jpg", img_bytes, "image/jpeg")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 422
        assert "multiple" in res.json()["error"]["message"].lower()


def test_upload_photo_success_saves_embedding(client, admin_token, db_session):
    """Successful photo upload generates 512-d normalized embedding and saves to PostgreSQL."""
    s1 = _create_student_via_api(client, admin_token, "SUCCESS-UPL", consent=True)
    student_uuid = uuid.UUID(s1)

    img_bytes = _create_sample_jpeg(width=320, height=320)

    norm_vec = np.random.randn(512).astype(np.float32)
    norm_vec = (norm_vec / np.linalg.norm(norm_vec)).astype(np.float32)
    mock_detected = DetectedFace(bbox=[30, 30, 200, 200], landmarks=None, det_score=0.99)
    mock_emb = EmbeddingResult(vector=norm_vec, det_score=0.99, quality_score=0.92)

    with patch("backend.app.vision.detector.detect_single_face", return_value=(mock_detected, "OK")), \
         patch("backend.app.vision.embedder.embed_face", return_value=mock_emb):
        res = client.post(
            f"/api/v1/students/{student_uuid}/face/upload",
            files={"photo": ("photo.jpg", img_bytes, "image/jpeg")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["stored_count"] == 1
        assert data["rejected_count"] == 0
        assert data["method"] == "photo_upload"
        assert abs(data["quality_score"] - 0.92) < 1e-3

    # Verify DB record
    embs = db_session.execute(
        select(FaceEmbedding).where(FaceEmbedding.student_id == student_uuid, FaceEmbedding.is_active.is_(True))
    ).scalars().all()
    assert len(embs) == 1
    assert len(embs[0].embedding) == 512
    # Verify vector norm
    loaded_vec = np.array(embs[0].embedding, dtype=np.float32)
    assert abs(np.linalg.norm(loaded_vec) - 1.0) < 1e-3


def test_upload_photo_re_registration_deactivates_old_embeddings(client, admin_token, db_session):
    """Re-registering face deactivates previous embeddings ensuring consistent behavior."""
    s1 = _create_student_via_api(client, admin_token, "RE-REG", consent=True)
    student_uuid = uuid.UUID(s1)

    img_bytes = _create_sample_jpeg(width=320, height=320)

    # First registration
    vec1 = np.random.randn(512).astype(np.float32)
    vec1 = (vec1 / np.linalg.norm(vec1)).astype(np.float32)
    mock_emb1 = EmbeddingResult(vector=vec1, det_score=0.95, quality_score=0.88)
    mock_det = DetectedFace(bbox=[20, 20, 150, 150], landmarks=None, det_score=0.95)

    with patch("backend.app.vision.detector.detect_single_face", return_value=(mock_det, "OK")), \
         patch("backend.app.vision.embedder.embed_face", return_value=mock_emb1):
        r1 = client.post(
            f"/api/v1/students/{student_uuid}/face/upload",
            files={"photo": ("photo1.jpg", img_bytes, "image/jpeg")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r1.status_code == 200

    # Second registration
    vec2 = np.random.randn(512).astype(np.float32)
    vec2 = (vec2 / np.linalg.norm(vec2)).astype(np.float32)
    mock_emb2 = EmbeddingResult(vector=vec2, det_score=0.98, quality_score=0.94)

    with patch("backend.app.vision.detector.detect_single_face", return_value=(mock_det, "OK")), \
         patch("backend.app.vision.embedder.embed_face", return_value=mock_emb2):
        r2 = client.post(
            f"/api/v1/students/{student_uuid}/face/upload",
            files={"photo": ("photo2.jpg", img_bytes, "image/jpeg")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r2.status_code == 200

    # DB verification: only 1 active embedding, 1 inactive embedding
    active_embs = db_session.execute(
        select(FaceEmbedding).where(FaceEmbedding.student_id == student_uuid, FaceEmbedding.is_active.is_(True))
    ).scalars().all()
    assert len(active_embs) == 1

    all_embs = db_session.execute(
        select(FaceEmbedding).where(FaceEmbedding.student_id == student_uuid)
    ).scalars().all()
    assert len(all_embs) == 2


def test_upload_photo_database_failure_rollback(client, admin_token, db_session):
    """Database exception triggers transaction rollback cleanly."""
    s1 = _create_student_via_api(client, admin_token, "ROLLBACK-STU", consent=True)
    student_uuid = uuid.UUID(s1)

    img_bytes = _create_sample_jpeg(width=320, height=320)
    norm_vec = np.random.randn(512).astype(np.float32)
    norm_vec = (norm_vec / np.linalg.norm(norm_vec)).astype(np.float32)
    mock_emb = EmbeddingResult(vector=norm_vec, det_score=0.95, quality_score=0.88)
    mock_det = DetectedFace(bbox=[20, 20, 150, 150], landmarks=None, det_score=0.95)

    with patch("backend.app.vision.detector.detect_single_face", return_value=(mock_det, "OK")), \
         patch("backend.app.vision.embedder.embed_face", return_value=mock_emb), \
         patch("backend.app.db.repositories.face_repo.add_embeddings", side_effect=RuntimeError("DB Connection Lost")):
        with pytest.raises(RuntimeError, match="DB Connection Lost"):
            client.post(
                f"/api/v1/students/{student_uuid}/face/upload",
                files={"photo": ("photo.jpg", img_bytes, "image/jpeg")},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

    # Verify no active embeddings were saved
    active_embs = db_session.execute(
        select(FaceEmbedding).where(FaceEmbedding.student_id == student_uuid, FaceEmbedding.is_active.is_(True))
    ).scalars().all()
    assert len(active_embs) == 0


# ===========================================================================
# 4. Recognition & Attendance Workflow Verification
# ===========================================================================

def test_nearest_search_finds_registered_student_and_rejects_unknown(client, admin_token, db_session):
    """
    Verification that saved embeddings in PostgreSQL are indexed and queryable via nearest(),
    matching registered student with high similarity, and rejecting distant vectors.
    """
    from backend.app.db.repositories import face_repo

    s1 = _create_student_via_api(client, admin_token, "RECOG-01", consent=True)
    student_uuid = uuid.UUID(s1)

    # Generate a registered embedding vector
    registered_vec = np.random.randn(512).astype(np.float32)
    registered_vec = (registered_vec / np.linalg.norm(registered_vec)).astype(np.float32)

    # Save to PostgreSQL
    face_repo.add_embeddings(
        db=db_session,
        embeddings=[registered_vec],
        student_id=student_uuid,
        quality_scores=[0.95],
    )
    db_session.flush()

    # 1. Query with exact/similar vector (sim > 0.85)
    query_similar = registered_vec + np.random.normal(0, 0.02, 512).astype(np.float32)
    query_similar = (query_similar / np.linalg.norm(query_similar)).astype(np.float32)

    matches = face_repo.nearest(db_session, query_similar, k=1)
    assert len(matches) > 0
    matched_student_id, _, similarity = matches[0]
    assert matched_student_id == student_uuid
    assert similarity > 0.85, f"Expected high similarity, got {similarity}"

    # 2. Query with orthogonal/unknown vector (sim < 0.6)
    orthogonal_vec = np.random.randn(512).astype(np.float32)
    # Project to orthogonal space
    orthogonal_vec -= np.dot(orthogonal_vec, registered_vec) * registered_vec
    orthogonal_vec = (orthogonal_vec / np.linalg.norm(orthogonal_vec)).astype(np.float32)

    unknown_matches = face_repo.nearest(db_session, orthogonal_vec, k=1)
    if unknown_matches:
        _, _, unk_sim = unknown_matches[0]
        # Cosine similarity with orthogonal vector should be near 0 (well below 0.6 threshold)
        assert unk_sim < 0.6, f"Unknown face similarity {unk_sim} should be below threshold 0.6"
