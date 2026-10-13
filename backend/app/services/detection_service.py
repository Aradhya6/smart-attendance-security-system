"""
Detection Service — Phase 17.

Writes deduplicated detection_events for UNKNOWN and RECOGNIZED tracks.
Per-track cooldown prevents event spam.
Unknown faces NEVER get attendance.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pytz
from sqlalchemy import text

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


class DetectionService:
    def __init__(self) -> None:
        settings = get_settings()
        self._unknown_cooldown = settings.unknown_event_cooldown_seconds
        self._recognized_cooldown = settings.recognized_event_cooldown_seconds
        self._snapshot_enabled = settings.unknown_snapshot_enabled
        self._cache: Dict[Tuple, float] = {}
        self._lock = threading.Lock()

    def handle_observation(self, track_id: str, face_result, camera_id: uuid.UUID) -> None:
        """Observer callback for detection events. Non-raising."""
        try:
            self._handle(track_id, face_result, camera_id)
        except Exception as exc:
            logger.error("DetectionService error (non-fatal): %s", exc)

    def _handle(self, track_id: str, face_result, camera_id: uuid.UUID) -> None:
        kind = face_result.kind
        if kind not in ("UNKNOWN", "STUDENT", "BLACKLISTED"):
            return

        cooldown = self._unknown_cooldown if kind == "UNKNOWN" else self._recognized_cooldown
        cache_key = (track_id, kind)

        with self._lock:
            last_ts = self._cache.get(cache_key)
            if last_ts is not None and (time.time() - last_ts) < cooldown:
                return
            self._cache[cache_key] = time.time()

        # bbox as list of ints for ARRAY(SmallInteger)
        bbox: Optional[List[int]] = None
        if face_result.bbox:
            try:
                bbox = [int(v) for v in face_result.bbox]
            except Exception:
                bbox = None

        from backend.app.db.session import SessionLocal
        with SessionLocal() as db:
            try:
                db.execute(
                    text("""
                        INSERT INTO detection_events
                            (camera_id, event_type, similarity, bbox, track_id, occurred_at, created_at)
                        VALUES
                            (:camera_id, :event_type, :similarity, :bbox, :track_id, NOW(), NOW())
                    """),
                    {
                        "camera_id": str(camera_id),
                        "event_type": kind,
                        "similarity": face_result.similarity,
                        "bbox": bbox,
                        "track_id": track_id,
                    },
                )
                db.commit()
                logger.debug("DetectionEvent: kind=%s track=%s camera=%s", kind, track_id, camera_id)
            except Exception as exc:
                db.rollback()
                logger.warning("DetectionService DB write failed: %s", exc)
