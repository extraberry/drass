# DRASS — Digital Research Archiving System with Semantic Search
**Mary the Queen College of Quezon City, Inc.** — desktop research archive for newly submitted theses and capstone projects.

> **Status:** all code in this repository was written without being able to install the dependencies or run MySQL in the authoring sandbox.
> Only the pure-Python domain tests (`server/tests/test_domain.py`, 21 tests) were executed there. The API, database layer, client and
> integration tests have **not yet been run**. Run the checklist in `docs/DEBUGGING.md` first and expect to fix some first-run errors.
> See `docs/IMPLEMENTATION_STATUS.md` for the honest per-feature status.

## Architecture
```
[PySide6 Desktop Client] --HTTP/LAN--> [FastAPI server] --> MySQL 8 (SQLAlchemy)
                                              |--> storage/ (PDFs, companions; never exposed by URL)
                                              |--> local Sentence-Transformers model (offline)
```
The client never touches MySQL or the file system of the server. All authorization is enforced server-side (`server/app/core/deps.py`, `server/app/domain/rbac.py`).

## Prerequisites (Windows)
Python 3.11/3.12, MySQL 8.x, ~3 GB disk (PyTorch + model). Internet is needed **only** to install packages and download the model once.

## Setup
1. **MySQL** — create DB and user:
   ```sql
   CREATE DATABASE drass CHARACTER SET utf8mb4;
   CREATE USER 'drass_user'@'localhost' IDENTIFIED BY 'choose-a-password';
   GRANT ALL ON drass.* TO 'drass_user'@'localhost';
   ```
2. **Install**: `powershell -ExecutionPolicy Bypass -File .\setup.ps1` (creates `.venv`, installs requirements, copies `.env.example` → `.env`). Edit `.env` (set `MYSQL_PASSWORD`), then run `setup.ps1` again to create tables and seed demo data.
   Manual equivalent: `.venv\Scripts\python.exe -m pip install -r requirements.txt` then `.venv\Scripts\python.exe scripts\setup_db.py --demo`.
3. **Embedding model** (once, with internet):
   `.venv\Scripts\python.exe -c "from sentence_transformers import SentenceTransformer as S; S('all-MiniLM-L6-v2').save('models/sentence-transformer-model')"`
   then re-run `scripts\rebuild_embeddings.py all` if demo data was seeded before the model existed.
4. **Migrations (Alembic)**: `scripts/setup_db.py` uses `create_all` for first install. To manage schema changes with Alembic:
   `.venv\Scripts\python.exe -m alembic revision --autogenerate -m "initial"` then `.venv\Scripts\python.exe -m alembic upgrade head` (the initial revision is generated from the models — not pre-generated here because it needs a live MySQL).
5. **Run**: `run_server.bat` (then open http://127.0.0.1:8000/health), then `run_client.bat`; or `run_all.bat`.
6. **Log in** with a demo account — see `docs/DEMO_ACCOUNTS.md`.

## Tests
`.venv\Scripts\python.exe -m pytest` (uses SQLite + a test-only hash embedder; no MySQL needed). Details: `docs/TESTING.md`.

## Campus deployment
One server PC (FastAPI + MySQL + storage + model), many clients over LAN with `DRASS_SERVER_URL=http://<server-ip>:8000`. Open TCP 8000 on the server's firewall for the LAN only. Set `ENABLE_DOCS=false`. Backups: `scripts/backup_database.py` plus copying `storage/` — the institution is responsible for storage, backups, power and infrastructure. No data leaves the campus; no external API is used.
