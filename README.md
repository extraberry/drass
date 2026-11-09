<<<<<<< HEAD
# DRASS — Digital Research Archiving System with Semantic Search
*(Earlier builds were branded "ResearchVault"; the name is now DRASS everywhere. Internal names such as the `drass` database, `drass_user` and the project folder are unchanged.)*
**Mary the Queen College of Quezon City, Inc.** — desktop research archive for newly submitted theses and capstone projects.
=======
# Digital Research Archiving System with Semantic Search
*(formerly "DRASS"; internal names such as the `drass` database, `drass_user` and the project folder are unchanged on purpose.)* desktop research archive for newly submitted theses and capstone projects.
>>>>>>> b9eea4f8b2e0b5a622885bbc51c40deba792c754

> **Status:** all code in this repository was written without being able to install the dependencies or run MySQL in the authoring sandbox.
> Only the pure-Python tests (`server/tests/test_domain.py`, 43 tests, and `server/tests/test_migration.py`, 9 tests) were executed there. The API, database layer, client and
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
One server PC (FastAPI + MySQL + storage + model), many clients over LAN with `DRASS_SERVER_URL=http://<server-ip>:8000`. Open TCP 8000 on the server's firewall for the LAN only. Set `ENABLE_DOCS=false`. Backups: `scripts\backup_now.bat` (database + research files + manifest; schedule it with Task Scheduler) and *Administrator -> Backup & Recovery* — the institution is responsible for storage, backups, power and infrastructure. No data leaves the campus; no external API is used.

## Integration API
After copying the update, run `.venv\Scripts\python.exe scripts\setup_db.py` once (creates the `api_keys` table; no ALTER needed). Admin: *Integrations (API keys)*. Details: `docs/INTEGRATION.md`.

## Roles and workflow (aligned with the Chapter 3 manuscript)
Roles: STUDENT, FACULTY, LIBRARY_STAFF, ADMIN, EXTERNAL_USER (visitors without an account act as guests). The **Head Librarian** is a Library Staff account designated by the Administrator (*Users -> Head Librarian*). 
Workflow: the Student submits one final PDF (manuscript + signed approval sheet) with title, abstract, keywords, authors, year, course, department, adviser and dean -> **Pending Verification** -> the Head Librarian ticks the signatory checklist (Adviser, Panelists, Dean, Researchers, sheet complete): incomplete -> **Returned** with remarks (the student resubmits); complete -> **Archived** with a publication status (Public / Restricted / Unpublished) and indexing for semantic search. Signatures are collected outside the system.
The Administrator manages users, roles, settings, reports, logs, indexing, backup and restoration, and cannot search or read research. Library Staff maintain metadata and publication status. Full details: `docs/WORKFLOWS.md`, `docs/MANUSCRIPT_ALIGNMENT.md`.

## Upgrading an existing database to the manuscript version
1. Stop the server and make a backup: `scripts\backup_now.bat`.
2. Copy the new files over the project (keep `.env`, `.venv`, `storage`, `models`).
3. Double-click `scripts\update_database.bat` (backup, then `align_database_to_manuscript.py` - type YES - then re-indexing). It adds the new columns and table, maps the old roles and statuses, and sets archived research to Public.
4. In *Administrator -> Users* make sure one Library Staff account has *Head Librarian* ticked (former Head Librarians are set automatically).
5. Start the server and the client; run `.venv\Scripts\python.exe -m pytest`.

## Upload limits
Research document (PDF) 100 MB, source code (.zip/.7z/.rar) 500 MB, video (.mp4/.mov/.webm) 500 MB, other supporting files 500 MB. The limits are written next to each upload button in the submission form; ADMIN can change them in *System Settings*.

## Backup and restoration
See `docs/BACKUP_AND_SYNC.md` (backup sets, restoration and the Task Scheduler setup).

## Change log
All changes by round: `docs/CHANGELOG.md`.
