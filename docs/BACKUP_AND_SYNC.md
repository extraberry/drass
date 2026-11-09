# Backing up the database and uploaded studies to a cloud folder (step by step)

The system works fully offline. This guide only makes a **safe copy** of everything in a free cloud folder
(OneDrive, Google Drive, Dropbox ...). Nothing in the system changes. It is **not** a live sync: it is a copy you make
regularly, so you can recover if the server PC breaks.

**What must be copied (both!)**
1. the **database** (accounts, study records, verifications) -> a `.sql` file
2. the **uploaded files** (PDFs, videos, source code) -> the `storage` folder

---
## Part A - One-time setup (about 5 minutes)

1. **Install the cloud app on the server PC** (OneDrive comes with Windows; or install Google Drive for desktop) and sign in.
   Make sure a normal folder syncs, e.g. `C:\Users\<you>\OneDrive`.
2. **Make a folder for the copies**, e.g. `C:\Users\<you>\OneDrive\DRASS-Backup` (or a folder on an external drive).
3. Open the project's `.env` file (in the `DRASS` folder) in Notepad and set this line to that folder, using forward slashes:
   ```
   BACKUP_DIR=C:/Users/<you>/OneDrive/DRASS-Backup
   ```
   Save the file.
4. **Check that `mysqldump` works.** Open Command Prompt and type `mysqldump --version`.
   - A version number appears -> good.
   - "not recognized" -> add MySQL's `bin` folder to PATH (usually `C:\Program Files\MySQL\MySQL Server 8.0\bin`):
     Start -> "Edit the system environment variables" -> Environment Variables -> Path -> Edit -> New -> paste the folder -> OK. Open a **new** Command Prompt and test again.

## Part B - Make a backup (manuscript FR17, NFR6)

Three ways, all producing the same **backup set** inside `BACKUP_DIR` (a folder named `YYYYMMDD-HHMMSS-manual`, `-scheduled` or `-pre-restore`):
- `database.sql` - the whole database
- `storage\manuscripts` and `storage\companions` - every research file
- `manifest.json` - date, file count and the checksum of `database.sql` (checked again before any restore)

1. **In the app (Administrator):** *Backup & Recovery -> Back up now*.
2. **By hand:** double-click `scripts\backup_now.bat`.
3. **Automatically (recommended: every day at closing time):** Start -> "Task Scheduler" -> Create Basic Task -> Daily, e.g. 6:00 PM -> Start a program ->
   Program/script: `C:\path\to\DRASS\scripts\backup_now.bat`, Add arguments: `--scheduled`, Start in: `C:\path\to\DRASS`. In the task's properties tick
   "Run whether user is logged on or not". (The server PC must be on; the same command is used for weekly full copies to a second drive.)

Keep `BACKUP_DIR` on **separate storage** (external drive or NAS; a cloud-synced folder also works). Delete very old backup folders to save space. Always back up before updating the system.

## Part C - Restore (documented procedure)

**From the app:** *Backup & Recovery* -> select a backup -> *Restore selected...* -> type `RESTORE`. The system first saves a `-pre-restore` backup of the current state, then replaces the database and the research files with the chosen set. Sign in again afterwards.
**From the command line** (server stopped): `.venv\Scripts\python.exe scripts\restore_backup.py` lists the backups; `.venv\Scripts\python.exe scripts\restore_backup.py <name>` restores one after you type `RESTORE`.
**On a new or repaired PC:** install the system as in the README (Python, MySQL, `.venv`, `.env` with the same `BACKUP_DIR`), run `scripts\setup_db.py` once, copy the backup folders into `BACKUP_DIR`, then restore the newest one with `restore_backup.py`. Start the server, open a study to confirm the file opens, and run `scripts\rebuild_embeddings.py all` if search is empty.
If `mysqldump` or `mysql` is not found, add MySQL's `bin` folder to PATH or set `MYSQLDUMP_PATH` / `MYSQL_PATH` in `.env`.

## Good to know
- The backup contains passwords (hashed) and private records: keep the cloud folder **private**, do not share it.
- A backup made at 8 AM does not contain what was submitted at 3 PM. Anything after the last backup is lost if the PC dies.
- Test a restore once on another PC before you need it. The same checksum in `manifest.json` protects against a damaged backup.
- This was not run on a real Windows PC by me, so if a step shows an error, send me the exact message.
