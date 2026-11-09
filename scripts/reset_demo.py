"""Put DRASS back to a clean demo state: empties every table and the stored research files, then re-creates the demo accounts,
the student roster and (unless --empty) the sample archived research.  Run it before each demonstration.

    python scripts/reset_demo.py            asks you to type RESET, then resets (archive keeps the sample research)
    python scripts/reset_demo.py --empty    same, but the archive starts with NO research (submit -> verify -> archive live)
    python scripts/reset_demo.py --yes      no question (for scripts)

THIS DELETES EVERYTHING in the database and the storage folder. Never run it on real data: back up first (scripts\\backup_now.bat)."""
import os
import shutil
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import text
from server.app.core.config import get_settings
from server.app.db import Base, SessionLocal, engine
from server.app import models  # noqa: F401  (register every table)
from server.app.seed import DEMO_PASSWORD, seed_core, seed_demo, seed_roster
from server.app.services import files_service


def main() -> None:
    s = get_settings()
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:
        sys.exit(f"Cannot connect to the database: {exc}\nCheck the MYSQL_* values in .env and that MySQL is running.")
    empty = "--empty" in sys.argv
    if "--yes" not in sys.argv:
        print(f"This DELETES ALL data in database '{engine.url.database}' and every file in {s.storage_root}.")
        print("Accounts, roster and sample research are then created again." if not empty else "Accounts and roster are created again; the archive starts empty.")
        if input("Type RESET to continue: ").strip() != "RESET":
            sys.exit("Cancelled. Nothing was changed.")
    Base.metadata.create_all(engine)                       # in case a table is missing
    with engine.begin() as conn:
        is_mysql = engine.dialect.name == "mysql"
        if is_mysql:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(Base.metadata.sorted_tables):
            # TRUNCATE also restarts the numbering, so the first new submission is DRASS-<year>-00001 again
            conn.execute(text(f"TRUNCATE TABLE `{table.name}`" if is_mysql else f"DELETE FROM {table.name}"))
        if is_mysql:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    removed = 0
    for sub in ("manuscripts", "companions", "temp"):
        d = s.storage_root / sub
        if d.is_dir():
            for f in d.iterdir():
                if f.is_file():
                    f.unlink(); removed += 1
                elif f.is_dir():
                    shutil.rmtree(f, ignore_errors=True)
    files_service.ensure_dirs()
    with SessionLocal() as db:
        seed_core(db)
        seed_roster(db)
        n = 0 if empty else seed_demo(db)
    print(f"Done. Removed {removed} stored file(s). Demo research records created: {n}.")
    print(f"Accounts: admin, headlibrarian, libstaff1, faculty1, dean1, student1, student2, external1   Password: {DEMO_PASSWORD}")
    print("Restart the server (so the search index starts fresh) and sign in again on every client: all old sessions were removed.")


if __name__ == "__main__":
    main()
