"""
Pytest configuration and shared fixtures for backend tests.
Uses dedicated test database (sas_test) to protect dev data.
"""
import os
import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from backend.app.db.base import Base
import backend.app.models  # noqa: F401

load_dotenv()

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/sas_test"
)

# Ensure psycopg is used for sync test engine
if "+asyncpg" in TEST_DATABASE_URL:
    TEST_DATABASE_URL = TEST_DATABASE_URL.replace("+asyncpg", "+psycopg")

test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure vector extension and schema exist on sas_test."""
    with test_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    # Create tables if not already created by Alembic
    Base.metadata.create_all(bind=test_engine)
    yield
    # Keep schema intact


@pytest.fixture
def db_session() -> Session:
    """
    Yields a database session wrapped in a transaction that rolls back
    at the end of each test to guarantee complete test isolation.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()
