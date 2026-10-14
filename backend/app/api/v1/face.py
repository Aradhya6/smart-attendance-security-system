"""
Face registration and capture session endpoints.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.v1.stream import get_preview_webcam
from backend.app.core.config import get_settings
from backend.app.core.deps import get_db, require_role
from backend.app.models.student import Student
from backend.app.models.user import User
from backend.app.schemas.face import (
    FaceCaptureResponse,
    FaceSessionCreateRequest,
    FaceSessionResponse,
    FaceStatusResponse,
)
from backend.app.services.audit_service import create_audit_log
from backend.app.services.registration_session import session_manager

router = APIRouter(prefix="/students/{student_id}/face", tags=["face"])


@router.post("/session", response_model=FaceSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_face_session(
    student_id: uuid.UUID,
    payload: FaceSessionCreateRequest,
    camera_id: str = Query("0", description="Camera index or identifier"),
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
) -> FaceSessionResponse:
    """Initialize an in-memory face registration session. Enforces consent."""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    if not student.consent_given_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student has not granted biometric consent. Consent must be recorded prior to face capture.",
        )

    try:
        session = session_manager.create_session(
            student_uuid=student.id,
            student_id=student.student_id,
            camera_id=camera_id,
            target_samples=payload.target_samples,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return FaceSessionResponse(
        session_id=session.session_id,
        student_id=student.student_id,
        target_samples=session.target_samples,
        current_samples=len(session.frames),
        expires_in=int(session.expires_at - session.created_at),
    )


@router.post("/session/{session_id}/capture", response_model=FaceCaptureResponse)
async def capture_frame(
    student_id: uuid.UUID,
    session_id: str,
    current_user: User = Depends(require_role("ADMIN")),
) -> FaceCaptureResponse:
    """Capture a single frame from the camera and store in-memory in the session."""
    session = session_manager.get_session(session_id)
    if not session or session.student_uuid != student_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active registration session not found or expired",
        )

    try:
        cam_idx = int(session.camera_id)
    except ValueError:
        cam_idx = 0

    cam = get_preview_webcam(cam_idx)
    if not cam.is_open():
        cam.open()

    from backend.app.vision.preprocess import validate_image_quality

    success, frame = cam.read_frame()
    if not success or frame is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to capture frame from camera",
        )

    # Validate image quality (resolution, brightness, blur)
    val_res = validate_image_quality(frame)
    if not val_res.ok:
        return FaceCaptureResponse(
            accepted=False,
            current_samples=len(session.frames),
            target_samples=session.target_samples,
            reason=val_res.reason,
            quality_score=val_res.metrics.blur_score if val_res.metrics else None,
            pose_prompt=session.current_prompt(),
        )

    # Add frame in memory
    count = session.add_frame(frame)
    next_prompt = session.current_prompt()

    return FaceCaptureResponse(
        accepted=True,
        current_samples=count,
        target_samples=session.target_samples,
        quality_score=val_res.metrics.blur_score if val_res.metrics else None,
        pose_prompt=next_prompt,
    )


@router.delete("/session/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_session(
    student_id: uuid.UUID,
    session_id: str,
    current_user: User = Depends(require_role("ADMIN")),
) -> Response:
    """Cancel and clear registration session frames from memory."""
    session = session_manager.get_session(session_id)
    if session:
        session_manager.delete_session(session_id)
    # Release camera
    cam = get_preview_webcam()
    cam.release()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/status", response_model=FaceStatusResponse)
async def get_face_status(
    student_id: uuid.UUID,
    current_user: User = Depends(require_role("ADMIN", "OPERATOR")),
    db: Session = Depends(get_db),
) -> FaceStatusResponse:
    """Check face registration status for a student (never returns vectors)."""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    from backend.app.db.repositories.student_repo import StudentRepository
    repo = StudentRepository(db)
    registered, count = repo.get_face_stats(student.id)

    return FaceStatusResponse(
        registered=registered,
        sample_count=count,
        model_name="buffalo_l (ArcFace w600k_r50)",
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_face_biometrics(
    request: Request,
    student_id: uuid.UUID,
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
) -> Response:
    """Hard-delete all face embeddings for student (consent withdrawal)."""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    from backend.app.models.face_embedding import FaceEmbedding
    from sqlalchemy import delete
    db.execute(delete(FaceEmbedding).where(FaceEmbedding.student_id == student.id))
    db.commit()

    client_ip = request.client.host if request.client else "unknown"
    create_audit_log(
        db=db,
        action="FACE_DELETE",
        entity_type="STUDENT",
        actor_user_id=current_user.id,
        entity_id=student.student_id,
        ip=client_ip,
        details={"reason": "Biometric withdrawal"},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class CommitSessionRequest(BaseModel):
    session_id: str


@router.post("/commit", status_code=status.HTTP_200_OK)
async def commit_face_registration(
    student_id: uuid.UUID,
    payload: CommitSessionRequest,
    request: Request,
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
) -> dict:
    """
    Commit a completed registration session: detect → embed → consistency → store.
    Returns stored_count and rejected_count.
    Embeddings are never returned.
    """
    from backend.app.services.face_service import commit_face_registration as do_commit

    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    try:
        stored, rejected = do_commit(
            db=db,
            student_uuid=student.id,
            session_id=payload.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    client_ip = request.client.host if request.client else "unknown"
    create_audit_log(
        db=db,
        action="FACE_REGISTER",
        entity_type="STUDENT",
        actor_user_id=current_user.id,
        entity_id=student.student_id,
        ip=client_ip,
        details={"stored": stored, "rejected": rejected},
    )
    return {
        "stored_count": stored,
        "rejected_count": rejected,
        "student_id": str(student.id),
    }


@router.post("/upload", status_code=status.HTTP_200_OK)
@router.post("/upload-photo", status_code=status.HTTP_200_OK)
async def register_face_from_photo(
    student_id: uuid.UUID,
    request: Request,
    photo: Optional[UploadFile] = File(None, description="Face photo (JPEG or PNG, max 5MB)"),
    file: Optional[UploadFile] = File(None, description="Face photo alias (JPEG or PNG, max 5MB)"),
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
) -> dict:
    """
    Register a student's face from an uploaded photo.

    Workflow: validate image → detect single face → generate 512-d embedding
    → consistency check → save to PostgreSQL via existing face_repo.
    Raw image is never permanently stored.
    """
    from backend.app.vision.image_io import safe_decode_upload, MAX_UPLOAD_BYTES
    from backend.app.vision.preprocess import validate_image_quality
    from backend.app.vision.detector import detect_single_face
    from backend.app.vision.embedder import embed_face
    from backend.app.vision.model_registry import ModelRegistry
    from backend.app.vision.quality import check_consistency
    from backend.app.db.repositories import face_repo

    target_file = photo or file
    if target_file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image file provided. Please upload a photo.",
        )

    # 1. Check student exists
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    # 2. Enforce biometric consent
    if not student.consent_given_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student has not granted biometric consent. Consent must be recorded prior to face registration.",
        )

    # 3. Enforce student is ACTIVE
    if student.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is not active. Only active students can register faces.",
        )

    # 4. Validate content type (defense in depth — magic bytes checked below)
    if target_file.content_type and target_file.content_type not in (
        "image/jpeg", "image/jpg", "image/png",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {target_file.content_type}. Only JPEG and PNG are accepted.",
        )

    # 5. Read and validate file size
    raw_bytes = await target_file.read()
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image too large ({len(raw_bytes)} bytes). Maximum is {MAX_UPLOAD_BYTES} bytes (5 MB).",
        )

    # 6. Safe decode (magic bytes + cv2 decode + dimension check)
    decode_result = safe_decode_upload(raw_bytes)
    if not decode_result.ok:
        detail_map = {
            "INVALID_IMAGE": "Image is corrupted or not a valid JPEG/PNG.",
            "OVERSIZED_IMAGE": "Image file exceeds the 5 MB limit.",
            "IMAGE_DIMENSIONS_TOO_LARGE": "Image dimensions exceed 4096px.",
        }
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail_map.get(decode_result.reason, f"Image validation failed: {decode_result.reason}"),
        )
    image = decode_result.image

    # 7. Image quality validation (resolution, blur, brightness)
    quality_result = validate_image_quality(image)
    if not quality_result.ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Image quality check failed: {quality_result.reason}. Please upload a clearer, well-lit photo.",
        )

    # 8. Detect exactly one face
    face, reason = detect_single_face(image)
    if face is None:
        detail_map = {
            "NO_FACE": "No face detected in the uploaded photo. Please upload a clear face photo.",
            "MULTIPLE_FACES": "Multiple faces detected. Please upload a photo containing exactly one face.",
            "FACE_TOO_SMALL": "Face is too small in the image. Please upload a closer photo.",
        }
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail_map.get(reason, f"Face detection failed: {reason}"),
        )

    # 9. Generate embedding via existing pipeline
    registry = ModelRegistry.instance()
    embedding_result = embed_face(image, face, registry=registry)
    if embedding_result is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not generate face embedding. Please try a different photo.",
        )

    # 10. Single-embedding consistency (pass-through for 1 sample)
    accepted, rejected_indices = check_consistency([embedding_result.vector])
    if not accepted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Embedding failed consistency check. Please try a different photo.",
        )

    # 11. Save to DB via existing face_repo (deactivate old, insert new)
    settings = get_settings()
    try:
        face_repo.deactivate_for_student(db, student.id)
        face_repo.add_embeddings(
            db=db,
            embeddings=accepted,
            student_id=student.id,
            model_name=settings.insightface_model_name,
            model_version="w600k_r50",
            quality_scores=[embedding_result.quality_score],
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    # 12. Audit log
    client_ip = request.client.host if request.client else "unknown"
    create_audit_log(
        db=db,
        action="FACE_REGISTER",
        entity_type="STUDENT",
        actor_user_id=current_user.id,
        entity_id=student.student_id,
        ip=client_ip,
        details={"method": "photo_upload", "stored": len(accepted), "rejected": len(rejected_indices)},
    )

    return {
        "stored_count": len(accepted),
        "rejected_count": len(rejected_indices),
        "student_id": str(student.id),
        "method": "photo_upload",
        "quality_score": embedding_result.quality_score,
    }
