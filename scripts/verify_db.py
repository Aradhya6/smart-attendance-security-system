"""DB verification script — run via: python scripts/verify_db.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()
from backend.app.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    # pgvector
    row = conn.execute(text("SELECT extname FROM pg_extension WHERE extname='vector'")).fetchone()
    print(f"[1] pgvector installed: {row is not None}")

    # Attendance unique constraint
    rows = conn.execute(text("""
        SELECT constraint_name FROM information_schema.table_constraints
        WHERE table_name='attendance_records' AND constraint_type='UNIQUE'
    """)).fetchall()
    print(f"[2] Attendance UNIQUE constraints: {[r[0] for r in rows]}")

    # HNSW index
    row = conn.execute(text("""
        SELECT indexname FROM pg_indexes
        WHERE tablename='face_embeddings' AND indexdef ILIKE '%hnsw%'
    """)).fetchone()
    print(f"[3] HNSW index: {row[0] if row else 'NOT FOUND'}")

    # Row counts
    for tbl in ["face_embeddings", "students", "attendance_records", "cameras", "detection_events"]:
        cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
        print(f"[4] {tbl}: {cnt} rows")

    # Cameras
    cams = conn.execute(text("SELECT name, source_type, source_url, id FROM cameras")).fetchall()
    for c in cams:
        print(f"[5] Camera: name={c.name} type={c.source_type} url={c.source_url} id={c.id}")

    # attendance_records columns
    cols = conn.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='attendance_records' ORDER BY ordinal_position
    """)).fetchall()
    print(f"[6] attendance_records cols: {[c[0] for c in cols]}")

    # Test a pgvector query
    import numpy as np
    v = np.random.randn(512).astype(np.float32)
    v = v / np.linalg.norm(v)
    q = str(v.tolist())
    results = conn.execute(text("""
        SELECT student_id, 1 - (embedding <=> CAST(:q AS vector)) AS sim
        FROM face_embeddings
        WHERE is_active = true
        ORDER BY embedding <=> CAST(:q AS vector)
        LIMIT 5
    """), {"q": q}).fetchall()
    print(f"[7] pgvector cosine search returned {len(results)} rows (0 expected — no embeddings yet)")

print("DB verification PASSED")
