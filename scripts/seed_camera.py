"""
scripts/seed_camera.py — Seed the 'Laptop Webcam' camera row if absent.

Run once after database migration:
    python scripts/seed_camera.py
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from backend.app.db.session import SessionLocal
from backend.app.models.camera import Camera


def seed_laptop_webcam() -> None:
    with SessionLocal() as db:
        existing = db.query(Camera).filter(Camera.name == "Laptop Webcam").first()
        if existing:
            print(f"[seed_camera] Laptop Webcam already exists: id={existing.id}")
            return

        cam = Camera(
            id=uuid.uuid4(),
            name="Laptop Webcam",
            location="Main Office",
            source_type="WEBCAM",
            source_url="0",
            enabled=True,
            status="UNKNOWN",
        )
        db.add(cam)
        db.commit()
        print(f"[seed_camera] Created Laptop Webcam: id={cam.id}")


if __name__ == "__main__":
    seed_laptop_webcam()
