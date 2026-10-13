"""
CameraWorker — Phase 14.

Two threads:
  reader  : grabs the latest frame from the webcam into a bounded queue (size 1).
  process : every Nth frame → VisionPipeline → Tracker → Overlay → JPEG buffer.

State machine: STOPPED → STARTING → RUNNING → ERROR | STOPPED

Worker exposes the latest annotated JPEG for MJPEG streaming.
Confirmed recognitions are published to registered observers (attendance handler).
"""
from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from typing import Callable, List, Optional

import cv2
import numpy as np

from backend.app.cameras.source import CameraSource
from backend.app.core.config import get_settings
from backend.app.vision.overlay import draw_faces
from backend.app.vision.tracker import SimpleTracker

logger = logging.getLogger(__name__)

# Worker states
STOPPED = "STOPPED"
STARTING = "STARTING"
RUNNING = "RUNNING"
ERROR = "ERROR"


class CameraWorker:
    """
    Reads camera frames in a background thread and runs recognition.

    Parameters
    ----------
    camera_id : uuid.UUID
        Database camera ID (used for audit / attendance).
    source : CameraSource
        Webcam or video source.
    pipeline : VisionPipeline
        Shared recognition pipeline (model already loaded).
    on_confirmed : list[Callable]
        Callbacks called for each confirmed track tuple:
        (track_id, face_result, camera_id)
    """

    def __init__(
        self,
        camera_id: uuid.UUID,
        source: CameraSource,
        pipeline,  # VisionPipeline
        on_confirmed: Optional[List[Callable]] = None,
    ) -> None:
        self.camera_id = camera_id
        self.source = source
        self.pipeline = pipeline
        self._on_confirmed: List[Callable] = on_confirmed or []

        settings = get_settings()
        self._process_every = settings.process_every_n_frames
        self._confirm_frames = settings.confirm_frames
        self._jpeg_quality = settings.stream_jpeg_quality
        self._max_fps = settings.stream_max_fps

        self._status = STOPPED
        self._last_error: Optional[str] = None
        self._fps: float = 0.0

        self._frame_q: queue.Queue = queue.Queue(maxsize=1)
        self._jpeg_lock = threading.Lock()
        self._latest_jpeg: Optional[bytes] = None

        self._reader_thread: Optional[threading.Thread] = None
        self._process_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._tracker = SimpleTracker(confirm_frames=self._confirm_frames)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def status(self) -> str:
        return self._status

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def get_jpeg(self) -> Optional[bytes]:
        with self._jpeg_lock:
            return self._latest_jpeg

    def start(self) -> None:
        if self._status in (STARTING, RUNNING):
            raise ValueError(f"Worker for camera {self.camera_id} is already {self._status}")

        self._status = STARTING
        self._stop_event.clear()
        self._last_error = None

        if not self.source.open():
            self._status = ERROR
            self._last_error = "Failed to open camera source"
            raise RuntimeError(self._last_error)

        self._status = RUNNING
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True, name=f"cam-reader-{self.camera_id}")
        self._process_thread = threading.Thread(target=self._process_loop, daemon=True, name=f"cam-proc-{self.camera_id}")
        self._reader_thread.start()
        self._process_thread.start()
        logger.info("CameraWorker started for camera %s", self.camera_id)

    def stop(self) -> None:
        self._stop_event.set()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=5.0)
        if self._process_thread and self._process_thread.is_alive():
            self._process_thread.join(timeout=5.0)
        try:
            self.source.release()
        except Exception as exc:
            logger.warning("Error releasing source: %s", exc)
        self._status = STOPPED
        logger.info("CameraWorker stopped for camera %s", self.camera_id)

    def add_observer(self, callback: Callable) -> None:
        self._on_confirmed.append(callback)

    # ------------------------------------------------------------------
    # Threads
    # ------------------------------------------------------------------

    def _reader_loop(self) -> None:
        """Continuously read latest frame; drop old frames if queue full."""
        while not self._stop_event.is_set():
            ok, frame = self.source.read_frame()
            if not ok or frame is None:
                time.sleep(0.01)
                continue
            # Drop stale frame; put new one
            try:
                self._frame_q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._frame_q.put_nowait(frame)
            except queue.Full:
                pass

    def _process_loop(self) -> None:
        """Process every Nth frame through pipeline."""
        frame_count = 0
        min_interval = 1.0 / self._max_fps if self._max_fps > 0 else 0.0
        t_last = time.monotonic()
        fps_frames = 0
        fps_t = time.monotonic()

        while not self._stop_event.is_set():
            try:
                frame = self._frame_q.get(timeout=1.0)
            except queue.Empty:
                continue

            frame_count += 1

            if frame_count % self._process_every == 0:
                try:
                    face_results = self.pipeline.process(frame)
                    tracked = self._tracker.update(face_results)
                    annotated = draw_faces(frame.copy(), tracked)

                    # Notify confirmed tracks
                    for track_id, result, confirmed in tracked:
                        if confirmed:
                            for cb in self._on_confirmed:
                                try:
                                    cb(track_id, result, self.camera_id)
                                except Exception as exc:
                                    logger.warning("Observer error: %s", exc)

                except Exception as exc:
                    logger.warning("Pipeline error: %s", exc)
                    annotated = frame
            else:
                annotated = frame

            # Encode to JPEG
            try:
                ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality])
                if ok:
                    with self._jpeg_lock:
                        self._latest_jpeg = buf.tobytes()
            except Exception as exc:
                logger.debug("JPEG encode error: %s", exc)

            # FPS control
            now = time.monotonic()
            fps_frames += 1
            if now - fps_t >= 2.0:
                self._fps = fps_frames / (now - fps_t)
                fps_frames = 0
                fps_t = now

            elapsed = now - t_last
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            t_last = time.monotonic()
