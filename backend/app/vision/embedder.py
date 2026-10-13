"""
Face Embedder — ArcFace w600k_r50 embedding generation (Phase 11).

Converts a detected face into a normalised 512-d float32 embedding vector
using the InsightFace ArcFace model loaded via ModelRegistry.

Key guarantees (enforced with assertions):
- embedding.shape == (512,)
- embedding.dtype == float32
- abs(norm - 1.0) < 1e-3  (L2-normalised)

Embeddings are NEVER logged or returned by any API.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# EMBEDDING_DIM is a module-level constant so other modules can reference it
# without importing numpy or insightface.
EMBEDDING_DIM = 512


@dataclass
class EmbeddingResult:
    """
    Result of a single face embedding pass.

    Attributes
    ----------
    vector : np.ndarray
        L2-normalised float32 vector of shape (512,).  Never log or return.
    det_score : float
        Detection confidence from the upstream detector.
    quality_score : float
        Sharpness-based quality estimate (Laplacian variance, normalised 0–1).
        Used as a hint for registration; not a hard gate.
    """

    vector: np.ndarray
    det_score: float
    quality_score: float = 0.0

    def __post_init__(self) -> None:
        assert self.vector.shape == (EMBEDDING_DIM,), (
            f"Embedding shape must be ({EMBEDDING_DIM},), got {self.vector.shape}"
        )
        assert self.vector.dtype == np.float32, (
            f"Embedding dtype must be float32, got {self.vector.dtype}"
        )
        norm = float(np.linalg.norm(self.vector))
        assert abs(norm - 1.0) < 1e-3, (
            f"Embedding must be L2-normalised (norm≈1), got norm={norm:.6f}"
        )


def embed_face(
    frame: np.ndarray,
    face,  # insightface Face object (DetectedFace._raw)
    registry=None,
) -> Optional[EmbeddingResult]:
    """
    Compute the ArcFace embedding for *face* detected in *frame*.

    Parameters
    ----------
    frame : np.ndarray
        BGR image that produced the detection.
    face : insightface Face | DetectedFace
        The detected face.  If it has a `normed_embedding` attribute (set by
        InsightFace recognition module), that is used directly.  Otherwise the
        ModelRegistry is queried to produce it.
    registry : ModelRegistry, optional
        Override for testing.

    Returns
    -------
    EmbeddingResult or None
        None if embedding cannot be produced (bad frame, model unavailable,
        assertion failure).
    """
    if registry is None:
        from backend.app.vision.model_registry import ModelRegistry

        registry = ModelRegistry.instance()

    # Get raw InsightFace face object
    raw_face = getattr(face, "_raw", face)

    # If InsightFace already embedded the face (normed_embedding is set),
    # use it directly — avoids a double pass through the recogniser.
    if hasattr(raw_face, "normed_embedding") and raw_face.normed_embedding is not None:
        vec = np.array(raw_face.normed_embedding, dtype=np.float32)
    else:
        # Need to run recognition module — ensure registry loaded with recognition
        try:
            app = registry.get(allowed_modules=["detection", "recognition"])
        except RuntimeError as exc:
            logger.warning("embed_face: model unavailable: %s", exc)
            return None

        # Re-run app.get() on frame with recognition enabled
        t0 = time.perf_counter()
        try:
            fresh_faces = app.get(frame)
        except Exception as exc:  # noqa: BLE001
            logger.warning("embed_face: inference error: %s", exc)
            return None
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug("embed_face: recognition pass took %.1f ms", elapsed_ms)

        if not fresh_faces:
            logger.debug("embed_face: no faces returned from re-run")
            return None

        # Pick the face matching by bbox proximity
        target_bbox = getattr(raw_face, "bbox", None)
        matched_raw = _match_face_by_bbox(fresh_faces, target_bbox)
        if matched_raw is None:
            matched_raw = fresh_faces[0]

        if not hasattr(matched_raw, "normed_embedding") or matched_raw.normed_embedding is None:
            logger.debug("embed_face: normed_embedding not available after recognition pass")
            return None
        vec = np.array(matched_raw.normed_embedding, dtype=np.float32)

    # Safety: re-normalise to guarantee unit norm
    norm = float(np.linalg.norm(vec))
    if norm < 1e-8:
        logger.warning("embed_face: zero-norm embedding discarded")
        return None
    vec = (vec / norm).astype(np.float32)

    # Compute a simple quality score from the original frame region
    quality = _estimate_quality(frame, face)
    det_score = float(getattr(raw_face, "det_score", 1.0))

    try:
        result = EmbeddingResult(vector=vec, det_score=det_score, quality_score=quality)
    except AssertionError as exc:
        logger.warning("embed_face: embedding assertion failed: %s", exc)
        return None

    return result


def _match_face_by_bbox(faces: list, target_bbox) -> Optional[object]:
    """Return the face whose bbox centre is closest to target_bbox."""
    if target_bbox is None or len(faces) == 1:
        return faces[0] if faces else None

    def centre(bbox):
        return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)

    tx, ty = centre(target_bbox)
    best = None
    best_dist = float("inf")
    for f in faces:
        if not hasattr(f, "bbox"):
            continue
        fx, fy = centre(f.bbox)
        d = (fx - tx) ** 2 + (fy - ty) ** 2
        if d < best_dist:
            best_dist = d
            best = f
    return best


def _estimate_quality(frame: np.ndarray, face) -> float:
    """
    Estimate sharpness-based quality for the face crop.

    Returns a float in [0, 1]: 1 = very sharp, 0 = very blurry.
    Quality is clamped from Laplacian variance normalised at 500 (heuristic).
    """
    try:
        import cv2

        bbox = getattr(getattr(face, "_raw", face), "bbox", None)
        if bbox is None:
            bbox = getattr(face, "bbox", None)
        if bbox is None or frame is None:
            return 0.0
        x1, y1, x2, y2 = [int(v) for v in bbox]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
        if x2 <= x1 or y2 <= y1:
            return 0.0
        crop = frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        return min(1.0, lap_var / 500.0)
    except Exception:  # noqa: BLE001
        return 0.0
