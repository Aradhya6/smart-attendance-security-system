"""
Face Service — sync version (Phase 12).
Orchestrates: session frames → detect → embed → consistency → DB commit.
"""
from __future__ import annotations
import logging
import uuid
from typing import Tuple
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.repositories import face_repo
from backend.app.services.registration_session import session_manager
from backend.app.vision.quality import check_consistency

logger = logging.getLogger(__name__)


def commit_face_registration(
    db: Session,
    student_uuid: uuid.UUID,
    session_id: str,
    model_name: str | None = None,
    model_version: str = "w600k_r50",
) -> Tuple[int, int]:
    """
    Convert an in-memory registration session into stored face embeddings.
    Returns (stored_count, rejected_count).
    Raises ValueError or RuntimeError on failure.
    """
    settings = get_settings()
    if model_name is None:
        model_name = settings.insightface_model_name

    session = session_manager.get_session(session_id)
    if session is None or session.is_expired():
        raise ValueError("Registration session not found or expired")
    if session.student_uuid != student_uuid:
        raise ValueError("Session does not belong to this student")

    frames = session.get_frames()
    min_samples = settings.face_min_samples
    if len(frames) < min_samples:
        raise ValueError(f"Too few samples: {len(frames)} collected, {min_samples} required")

    from backend.app.vision.detector import detect_faces
    from backend.app.vision.embedder import embed_face
    from backend.app.vision.model_registry import ModelRegistry

    registry = ModelRegistry.instance()

    raw_embeddings = []
    quality_scores = []

    for frame in frames:
        faces = detect_faces(frame, registry=registry)
        if not faces:
            continue
        result = embed_face(frame, faces[0], registry=registry)
        if result is not None:
            raw_embeddings.append(result.vector)
            quality_scores.append(result.quality_score)

    if not raw_embeddings:
        raise RuntimeError(
            "No embeddings could be computed. Ensure the model is loaded and faces are visible."
        )

    accepted, rejected_indices = check_consistency(raw_embeddings)
    accepted_quality = [quality_scores[i] for i in range(len(quality_scores)) if i not in rejected_indices]

    if not accepted:
        raise RuntimeError("All embeddings failed consistency check. Re-register with better lighting.")

    try:
        face_repo.deactivate_for_student(db, student_uuid)
        face_repo.add_embeddings(
            db=db,
            embeddings=accepted,
            student_id=student_uuid,
            model_name=model_name,
            model_version=model_version,
            quality_scores=accepted_quality,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    session_manager.delete_session(session_id)
    logger.info("commit_face_registration: student=%s stored=%d rejected=%d",
                student_uuid, len(accepted), len(rejected_indices))
    return len(accepted), len(rejected_indices)
