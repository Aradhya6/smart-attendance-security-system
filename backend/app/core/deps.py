"""
FastAPI dependency providers.
"""
from typing import Generator
from sqlalchemy.orm import Session
from backend.app.db.session import SessionLocal
from backend.app.core.config import get_settings


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional DB session; always closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_settings_dep():
    """Provide cached settings (for use in route signatures)."""
    return get_settings()
