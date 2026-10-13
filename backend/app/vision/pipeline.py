"""
VisionPipeline — SYNC version (Phase 13).
detect → embed → pgvector search → decide → FaceResult list.
"""
from __future__ import annotations
import logging
import uuid
from typing import Dict, List, Optional
import numpy as np

from backend.app.vision.detector import detect_faces
from backend.app.vision.embedder import embed_face
from backend.app.vision.recognizer import FaceResult, aggregate_candidates, decide

logger = logging.getLogger(__name__)


class VisionPipeline:
    def __init__(
        self,
        db_session_factory=None,
        threshold: float = 0.50,
        margin: float = 0.05,
        top_k: int = 5,
        registry=None,
        student_id_cache: Optional[Dict[uuid.UUID, tuple]] = None,
    ) -> None:
        self.db_session_factory = db_session_factory
        self.threshold = threshold
        self.margin = margin
        self.top_k = top_k
        self.registry = registry
        self.student_id_cache: Dict[uuid.UUID, tuple] = student_id_cache or {}

    def process(self, frame: np.ndarray) -> List[FaceResult]:
        """Run full pipeline on a single frame. Sync version."""
        detected = detect_faces(frame, registry=self.registry)
        if not detected:
            return []

        results: List[FaceResult] = []
        for face in detected:
            emb_result = embed_face(frame, face, registry=self.registry)
            if emb_result is None:
                results.append(FaceResult(
                    recognized=False, kind="UNKNOWN", student_id=None, name=None,
                    similarity=0.0, bbox=face.bbox, det_score=face.det_score,
                ))
                continue

            raw_candidates = self._search(emb_result.vector)
            candidates = aggregate_candidates(raw_candidates)
            recognized, kind, best = decide(candidates, self.threshold, self.margin)

            if recognized and best is not None:
                student_uuid = best.student_id
                sid_str, name = self._lookup(student_uuid)
                results.append(FaceResult(
                    recognized=True, kind=kind, student_id=sid_str, name=name,
                    similarity=best.similarity, bbox=face.bbox, det_score=face.det_score,
                    _student_uuid=student_uuid,
                ))
            else:
                results.append(FaceResult(
                    recognized=False, kind="UNKNOWN", student_id=None, name=None,
                    similarity=best.similarity if best else 0.0,
                    bbox=face.bbox, det_score=face.det_score,
                ))
        return results

    def _search(self, vector: np.ndarray):
        if self.db_session_factory is None:
            return []
        try:
            from backend.app.db.repositories.face_repo import nearest
            with self.db_session_factory() as db:
                return nearest(db, vector, k=self.top_k)
        except Exception as exc:
            logger.warning("VisionPipeline._search error: %s", exc)
            return []

    def _lookup(self, student_uuid: Optional[uuid.UUID]) -> tuple:
        if student_uuid is None:
            return None, None
        entry = self.student_id_cache.get(student_uuid)
        if entry:
            return entry
        return str(student_uuid)[:8], None

    def update_cache(self, student_uuid: uuid.UUID, student_id_str: str, name: str) -> None:
        self.student_id_cache[student_uuid] = (student_id_str, name)
