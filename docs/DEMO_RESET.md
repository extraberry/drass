# Resetting DRASS before a demonstration

Use this whenever you want the system back to a clean, known state (no leftover test submissions, numbering restarts at 00001).

## Steps (Windows)
1. Close the server window (and any open DRASS clients).
2. Double-click **`scripts\reset_demo.bat`** in the project folder.
3. Choose:
   - **1 - with sample research**: the archive already contains the sample studies, so search, recommendations and the reader work straight away.
   - **2 - empty**: the archive has no research; you submit, verify and archive one live (student1 -> headlibrarian), which is the full workflow demo.
4. Type `RESET` when asked.
5. Start the server again (`run_server.bat`), wait for the server window to say *Embedding model ready*, then open the client.

Command-line equivalent: `.venv\Scripts\python.exe scripts\reset_demo.py [--empty] [--yes]`.

## What it does
- Empties **every** table (users, research, files list, history, logs, sessions, settings) and restarts the numbering.
- Deletes the stored research files (the `storage` folder: manuscripts, companions, temp).
- Re-creates the five roles, departments and courses, the demo accounts (`docs/DEMO_ACCOUNTS.md`, password `Drass2026`), the student roster, and (option 1) the sample archived research with its search index.
- Does **not** touch the database server itself, `.env`, the backups folder or the embedding model.

## Cautions
- **It deletes everything.** Never run it on a database holding real student research. Run `scripts\backup_now.bat` first if there is anything you might want back.
- Everyone is signed out (sessions are removed): sign in again on each client.
- Option 1 re-indexes the sample research, so it takes a little while the first time because the search model must load.
- Before the demo, do one search to check it works, and keep the server running so the model stays loaded.

## Quick demo checklist
- [ ] Reset (option 1 or 2) and restart the server
- [ ] Wait for *Embedding model ready* in the server window
- [ ] Sign in as `student1` once to confirm the client reaches the server
- [ ] Run one search, e.g. "research projects that use technology to improve student learning"
