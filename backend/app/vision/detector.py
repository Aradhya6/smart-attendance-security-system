"""
Face Detector — wraps InsightFace SCRFD detection.

Returns a list of DetectedFace objects (bbox, landmarks, score).
Filters faces by confidence score (DET_THRESHOLD) and minimum face width
(MIN_FACE_PIXELS) as required by the playbook.

Detection-only mode: ModelRegistry is called with allowed_modules=['detection']
in Phase 10 and upgraded to ['detection','recognition'] in Phase 11.

All latency is logged at DEBUG level; never logged with face data.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DetectedFace:
    """
    Result of a single face detection.

    Attributes
    ----------
    bbox : list[int]
        [x1, y1, x2, y2] in pixel coordinates.
    landmarks : np.ndarray | None
        5-point facial landmarks (shape [5, 2]) or None if not available.
    det_score : float
        Detector confidence (0–1).
    """

    bbox: List[int]
    landmarks: Optional[np.ndarray]
    det_score: float

    # Raw InsightFace Face object; kept for embedder use (not serialised)
    _raw: Optional[object] = field(default=None, repr=False, compare=False)


def detect_faces(
    frame: np.ndarray,
    det_threshold: Optional[float] = None,
    min_face_pixels: Optional[int] = None,
    registry=None,
) -> List[DetectedFace]:
    """
    Run SCRFD face detection on *frame* and return accepted detections.

    Parameters
    ----------
    frame : np.ndarray
        BGR image (H, W, 3).
    det_threshold : float, optional
        Minimum detection confidence. Defaults to env DET_THRESHOLD (0.5).
    min_face_pixels : int, optional
        Minimum face bounding-box width in pixels. Defaults to env MIN_FACE_PIXELS (80).
    registry : ModelRegistry, optional
        Custom registry (for testing). Defaults to the singleton.

    Returns
    -------
    list[DetectedFace]
        Detections passing both filters, ordered by decreasing det_score.
        Empty list if no faces found, frame is bad, or model unavailable.
    """
    if frame is None or frame.size == 0:
        logger.debug("detect_faces: received empty frame, returning []")
        return []

    if det_threshold is None:
        det_threshold = float(os.environ.get("DET_THRESHOLD", "0.5"))
    if min_face_pixels is None:
        min_face_pixels = int(os.environ.get("MIN_FACE_PIXELS", "80"))

    if registry is None:
        from backend.app.vision.model_registry import ModelRegistry

        registry = ModelRegistry.instance()

    try:
        app = registry.get()
    except RuntimeError as exc:
        logger.warning("detect_faces: model unavailable: %s", exc)
        return []

    t0 = time.perf_counter()
    try:
        raw_faces = app.get(frame)
    except Exception as exc:  # noqa: BLE001
        logger.warning("detect_faces: inference error: %s", exc)
        return []
    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.debug("detect_faces: inference took %.1f ms, raw faces=%d", elapsed_ms, len(raw_faces))

    results: List[DetectedFace] = []
    for face in raw_faces:
        score = float(face.det_score) if hasattr(face, "det_score") else 1.0
        if score < det_threshold:
            logger.debug("detect_faces: skipping face with score %.3f < threshold %.3f", score, det_threshold)
            continue

        bbox_raw = face.bbox.astype(int).tolist() if hasattr(face, "bbox") else [0, 0, 0, 0]
        # bbox_raw is [x1, y1, x2, y2]
        face_width = bbox_raw[2] - bbox_raw[0]
        if face_width < min_face_pixels:
            logger.debug(
                "detect_faces: skipping face width=%d < min_face_pixels=%d",
                face_width,
                min_face_pixels,
            )
            continue

        kps = face.kps if hasattr(face, "kps") and face.kps is not None else None

        results.append(
            DetectedFace(
                bbox=bbox_raw,
                landmarks=kps,
                det_score=score,
                _raw=face,
            )
        )

    # Sort by decreasing confidence
    results.sort(key=lambda f: f.det_score, reverse=True)
    logger.debug(
        "detect_faces: %d faces passed filters (threshold=%.2f, min_px=%d)",
        len(results),
        det_threshold,
        min_face_pixels,
    )
    return results


def detect_single_face(
    frame: np.ndarray,
    det_threshold: Optional[float] = None,
    min_face_pixels: Optional[int] = None,
    registry=None,
) -> tuple[Optional[DetectedFace], str]:
    """
    Detect exactly one face suitable for registration/embedding.

    Returns
    -------
    (face, reason) : tuple
        face is None when not exactly one valid face is found.
        reason is one of: 'OK', 'NO_FACE', 'MULTIPLE_FACES', 'FACE_TOO_SMALL'.
    """
    faces = detect_faces(frame, det_threshold=det_threshold, min_face_pixels=min_face_pixels, registry=registry)

    if len(faces) == 0:
        # Check for faces below min_face_pixels (before pixel filter)
        raw_faces = _get_raw_faces(frame, registry)
        if raw_faces and all(
            (f.bbox[2] - f.bbox[0]) < (min_face_pixels or int(os.environ.get("MIN_FACE_PIXELS", "80")))
            for f in _raw_to_detected(raw_faces, det_threshold or float(os.environ.get("DET_THRESHOLD", "0.5")))
        ):
            return None, "FACE_TOO_SMALL"
        return None, "NO_FACE"

    if len(faces) > 1:
        return None, "MULTIPLE_FACES"

    return faces[0], "OK"


def _get_raw_faces(frame: np.ndarray, registry=None) -> list:
    """Get raw faces without size filtering (for FACE_TOO_SMALL detection)."""
    if registry is None:
        from backend.app.vision.model_registry import ModelRegistry

        registry = ModelRegistry.instance()
    try:
        app = registry.get()
        return app.get(frame)
    except Exception:  # noqa: BLE001
        return []


def _raw_to_detected(raw_faces: list, det_threshold: float) -> List[DetectedFace]:
    """Convert raw InsightFace faces to DetectedFace, applying score filter only."""
    results = []
    for face in raw_faces:
        score = float(face.det_score) if hasattr(face, "det_score") else 1.0
        if score < det_threshold:
            continue
        bbox_raw = face.bbox.astype(int).tolist() if hasattr(face, "bbox") else [0, 0, 0, 0]
        kps = face.kps if hasattr(face, "kps") and face.kps is not None else None
        results.append(DetectedFace(bbox=bbox_raw, landmarks=kps, det_score=score, _raw=face))
    return results
