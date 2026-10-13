"""
Pydantic schemas for recognition endpoints (Phase 13).

IMPORTANT: No embedding field anywhere in these schemas.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class FaceResultSchema(BaseModel):
    """Single-face identity decision returned by /recognition/identify."""

    recognized: bool = Field(..., description="True if a match exceeds threshold")
    kind: str = Field(..., description="STUDENT | BLACKLISTED | UNKNOWN")
    student_id: Optional[str] = Field(None, description="Business student ID (e.g. '001'), not UUID")
    name: Optional[str] = Field(None, description="Student name or None for UNKNOWN")
    similarity: float = Field(..., description="Cosine similarity (0–1). NOT 'accuracy'.")
    bbox: List[int] = Field(..., description="[x1, y1, x2, y2] in pixels")

    model_config = {"json_schema_extra": {"example": {
        "recognized": True,
        "kind": "STUDENT",
        "student_id": "001",
        "name": "Alice",
        "similarity": 0.87,
        "bbox": [120, 60, 280, 220],
    }}}


class IdentifyResponse(BaseModel):
    """Response envelope for /recognition/identify."""

    faces: List[FaceResultSchema] = Field(
        default_factory=list,
        description="One entry per detected face.  Empty if no faces found.",
    )


class WorkerStateSchema(BaseModel):
    """Current state of a camera worker."""

    camera_id: str
    status: str = Field(..., description="STOPPED | STARTING | RUNNING | ERROR")
    fps: Optional[float] = None
    last_error: Optional[str] = None
