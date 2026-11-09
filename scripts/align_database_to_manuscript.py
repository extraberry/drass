"""Bring an EXISTING DRASS database in line with the capstone manuscript (Chapter 3):
   * five roles: Student, Faculty, Library Staff (Head Librarian = designated Library Staff), Administrator, External User
   * new workflow: Pending Verification -> Returned / Archived (the Head Librarian verifies the signatories)
   * dean, publication status (Public / Restricted / Unpublished) and the approving librarian on research records
Back up first (scripts\\backup_now.bat).  Usage:  python scripts/align_database_to_manuscript.py [--yes]
Safe to run twice."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sqlalchemy import inspect, text
from server.app.db import Base, engine
from server.app import models  # noqa: F401  (register the new signatory_verifications table)
from manuscript_migration import migrate


class SqlaAdapter:
    def __init__(self, conn):
        self.conn, self.insp = conn, inspect(conn)

    def execute(self, sql):
        res = self.conn.execute(text(sql))
        return [tuple(r) for r in res.fetchall()] if res.returns_rows else []

    def try_execute(self, sql):
        try:
            with self.conn.begin_nested():
                self.conn.execute(text(sql))
        except Exception:   # noqa: BLE001  (e.g. index already exists)
            pass

    def has_column(self, table, column):
        return column in {c["name"] for c in inspect(self.conn).get_columns(table)}


def main() -> None:
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:
        sys.exit(f"Cannot connect to the database: {exc}\nCheck the MYSQL_* values in .env and that MySQL is running.")
    if "--yes" not in sys.argv:
        print("This updates the database to the manuscript's roles and workflow:")
        print("  - Advisers/Panelists/Deans become FACULTY; Head Librarians become LIBRARY_STAFF (still the Head Librarian)")
        print("  - research under review becomes 'Pending Verification'; rejected or returned research becomes 'Returned'")
        print("  - archived research gets the publication status PUBLIC")
        if input("Have you made a backup? Type YES to continue: ").strip() != "YES":
            sys.exit("Cancelled. Nothing was changed.")
    Base.metadata.create_all(engine)                          # creates signatory_verifications (and any other missing table)
    with engine.begin() as conn:
        summary = migrate(SqlaAdapter(conn))
    print("Done:", summary)
    if not summary["head_librarians"]:
        print("WARNING: there is no active Head Librarian. In the app (Administrator > Users) tick 'Head Librarian' on a Library Staff account,\n"
              "         otherwise submissions will stay Pending Verification.")
    print("Next: run  scripts\\rebuild_embeddings.py all  if search results look stale.")


if __name__ == "__main__":
    main()
