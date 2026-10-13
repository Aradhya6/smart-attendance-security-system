"""
Face Embedding Repository — SYNC SQLAlchemy (Phase 12).

All operations use synchronous sessions (psycopg/psycopg2) consistent
with the rest of the codebase.
"""
from __future__ import annotations

import uuid
import logging
from typing import List, Optional, Tuple

import numpy as np
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from backend.app.models.face_embedding import FaceEmbedding

logger = logging.getLogger(__name__)

HNSW_EF_SEARCH = 40


def add_embeddings(
    db: Session,
    embeddings: List[np.ndarray],
    student_id: Optional[uuid.UUID] = None,
    blacklist_entry_id: Optional[uuid.UUID] = None,
    model_name: str = "buffalo_s",
    model_version: str = "w600k_r50",
    quality_scores: Optional[List[float]] = None,
) -> List[uuid.UUID]:
    """Insert new face embeddings. Caller must commit the transaction."""
    assert (student_id is None) != (blacklist_entry_id is None), \
        "Exactly one of student_id or blacklist_entry_id must be set"
    if quality_scores is None:
        quality_scores = [None] * len(embeddings)

    new_ids = []
    for i, vec in enumerate(embeddings):
        emb = FaceEmbedding(
            id=uuid.uuid4(),
            student_id=student_id,
            blacklist_entry_id=blacklist_entry_id,
            embedding=vec.tolist(),
            model_name=model_name,
            model_version=model_version,
            quality_score=quality_scores[i],
            is_active=True,
        )
        db.add(emb)
        new_ids.append(emb.id)

    db.flush()
    logger.info("add_embeddings: inserted %d embeddings for student=%s", len(embeddings), student_id)
    return new_ids


def deactivate_for_student(db: Session, student_id: uuid.UUID) -> int:
    """Soft-deactivate all active embeddings for a student."""
    result = db.execute(
        update(FaceEmbedding)
        .where(FaceEmbedding.student_id == student_id)
        .where(FaceEmbedding.is_active.is_(True))
        .values(is_active=False)
        .execution_options(synchronize_session="fetch")
    )
    return result.rowcount


def delete_for_student(db: Session, student_id: uuid.UUID) -> int:
    """Hard-delete all embeddings for a student."""
    result = db.execute(
        text("DELETE FROM face_embeddings WHERE student_id = :sid"),
        {"sid": str(student_id)},
    )
    return result.rowcount


def count_active_for_student(db: Session, student_id: uuid.UUID) -> int:
    """Return count of active embeddings for a student."""
    result = db.execute(
        text("SELECT COUNT(*) FROM face_embeddings WHERE student_id = :sid AND is_active = true"),
        {"sid": str(student_id)},
    )
    return result.scalar() or 0


def nearest(
    db: Session,
    query_vector: np.ndarray,
    k: int = 5,
) -> List[Tuple[Optional[uuid.UUID], Optional[uuid.UUID], float]]:
    """
    Find k nearest active embeddings by cosine similarity.
    similarity = 1 - cosine_distance.
    """
    try:
        db.execute(text(f"SET LOCAL hnsw.ef_search = {HNSW_EF_SEARCH}"))
    except Exception:
        pass  # Not all postgres versions support SET LOCAL in all contexts

    vec_list = query_vector.tolist()
    rows = db.execute(
        text("""
            SELECT student_id, blacklist_entry_id,
                   1 - (embedding <=> CAST(:q AS vector)) AS similarity
            FROM face_embeddings
            WHERE is_active = true
            ORDER BY embedding <=> CAST(:q AS vector)
            LIMIT :k
        """),
        {"q": str(vec_list), "k": k},
    ).fetchall()

    return [
        (row.student_id, row.blacklist_entry_id, float(row.similarity))
        for row in rows
    ]
