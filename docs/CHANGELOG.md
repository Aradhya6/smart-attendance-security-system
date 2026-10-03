# CHANGELOG

## [Phase 1] - 2026-10-02
### Added
- Completed Phase 1 Architecture Finalization.
- Created repository architecture blueprints in `docs/architecture/`:
  - `ARCHITECTURE.md`: High-level system context, modular monolith structure, process model, and risk mitigations.
  - `DECISIONS.md`: Formal ADRs (ADR-01 through ADR-15).
  - `DATABASE.md`: PostgreSQL 16 + pgvector schema, table specifications, indices, constraints, and Mermaid ER diagram.
  - `API.md`: Comprehensive REST API catalog (/api/v1) covering health, auth, users, students, face registration, recognition, attendance, cameras, alerts, blacklist, tracking, and reports.
  - `AI_PIPELINE.md`: Shared AI Vision Engine design (InsightFace SCRFD + ArcFace `buffalo_l`), landmark alignment, quality filtering, temporal confirmation, and threshold calibration.
  - `FRONTEND.md`: Streamlit multi-page UI dashboard layout, JWT session state management, API client architecture, and visual bounding box conventions.
  - `DATA_FLOW.md`: End-to-end Mermaid sequence diagrams for frame processing, attendance marking, unknown person detection, blacklist alerts, and movement tracking.
  - `MODULE_BOUNDARIES.md`: Package layout, strict import dependency rules, and boundary enforcement guidelines.
- Updated `README.md` to link all 8 architecture blueprints.

## [Phase 2] - 2026-10-02
### Added
- Python 3.11 virtual environment configuration and CPU dependencies.
- Environment verification script `scripts/check_env.py`.
- Windows setup guide `docs/SETUP_WINDOWS.md`.

## [Phase 3] - 2026-10-02
### Added
- Docker infrastructure setup: PostgreSQL 16 + pgvector container and Redis profile.
- Extension initialization SQL `docker/postgres/init/01-extensions.sql`.

## [Phase 4] - 2026-10-02
### Added
- 11 SQLAlchemy 2.0 models with Mapped typing and constraints.
- Initial Alembic migration `0001_initial.py` with HNSW vector index and partial unique index.
- Comprehensive database schema test suite `backend/tests/db/test_schema.py` (7 tests).

## [Phase 5] - 2026-10-03
### Added
- FastAPI application factory `create_app()` in `backend/app/main.py`.
- Application configuration via `pydantic-settings` in `backend/app/core/config.py`.
- Structured JSON logging with sensitive field redaction in `backend/app/core/logging.py`.
- Uniform error handling and exception handlers without traceback leakage in `backend/app/core/errors.py`.
- Security headers middleware, Request ID middleware, and CORS configuration.
- Health check endpoints (`/api/v1/health` and `/api/v1/health/db`).
- API foundation test suite `backend/tests/api/` (10 tests).

