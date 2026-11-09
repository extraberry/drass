"""Full backup (manuscript NFR6): database dump + research files + manifest, into BACKUP_DIR.
Run by hand (scripts\\backup_now.bat) or on a schedule (Windows Task Scheduler, see docs/BACKUP_AND_SYNC.md).
Usage: python scripts/backup_now.py [--scheduled]"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server.app.services import backup_service


def main() -> None:
    label = "scheduled" if "--scheduled" in sys.argv else "manual"
    try:
        m = backup_service.create_backup(label)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"BACKUP FAILED: {exc}")
    print(f"Backup created: {backup_service.backup_root() / m['name']}")
    print(f"  files: {m['file_count']}  size: {m['storage_bytes']} bytes  database sha256: {m['database_sha256'][:16]}...")
    print("Keep BACKUP_DIR on separate storage (external drive or NAS).")


if __name__ == "__main__":
    main()
