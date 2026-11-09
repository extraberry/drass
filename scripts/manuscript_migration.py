"""Database migration to the capstone manuscript (Chapter 3): five roles, signatory-verification workflow, publication status.

Pure SQL over a tiny adapter (execute / has_column), so it runs on MySQL through SQLAlchemy and is unit-tested on SQLite.
Idempotent: running it again changes nothing.  Used by scripts/align_database_to_manuscript.py."""
ROLE_DESC = {
    "STUDENT": "Submits the final PDF and metadata, tracks status and remarks, and searches and reads accessible research",
    "FACULTY": "Advisers, panelists and deans: search, filter and read accessible research (they sign approval sheets outside the system)",
    "LIBRARY_STAFF": "Manages research records, metadata and publication status; the Head Librarian also verifies signatories and gives the final archival approval",
    "ADMIN": "Manages accounts, roles, settings, backup and recovery, and activity records",
    "EXTERNAL_USER": "Searches and views research permitted by its publication status",
}
# role rows that no longer exist -> the role their users move to
RETIRED_ROLES = {"ADVISER": "FACULTY", "PANELIST": "FACULTY", "DEAN": "FACULTY", "HEAD_LIBRARIAN": "LIBRARY_STAFF"}
STATUS_MAP = {
    "SUBMITTED": "PENDING_VERIFICATION", "UNDER_ADVISER_REVIEW": "PENDING_VERIFICATION",
    "UNDER_HEAD_LIBRARIAN_REVIEW": "PENDING_VERIFICATION", "UNDER_PANEL_REVIEW": "PENDING_VERIFICATION",
    "UNDER_DEAN_REVIEW": "PENDING_VERIFICATION",
    "RETURNED_FOR_REVISION": "RETURNED", "REJECTED": "RETURNED",
}
NEW_COLUMNS = [  # table, column, DDL
    ("users", "is_head_librarian", "BOOLEAN NOT NULL DEFAULT 0"),
    ("research_works", "dean_id", "INTEGER NULL"),
    ("research_works", "publication_status", "VARCHAR(20) NULL"),
    ("research_works", "archived_by", "INTEGER NULL"),
]
NEW_INDEXES = [
    "CREATE INDEX ix_research_works_dean_id ON research_works (dean_id)",
    "CREATE INDEX ix_research_works_publication_status ON research_works (publication_status)",
]


def _q(text: str) -> str:
    return text.replace("'", "''")


def _in(values) -> str:
    return ", ".join("'" + _q(v) + "'" for v in values)


def migrate(a, log=print) -> dict:
    """`a` needs: execute(sql) -> list of row tuples, has_column(table, column) -> bool, try_execute(sql)."""
    summary = {"columns_added": 0, "users_moved": 0, "head_librarians": 0, "works_migrated": 0, "roles_removed": 0}

    # 1. new columns on existing tables
    for table, col, ddl in NEW_COLUMNS:
        if not a.has_column(table, col):
            a.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            summary["columns_added"] += 1
            log(f"  added {table}.{col}")
    if summary["columns_added"]:
        for sql in NEW_INDEXES:
            a.try_execute(sql)

    # 2. the five roles
    roles = {name: rid for rid, name in a.execute("SELECT role_id, role_name FROM roles")}
    for name, desc in ROLE_DESC.items():
        if name not in roles:
            a.execute(f"INSERT INTO roles (role_name, description) VALUES ('{name}', '{_q(desc)}')")
            log(f"  created role {name}")
        else:
            a.execute(f"UPDATE roles SET description = '{_q(desc)}' WHERE role_name = '{name}'")
    roles = {name: rid for rid, name in a.execute("SELECT role_id, role_name FROM roles")}

    # 3. move users of retired roles; the old Head Librarians become Library Staff with the Head Librarian designation
    for old, new in RETIRED_ROLES.items():
        if old not in roles:
            continue
        n = a.execute(f"SELECT COUNT(*) FROM users WHERE role_id = {roles[old]}")[0][0]
        if n:
            flag = ", is_head_librarian = 1" if old == "HEAD_LIBRARIAN" else ""
            a.execute(f"UPDATE users SET role_id = {roles[new]}{flag} WHERE role_id = {roles[old]}")
            summary["users_moved"] += n
            log(f"  moved {n} user(s) from {old} to {new}" + (" (designated Head Librarian)" if old == "HEAD_LIBRARIAN" else ""))
        a.execute(f"DELETE FROM roles WHERE role_id = {roles[old]}")
        summary["roles_removed"] += 1
        log(f"  removed role {old}")
    # a Head Librarian flag only makes sense for Library Staff
    a.execute(f"UPDATE users SET is_head_librarian = 0 WHERE role_id <> {roles['LIBRARY_STAFF']} AND is_head_librarian <> 0")

    # 4. old workflow statuses -> Pending Verification / Returned (history keeps one row per migrated work)
    old_names = list(STATUS_MAP)
    for col in ("from_status", "to_status"):
        for new in ("PENDING_VERIFICATION", "RETURNED"):
            olds = [k for k, v in STATUS_MAP.items() if v == new]
            a.execute(f"UPDATE status_history SET {col} = '{new}' WHERE {col} IN ({_in(olds)})")
    for wid, old in a.execute(f"SELECT work_id, current_status FROM research_works WHERE current_status IN ({_in(old_names)})"):
        new = STATUS_MAP[old]
        a.execute(f"UPDATE research_works SET current_status = '{new}' WHERE work_id = {wid}")
        a.execute("INSERT INTO status_history (work_id, from_status, to_status, actor_user_id, reason, created_at) VALUES "
                  f"({wid}, '{old}', '{new}', NULL, 'Migrated to the manuscript workflow (signatory verification by the Head Librarian)', CURRENT_TIMESTAMP)")
        summary["works_migrated"] += 1
    if summary["works_migrated"]:
        log(f"  moved {summary['works_migrated']} research record(s) to the Pending Verification / Returned statuses")

    # 5. archived research needs a publication status (FR10); existing archived research stays visible as before
    a.execute("UPDATE research_works SET publication_status = 'PUBLIC' WHERE current_status = 'ARCHIVED' AND publication_status IS NULL")

    # 6. record the migration
    a.execute("INSERT INTO audit_logs (user_id, action, target_type, target_id, result, details, timestamp) VALUES "
              f"(NULL, 'DB_MIGRATED_TO_MANUSCRIPT', 'system', NULL, 'SUCCESS', '{_q(str(summary))}', CURRENT_TIMESTAMP)")
    summary["head_librarians"] = a.execute(
        f"SELECT COUNT(*) FROM users WHERE is_head_librarian = 1 AND status = 'ACTIVE' AND role_id = {roles['LIBRARY_STAFF']}")[0][0]
    return summary
