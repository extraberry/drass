"""Manuscript migration (scripts/manuscript_migration.py) on a SQLite copy of the OLD schema. Needs only the standard library."""
import importlib.util
import os
import sqlite3
import unittest

_spec = importlib.util.spec_from_file_location(
    "manuscript_migration", os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "manuscript_migration.py"))
mm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mm)


class Sqlite3Adapter:
    def __init__(self, conn): self.conn = conn
    def execute(self, sql): return self.conn.execute(sql).fetchall()
    def try_execute(self, sql):
        try: self.conn.execute(sql)
        except sqlite3.Error: pass
    def has_column(self, table, column): return column in [r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")]


OLD_SCHEMA = """
CREATE TABLE roles (role_id INTEGER PRIMARY KEY AUTOINCREMENT, role_name TEXT UNIQUE, description TEXT);
CREATE TABLE users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, role_id INTEGER, status TEXT DEFAULT 'ACTIVE');
CREATE TABLE research_works (work_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, current_status TEXT, adviser_id INTEGER);
CREATE TABLE status_history (history_id INTEGER PRIMARY KEY AUTOINCREMENT, work_id INTEGER, from_status TEXT, to_status TEXT,
                             actor_user_id INTEGER, reason TEXT, created_at TIMESTAMP);
CREATE TABLE audit_logs (log_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, target_type TEXT, target_id TEXT,
                         result TEXT, details TEXT, timestamp TIMESTAMP);
"""


def old_db():
    c = sqlite3.connect(":memory:")
    c.executescript(OLD_SCHEMA)
    for r in ("STUDENT", "ADVISER", "HEAD_LIBRARIAN", "ADMIN", "EXTERNAL_USER", "PANELIST"):
        c.execute("INSERT INTO roles (role_name, description) VALUES (?, 'old')", (r,))
    rid = {n: i for i, n in c.execute("SELECT role_id, role_name FROM roles")}
    for u, r in (("stu", "STUDENT"), ("adv", "ADVISER"), ("head", "HEAD_LIBRARIAN"), ("adm", "ADMIN"), ("ext", "EXTERNAL_USER"), ("pan", "PANELIST")):
        c.execute("INSERT INTO users (username, role_id) VALUES (?, ?)", (u, rid[r]))
    for t, s in (("a", "DRAFT"), ("b", "SUBMITTED"), ("c", "UNDER_ADVISER_REVIEW"), ("d", "UNDER_HEAD_LIBRARIAN_REVIEW"),
                 ("e", "RETURNED_FOR_REVISION"), ("f", "REJECTED"), ("g", "ARCHIVED")):
        c.execute("INSERT INTO research_works (title, current_status) VALUES (?, ?)", (t, s))
    c.execute("INSERT INTO status_history (work_id, from_status, to_status, reason) VALUES (3, 'SUBMITTED', 'UNDER_ADVISER_REVIEW', 'x')")
    c.commit()
    return c


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.c = old_db()
        self.a = Sqlite3Adapter(self.c)
        self.s = mm.migrate(self.a, log=lambda *_: None)

    def roles(self): return {n: i for i, n in self.c.execute("SELECT role_id, role_name FROM roles")}

    def test_new_columns_exist(self):
        for table, col, _ in mm.NEW_COLUMNS: self.assertTrue(self.a.has_column(table, col), col)

    def test_exactly_the_five_manuscript_roles_remain(self):
        self.assertEqual(set(self.roles()), {"STUDENT", "FACULTY", "LIBRARY_STAFF", "ADMIN", "EXTERNAL_USER"})

    def test_users_moved_and_head_librarian_designated(self):
        r = self.roles()
        rows = {u: (role, head) for u, role, head in self.c.execute("SELECT username, role_id, is_head_librarian FROM users")}
        self.assertEqual(rows["adv"], (r["FACULTY"], 0))
        self.assertEqual(rows["pan"], (r["FACULTY"], 0))
        self.assertEqual(rows["head"], (r["LIBRARY_STAFF"], 1))
        self.assertEqual(rows["stu"], (r["STUDENT"], 0))
        self.assertEqual(self.s["head_librarians"], 1)

    def test_statuses_follow_the_manuscript_workflow(self):
        got = {t: s for t, s in self.c.execute("SELECT title, current_status FROM research_works")}
        self.assertEqual(got, {"a": "DRAFT", "b": "PENDING_VERIFICATION", "c": "PENDING_VERIFICATION", "d": "PENDING_VERIFICATION",
                               "e": "RETURNED", "f": "RETURNED", "g": "ARCHIVED"})
        self.assertEqual(self.s["works_migrated"], 5)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM status_history WHERE reason LIKE 'Migrated%'").fetchone()[0], 5)
        self.assertEqual(self.c.execute("SELECT to_status FROM status_history WHERE reason = 'x'").fetchone()[0], "PENDING_VERIFICATION")

    def test_archived_research_becomes_public(self):
        self.assertEqual(self.c.execute("SELECT publication_status FROM research_works WHERE title = 'g'").fetchone()[0], "PUBLIC")
        self.assertIsNone(self.c.execute("SELECT publication_status FROM research_works WHERE title = 'b'").fetchone()[0])

    def test_running_twice_changes_nothing_more(self):
        before = self.c.execute("SELECT COUNT(*) FROM status_history").fetchone()[0]
        s2 = mm.migrate(self.a, log=lambda *_: None)
        self.assertEqual((s2["columns_added"], s2["users_moved"], s2["works_migrated"], s2["roles_removed"]), (0, 0, 0, 0))
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM status_history").fetchone()[0], before)
        self.assertEqual(len(self.roles()), 5)

    def test_migration_is_recorded_in_the_audit_log(self):
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM audit_logs WHERE action = 'DB_MIGRATED_TO_MANUSCRIPT'").fetchone()[0], 1)


class MigrationEdgeTests(unittest.TestCase):
    def test_no_head_librarian_is_reported(self):
        c = sqlite3.connect(":memory:"); c.executescript(OLD_SCHEMA)
        for r in ("STUDENT", "ADMIN"): c.execute("INSERT INTO roles (role_name, description) VALUES (?, 'old')", (r,))
        s = mm.migrate(Sqlite3Adapter(c), log=lambda *_: None)
        self.assertEqual(s["head_librarians"], 0)

    def test_old_library_staff_role_keeps_its_users_without_head_flag(self):
        c = sqlite3.connect(":memory:"); c.executescript(OLD_SCHEMA)
        c.execute("INSERT INTO roles (role_name, description) VALUES ('LIBRARY_STAFF', 'old')")
        c.execute("INSERT INTO users (username, role_id) VALUES ('lib', 1)")
        mm.migrate(Sqlite3Adapter(c), log=lambda *_: None)
        self.assertEqual(c.execute("SELECT is_head_librarian FROM users WHERE username = 'lib'").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
