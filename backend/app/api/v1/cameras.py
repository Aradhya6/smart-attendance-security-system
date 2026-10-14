"""
Cameras API — list and query registered cameras from PostgreSQL.
"""
from __future__ import annotations
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.deps import get_db, require_role
from backend.app.models.camera import Camera
from backend.app.models.user import User

router = APIRouter(prefix="/cameras", tags=["cameras"])


class CameraResponse(BaseModel):
    id: str = Field(..., description="Camera UUID string")
    name: str = Field(..., description="Camera human-readable name")
    location: str = Field(..., description="Physical or logical location")
    source_type: str = Field(..., description="WEBCAM | RTSP | VIDEO_FILE")
    source_url: Optional[str] = Field(None, description="Device index or stream URL")
    enabled: bool = Field(True, description="Whether camera is active")
    status: str = Field("ONLINE", description="Camera health status")


@router.get("", response_model=List[CameraResponse])
def list_cameras(
    current_user: User = Depends(require_role("ADMIN", "OPERATOR")),
    db: Session = Depends(get_db),
) -> List[CameraResponse]:
    """Fetch registered cameras from PostgreSQL; seed Laptop Webcam if empty."""
    cameras = db.query(Camera).order_by(Camera.name).all()
    if not cameras:
        default_cam = Camera(
            id=uuid.UUID("4498d160-0483-47b3-92b1-8c6dc97f8100"),
            name="Laptop Webcam",
            location="Built-in / Local",
            source_type="WEBCAM",
            source_url="0",
            enabled=True,
            status="ONLINE",
        )
        db.add(default_cam)
        db.commit()
        cameras = [default_cam]

    return [
        CameraResponse(
            id=str(c.id),
            name=c.name,
            location=c.location,
            source_type=c.source_type,
            source_url=c.source_url,
            enabled=c.enabled,
            status=c.status,
        )
        for c in cameras
    ]
