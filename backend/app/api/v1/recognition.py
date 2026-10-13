"""
Recognition API — Phase 13 + 14 (sync version).
POST /recognition/identify       — single-image identification (ADMIN)
POST /recognition/workers/{id}/start
POST /recognition/workers/{id}/stop
GET  /recognition/workers
"""
from __future__ import annotations
import uuid
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.core.deps import get_db, require_role
from backend.app.models.user import User
from backend.app.schemas.recognition import FaceResultSchema, IdentifyResponse, WorkerStateSchema

router = APIRouter(prefix="/recognition", tags=["recognition"])


@router.post("/identify", response_model=IdentifyResponse)
def identify_image(
    file: UploadFile = File(..., description="JPEG/PNG image ≤5 MB"),
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    """Identify face(s) in an uploaded image. Embeddings never returned."""
    from backend.app.vision.image_io import safe_decode_upload
    from backend.app.vision.pipeline import VisionPipeline
    from backend.app.vision.model_registry import ModelRegistry
    from backend.app.core.config import get_settings
    from backend.app.db.session import SessionLocal
    import asyncio

    raw_bytes = asyncio.get_event_loop().run_until_complete(file.read()) if False else file.file.read()
    result = safe_decode_upload(raw_bytes)
    if not result.ok:
        raise HTTPException(status_code=422, detail=f"Image rejected: {result.reason}")
    if result.image is None:
        raise HTTPException(status_code=422, detail="Image could not be decoded")

    settings = get_settings()
    pipeline = VisionPipeline(
        db_session_factory=SessionLocal,
        threshold=settings.recognition_threshold,
        margin=settings.recognition_margin,
        top_k=settings.top_k,
        registry=ModelRegistry.instance(),
    )
    faces = pipeline.process(result.image)
    return IdentifyResponse(faces=[
        FaceResultSchema(
            recognized=f.recognized, kind=f.kind,
            student_id=f.student_id, name=f.name,
            similarity=round(f.similarity, 4), bbox=f.bbox,
        ) for f in faces
    ])


@router.post("/workers/{camera_id}/start", status_code=200)
def start_worker(
    camera_id: uuid.UUID,
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    from backend.app.cameras.manager import camera_manager
    try:
        state = camera_manager.start_worker(camera_id, db)
        return {"camera_id": str(camera_id), "status": state}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/workers/{camera_id}/stop", status_code=200)
def stop_worker(
    camera_id: uuid.UUID,
    current_user: User = Depends(require_role("ADMIN")),
):
    from backend.app.cameras.manager import camera_manager
    state = camera_manager.stop_worker(camera_id)
    return {"camera_id": str(camera_id), "status": state}


@router.get("/workers", response_model=List[WorkerStateSchema])
def list_workers(
    current_user: User = Depends(require_role("ADMIN", "OPERATOR")),
):
    from backend.app.cameras.manager import camera_manager
    return camera_manager.list_workers()
