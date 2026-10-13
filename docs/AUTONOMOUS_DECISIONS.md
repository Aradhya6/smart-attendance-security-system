# AUTONOMOUS_DECISIONS.md

Decisions made autonomously during the Phases 10–19 run.

| Phase | Decision | Reason | Impact |
|---|---|---|---|
| ENV | Use `INSIGHTFACE_MODEL_NAME=buffalo_s` (from .env.example) instead of `INSIGHTFACE_MODEL=buffalo_l` (from PLAYBOOK) | .env.example and README specify `buffalo_s`; it produces the same 512-d ArcFace embeddings but is faster on CPU. Config key kept as `insightface_model_name` matching .env.example. Both models produce 512-d embeddings. | buffalo_s loads faster; performance may differ on real faces — NOT VERIFIED. |
| ENV | DB uses `smart_attendance` database (from docker-compose.yml and .env.example) rather than `sas_db` (PLAYBOOK reference) | .env.example defines `POSTGRES_DB=smart_attendance`; docker container is already running with this name. No changes to credentials. | Consistent with existing setup |
| ENV | RECOGNITION_THRESHOLD default set to 0.50 (matching .env.example `FACE_MATCH_THRESHOLD`) rather than 0.45 (PLAYBOOK default) | .env.example uses `FACE_MATCH_THRESHOLD=0.50`. Config aliased to both names for compatibility. | Higher threshold means fewer false positives; must be calibrated by human |
| ENV | No Redis started or required | Playbook says Redis is NOT needed for phases 10–19 scope | Correct: Redis deferred to Phase 29 |
| 10 | Model loaded with `allowed_modules=['detection']` for Phase 10 detector, then extended to `['detection','recognition']` in Phase 11 | Follows playbook architecture: detection-only first, recognition added in Phase 11 | ModelRegistry supports both modes |
| 10 | Use `buffalo_s` model pack (env var `INSIGHTFACE_MODEL_NAME`) — both `buffalo_s` and `buffalo_l` supported at runtime via env | Follows .env.example | Agent logs `INSIGHTFACE_MODEL_NAME` on startup |
| 15 | `attendance_sessions` table migration added (Phase 15, ADR-08 extension) | Playbook requires attendance_sessions for session finalize/absent flow | One small reversible Alembic migration |
| ALL | Tests use mocked models and cameras for deterministic CI | No webcam and no model weights in agent environment | Real-model tests marked NOT VERIFIED; skip with clear message if fixtures absent |
