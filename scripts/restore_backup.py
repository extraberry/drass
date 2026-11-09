"""Restore a backup set made by backup_now.py (a safety backup of the current state is taken first).
Usage: python scripts/restore_backup.py            (lists backups)
       python scripts/restore_backup.py <name>     (restores it after you type RESTORE)
Stop the server before restoring."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server.app.services import backup_service


def main() -> None:
    if len(sys.argv) < 2:
        items = backup_service.list_backups()
        if not items:
            sys.exit(f"No backups in {backup_service.backup_root()}")
        for m in items:
            print(f"{m['name']:<36} {m['created_at']}  {m['file_count']} files")
        print("\nRestore with: python scripts/restore_backup.py <name>")
        return
    name = sys.argv[1]
    if input(f"This REPLACES the database and research files with backup '{name}'. Type RESTORE to continue: ").strip() != "RESTORE":
        sys.exit("Cancelled. Nothing was changed.")
    try:
        r = backup_service.restore_backup(name)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"RESTORE FAILED: {exc}")
    print(f"Restored {r['restored']} ({r['file_count']} files). Safety backup of the previous state: {r['safety_backup']}")


if __name__ == "__main__":
    main()
