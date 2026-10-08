# Debugging guide (first run)
The code was never executed end-to-end by its author tooling. Work through these stages **in order**; do not move on until a stage is green. When something fails, copy the *last 15 lines* of the traceback.

## Stage 0 — Python without Activate/pip.exe (Windows policy problems)
Always call `.venv\Scripts\python.exe -m ...` instead of activating. Check: `.venv\Scripts\python.exe --version`.

## Stage 1 — Dependencies
```
.venv\Scripts\python.exe scripts\setup.py
```
`[MISSING] x` → `.venv\Scripts\python.exe -m pip install x`. `fitz` = package **PyMuPDF**. If PySide6/torch fail to install, check Python is 3.11/3.12 (64-bit).

## Stage 2 — Pure logic tests (no DB)
`.venv\Scripts\python.exe -m unittest server.tests.test_domain -v` → expect 21 OK.

## Stage 3 — Automated API tests (SQLite, no MySQL)
`.venv\Scripts\python.exe -m pytest server/tests -x -vv`  (`-x` stops at first failure).
| Symptom | Likely cause / fix |
|---|---|
| `ImportError` at collection | missing package (Stage 1) or running outside the repo root |
| `sqlalchemy.exc.*` mapper errors | model typo — read the column named in the message (`server/app/models.py`) |
| 500 in a test | run only that test with `-x -vv -s`; the server logs the traceback (`drass.app` logger) |
| 422 where 200 expected | print `r.json()` — `fields` names the bad input |
| TC-06 fails on ranking | the test uses a toy hash embedder; check `semantic_threshold` was lowered in the test, then run `server/tests/test_real_model.py` with the real model |
| reader/upload tests skipped | PyMuPDF not installed |
Run a single test: `pytest server/tests/test_api.py::test_tc03_approval_chain_and_history -x -vv -s`.

## Stage 4 — MySQL connection
1. `mysql -u drass_user -p drass -e "select 1"` works? If not, fix user/password/grants.
2. `.venv\Scripts\python.exe scripts\setup_db.py --demo`
   - `Can't connect to MySQL server` → service stopped / wrong host/port in `.env`.
   - `Access denied` → password in `.env` ≠ MySQL user's password. Special characters are URL-encoded automatically.
   - `Unknown database` → `CREATE DATABASE drass ...`
   - `cryptography` error with `caching_sha2_password` → `pip install cryptography`.
3. Verify: `mysql ... -e "select username, role_id from users"` shows 10 users.

## Stage 5 — Server
`run_server.bat` → open `http://127.0.0.1:8000/health` (expect `{"status":"ok"}`) and `/docs` (try *POST /auth/login* with `student1` / `Drass#2026demo`; copy the token into *Authorize*).
- Address in use → another process on 8000; change `API_PORT`/`--port` and the client's `DRASS_SERVER_URL`.
- `EmbeddingUnavailable` / "model folder not found" → Stage 6.
- From another PC: open Windows Firewall inbound TCP 8000; use the server's LAN IP.

## Stage 6 — Embedding model
Folder `models/sentence-transformer-model` must contain `config.json` and `modules.json` etc. Re-download (README step 3). Then `scripts\rebuild_embeddings.py all`. Admin → *Indexing Monitor* should show Indexed = Archived.
Offline machine? Copy the folder from an online machine.

## Stage 7 — Client
`run_client.bat`. Start the server first. Login window → **Server** field must be the server URL.
- "Cannot reach the DRASS server" → Stage 5 (server/firewall/URL).
- Window never appears / Qt plugin error → reinstall PySide6; run `python client/main.py` in a terminal to see the traceback.
- A button does nothing → errors are shown in dialogs; also run the client from a terminal to read exceptions printed by Qt slots.
- Blank reader page → server needs PyMuPDF; check server log for `StorageError`.
- Session expired right after login → PC clock differs? Server and DB use UTC; check `idle_timeout_minutes` in Settings.

## Stage 8 — Walk the demo scenario
`docs/DEMO_ACCOUNTS.md`. For each step that fails, check **Admin → Audit Logs** (what the server recorded) and the server console (traceback).

## Useful commands
- Reset a dev database: `mysql -e "DROP DATABASE drass; CREATE DATABASE drass CHARACTER SET utf8mb4"` then `scripts\setup_db.py --demo`.
- Rebuild search index: `scripts\rebuild_embeddings.py all`.
- Verbose server logging: edit `level=logging.INFO` → `DEBUG` in `server/app/main.py`.
- Tell me the stage, the command, and the last 15 traceback lines and I can fix it quickly.
