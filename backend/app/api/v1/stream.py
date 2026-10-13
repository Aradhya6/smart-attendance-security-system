"""
MJPEG Stream endpoints — Phase 14 update.
Serves annotated frames from CameraWorker when a worker is running;
falls back to raw webcam for preview/registration.
"""
import time
import uuid as uuid_lib
from typing import Generator, Optional

import cv2
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from backend.app.cameras.webcam import WebcamSource
from backend.app.core.deps import require_role
from backend.app.models.user import User
from backend.app.schemas.face import StreamTicketRequest, StreamTicketResponse
from backend.app.services.registration_session import session_manager

router = APIRouter(tags=["stream"])

# Global preview webcam instance (used for face registration capture)
_preview_webcam: Optional[WebcamSource] = None


def get_preview_webcam(camera_index: int = 0) -> WebcamSource:
    global _preview_webcam
    if _preview_webcam is None:
        _preview_webcam = WebcamSource(camera_index=camera_index)
    return _preview_webcam


@router.post("/stream/ticket", response_model=StreamTicketResponse)
async def generate_stream_ticket(
    payload: StreamTicketRequest,
    current_user: User = Depends(require_role("ADMIN", "OPERATOR")),
) -> StreamTicketResponse:
    """Generate a single-use, 60-second ticket for camera stream access."""
    ticket = session_manager.create_stream_ticket(
        camera_id=payload.camera_id,
        user_id=str(current_user.id),
        ttl_seconds=60,
    )
    return StreamTicketResponse(ticket=ticket, camera_id=payload.camera_id, expires_in=60)


def _generate_mjpeg_raw(cam: WebcamSource) -> Generator[bytes, None, None]:
    if not cam.is_open():
        cam.open()
    try:
        while True:
            success, frame = cam.read_frame()
            if not success or frame is None:
                time.sleep(0.05)
                continue
            ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if not ret:
                continue
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            time.sleep(0.033)
    finally:
        pass


def _generate_mjpeg_worker(camera_id: uuid_lib.UUID) -> Generator[bytes, None, None]:
    """Serve annotated JPEG frames from the running CameraWorker."""
    from backend.app.cameras.manager import camera_manager
    interval = 1.0 / 15  # max 15 fps
    while True:
        worker = camera_manager.get_worker(camera_id)
        if worker is None:
            time.sleep(0.1)
            continue
        jpeg = worker.get_jpeg()
        if jpeg:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        time.sleep(interval)


@router.get("/stream/{camera_id}")
async def stream_camera(
    camera_id: str,
    ticket: str = Query(..., description="Short-lived stream ticket"),
):
    """Serve MJPEG stream. Uses annotated frames if worker is running."""
    if not session_manager.validate_stream_ticket(ticket, camera_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or mismatched stream ticket",
        )

    # Try UUID camera_id first (live recognition worker)
    try:
        cam_uuid = uuid_lib.UUID(camera_id)
        from backend.app.cameras.manager import camera_manager
        if camera_manager.get_worker(cam_uuid) is not None:
            return StreamingResponse(
                _generate_mjpeg_worker(cam_uuid),
                media_type="multipart/x-mixed-replace; boundary=frame",
            )
    except ValueError:
        pass

    # Fallback: raw webcam
    try:
        cam_idx = int(camera_id)
    except ValueError:
        cam_idx = 0

    cam = get_preview_webcam(cam_idx)
    return StreamingResponse(
        _generate_mjpeg_raw(cam),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
