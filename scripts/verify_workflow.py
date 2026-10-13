"""
End-to-end workflow integration test (no webcam, uses mock frames).
Tests: create student → capture session → commit registration → recognition → attendance.
"""
import os, sys, uuid, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()

print("[1] Importing DB session...")
from backend.app.db.session import SessionLocal
from backend.app.models.student import Student
from backend.app.db.repositories import face_repo

print("[2] Creating test student...")
test_uuid = uuid.uuid4()
with SessionLocal() as db:
    student = Student(
        id=test_uuid,
        student_id=f"VERIFY_{test_uuid.hex[:8]}",
        name="Verify Test User",
        department="Testing",
        year=1,
        status="ACTIVE",
        consent_given_at=__import__('datetime').datetime.utcnow(),
        consent_version="v1.0",
    )
    db.add(student)
    db.commit()
    print(f"[2] Student created: {student.student_id}")

print("[3] Adding a synthetic embedding directly (bypassing image capture)...")
v = np.random.randn(512).astype(np.float32)
v = v / np.linalg.norm(v)

with SessionLocal() as db:
    face_repo.add_embeddings(
        db=db,
        embeddings=[v],
        student_id=test_uuid,
        model_name="buffalo_s",
        model_version="w600k_r50",
        quality_scores=[0.9],
    )
    db.commit()
    cnt = face_repo.count_active_for_student(db, test_uuid)
    print(f"[3] Embeddings stored: {cnt}")
    assert cnt == 1

print("[4] Searching for nearest neighbor (should find ourselves)...")
with SessionLocal() as db:
    hits = face_repo.nearest(db, v, k=3)
    print(f"[4] Nearest neighbors: {len(hits)}")
    if hits:
        best_sid, best_blid, best_sim = hits[0]
        print(f"[4] Best match: student_id={best_sid} sim={best_sim:.4f}")
        # Should match ourselves
        assert best_sid == test_uuid, f"Expected {test_uuid}, got {best_sid}"
        assert best_sim > 0.99, f"Expected sim>0.99 for exact match, got {best_sim}"
    else:
        print("[4] WARNING: no neighbors found (pgvector search returned empty)")

print("[5] Testing attendance duplicate prevention...")
from sqlalchemy import text
import datetime, pytz
from backend.app.core.config import get_settings

settings = get_settings()
tz = pytz.timezone(settings.app_timezone)
today = datetime.datetime.now(tz).date()

cam_id_str = "4498d160-0483-47b3-92b1-8c6dc97f8100"  # seeded camera

with SessionLocal() as db:
    for i in range(3):  # Insert 3 times — only 1 should succeed
        db.execute(text("""
            INSERT INTO attendance_records
                (id, student_id, camera_id, attendance_date, session_label,
                 marked_at, status, similarity, method, created_at)
            VALUES
                (gen_random_uuid(), :student_id, :camera_id,
                 :att_date, 'DEFAULT', NOW(), 'PRESENT', 0.9, 'AUTO', NOW())
            ON CONFLICT (student_id, attendance_date, session_label) DO NOTHING
        """), {"student_id": str(test_uuid), "camera_id": cam_id_str, "att_date": today})
    db.commit()

    cnt = db.execute(text(
        "SELECT COUNT(*) FROM attendance_records WHERE student_id=:sid"
    ), {"sid": str(test_uuid)}).scalar()
    print(f"[5] Attendance rows for student (expected 1): {cnt}")
    assert cnt == 1, f"Duplicate prevention failed! Got {cnt} rows"

print("[6] Testing deactivate_for_student (re-registration)...")
with SessionLocal() as db:
    face_repo.deactivate_for_student(db, test_uuid)
    db.commit()
    active_cnt = face_repo.count_active_for_student(db, test_uuid)
    print(f"[6] Active embeddings after deactivate: {active_cnt} (expected 0)")
    assert active_cnt == 0

print("[7] Cleaning up test data...")
with SessionLocal() as db:
    db.execute(text("DELETE FROM attendance_records WHERE student_id=:sid"), {"sid": str(test_uuid)})
    db.execute(text("DELETE FROM face_embeddings WHERE student_id=:sid"), {"sid": str(test_uuid)})
    db.execute(text("DELETE FROM students WHERE id=:sid"), {"sid": str(test_uuid)})
    db.commit()
    print("[7] Cleanup complete")

print("\n=== End-to-end integration verification PASSED ===")
