# Architecture
Desktop client (PySide6, `client/`) → HTTP → FastAPI (`server/app/api`) → services (`server/app/services`) → MySQL / `storage/` / local embedding model.
- `domain/`: pure rules (workflow state machine, RBAC matrix, duplicate key, file validation, auth rules, search maths) — no framework imports; unit-tested.
- `services/`: transactions, audit, notifications; routes only parse input and call services.
- `core/deps.py`: `current_user` (session check) and `require(permission)` (RBAC + PERMISSION_DENIED audit) used by every protected route.
- Long work (uploads, search, reports, reader pages) runs in client worker threads (`client/app/worker.py`); reindexing runs as a server background task with progress.
