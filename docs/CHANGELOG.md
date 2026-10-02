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
