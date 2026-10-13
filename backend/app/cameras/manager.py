"""
CameraManager — Phase 14.

Single-camera manager for the MVP. Manages worker lifecycle and the
student-label cache for the shared VisionPipeline.
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self) -> None:
        self._workers: Dict[uuid.UUID, object] = {}  # camera_id → CameraWorker

    def start_worker(self, camera_id: uuid.UUID, db: Session) -> str:
        """Start a worker for the given camera. Raises ValueError if already running."""
        from backend.app.cameras.webcam import WebcamSource
        from backend.app.cameras.worker import CameraWorker, RUNNING
        from backend.app.core.config import get_settings
        from backend.app.models.camera import Camera
        from backend.app.models.student import Student
        from backend.app.vision.model_registry import ModelRegistry
        from backend.app.vision.pipeline import VisionPipeline
        from backend.app.db.repositories.face_repo import count_active_for_student

        if camera_id in self._workers:
            w = self._workers[camera_id]
            if w.status == RUNNING:
                raise ValueError(f"Worker for camera {camera_id} is already running")

        settings = get_settings()

        # Load camera record
        camera = db.get(Camera, camera_id)
        if camera is None:
            raise ValueError(f"Camera {camera_id} not found")

        # Build student label cache
        students = db.query(Student).filter(Student.is_active.is_(True)).all()
        student_cache = {s.id: (s.student_id, s.full_name) for s in students}

        # Build pipeline
        registry = ModelRegistry.instance()
        from backend.app.db.session import SessionLocal
        pipeline = VisionPipeline(
            db_session_factory=SessionLocal,
            threshold=settings.recognition_threshold,
            margin=settings.recognition_margin,
            top_k=settings.top_k,
            registry=registry,
            student_id_cache=student_cache,
        )

        # Source
        try:
            cam_index = int(camera.source_url or settings.webcam_index)
        except (ValueError, TypeError):
            cam_index = int(settings.webcam_index)

        source = WebcamSource(camera_index=cam_index)

        worker = CameraWorker(
            camera_id=camera_id,
            source=source,
            pipeline=pipeline,
        )

        # Wire attendance handler
        from backend.app.services.attendance_service import AttendanceService
        att_service = AttendanceService()
        worker.add_observer(att_service.handle_confirmed)

        # Wire detection event handler (Phase 17)
        from backend.app.services.detection_service import DetectionService
        det_service = DetectionService()
        worker.add_observer(det_service.handle_observation)

        worker.start()
        self._workers[camera_id] = worker
        logger.info("CameraManager: started worker for camera %s", camera_id)
        return worker.status

    def stop_worker(self, camera_id: uuid.UUID) -> str:
        """Stop a worker. Returns final status."""
        from backend.app.cameras.worker import STOPPED
        if camera_id not in self._workers:
            return STOPPED
        worker = self._workers.pop(camera_id)
        worker.stop()
        return STOPPED

    def list_workers(self) -> List[dict]:
        return [
            {
                "camera_id": str(cid),
                "status": w.status,
                "fps": round(w.fps, 1),
                "last_error": w.last_error,
            }
            for cid, w in self._workers.items()
        ]

    def get_worker(self, camera_id: uuid.UUID):
        return self._workers.get(camera_id)

    def stop_all(self) -> None:
        for camera_id in list(self._workers.keys()):
            try:
                self.stop_worker(camera_id)
            except Exception as exc:
                logger.warning("Error stopping worker %s: %s", camera_id, exc)


# Module-level singleton
camera_manager = CameraManager()
