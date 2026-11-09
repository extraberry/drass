"""Backup and restoration of the database and the research files (manuscript FR17, NFR6, Table 12 component 8).

A backup set is a folder inside BACKUP_DIR (point BACKUP_DIR at the separate backup storage: external drive or NAS):
    <BACKUP_DIR>/<YYYYmmdd-HHMMSS>-<label>/database.sql      full database dump (mysqldump for MySQL)
                                          /storage/manuscripts, /storage/companions   copies of the research files
                                          /manifest.json      checksum of the dump + file counts
Restoring first takes a safety backup of the current state, then replaces the database and the research files."""
import glob
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from sqlalchemy.engine import make_url
from ..core.config import get_settings
from ..domain.errors import NotFound, StorageError, ValidationFailed

STORAGE_DIRS = ("manuscripts", "companions")
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
LABELS = ("manual", "scheduled", "pre-restore")


def backup_root() -> Path:
    p = get_settings().backup_dir
    p.mkdir(parents=True, exist_ok=True)
    return p


def _storage_root() -> Path:
    return get_settings().storage_root


def find_mysql_tool(name: str) -> str | None:
    """`mysqldump` / `mysql`: PATH first, then MYSQLDUMP_PATH / MYSQL_PATH (.env), then the usual Windows install folders."""
    env_key = "MYSQLDUMP_PATH" if name == "mysqldump" else "MYSQL_PATH"
    found = shutil.which(name) or os.environ.get(env_key)
    if found and os.path.exists(found):
        return found
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        hits = sorted(glob.glob(os.path.join(base, "MySQL", "*", "bin", name + ".exe")) +
                      glob.glob(os.path.join(base, "MySQL", "*", "*", "bin", name + ".exe")))
        if hits:
            return hits[-1]
    return None


def _missing_tool(name: str) -> StorageError:
    return StorageError(f"{name} was not found on the server. Add MySQL's bin folder to PATH "
                        f"(e.g. C:\\Program Files\\MySQL\\MySQL Server 8.0\\bin) or set "
                        f"{'MYSQLDUMP_PATH' if name == 'mysqldump' else 'MYSQL_PATH'} in .env, then try again.")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- database dump / load ----------
def dump_database(dst: Path) -> None:
    url = make_url(get_settings().database_url)
    if url.get_backend_name() == "sqlite":
        conn = sqlite3.connect(url.database)
        try:
            with open(dst, "w", encoding="utf-8") as f:
                for line in conn.iterdump():
                    f.write(line + "\n")
        finally:
            conn.close()
        return
    exe = find_mysql_tool("mysqldump")
    if not exe:
        raise _missing_tool("mysqldump")
    env = {**os.environ, "MYSQL_PWD": url.password or ""}                 # keeps the password off the command line
    with open(dst, "wb") as f:
        r = subprocess.run([exe, "-h", url.host or "127.0.0.1", "-P", str(url.port or 3306), "-u", url.username or "",
                            "--single-transaction", "--default-character-set=utf8mb4", url.database],
                           stdout=f, stderr=subprocess.PIPE, env=env)
    if r.returncode != 0:
        raise StorageError("mysqldump failed: " + r.stderr.decode("utf-8", "replace")[:300])


def load_database(src: Path) -> None:
    from .. import db as dbmod
    url = make_url(get_settings().database_url)
    dbmod.engine.dispose()
    if url.get_backend_name() == "sqlite":
        conn = sqlite3.connect(url.database)
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            for t in tables:
                conn.execute(f'DROP TABLE IF EXISTS "{t}"')
            conn.executescript(src.read_text(encoding="utf-8"))
            conn.commit()
        finally:
            conn.close()
        return
    exe = find_mysql_tool("mysql")
    if not exe:
        raise _missing_tool("mysql")
    env = {**os.environ, "MYSQL_PWD": url.password or ""}
    with open(src, "rb") as f:
        r = subprocess.run([exe, "-h", url.host or "127.0.0.1", "-P", str(url.port or 3306), "-u", url.username or "",
                            "--default-character-set=utf8mb4", url.database], stdin=f, stderr=subprocess.PIPE, env=env)
    if r.returncode != 0:
        raise StorageError("The database could not be restored: " + r.stderr.decode("utf-8", "replace")[:300])


# ---------- research files ----------
def _copy_storage(dst_root: Path) -> tuple[int, int]:
    count = size = 0
    for sub in STORAGE_DIRS:
        src = _storage_root() / sub
        target = dst_root / sub
        target.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            continue
        for p in src.rglob("*"):
            rel = p.relative_to(src)
            if p.is_dir():
                (target / rel).mkdir(parents=True, exist_ok=True)
            elif p.name != ".gitkeep":
                (target / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target / rel)
                count += 1
                size += p.stat().st_size
    return count, size


def _restore_storage(src_root: Path) -> int:
    count = 0
    for sub in STORAGE_DIRS:
        dest = _storage_root() / sub
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        src = src_root / sub
        if src.exists():
            for p in src.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(src)
                    (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, dest / rel)
                    count += 1
    return count


# ---------- public API ----------
def create_backup(label: str = "manual") -> dict:
    if label not in LABELS:
        raise ValidationFailed("Unknown backup label.")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}-{label}"
    folder = backup_root() / name
    n = 1
    while folder.exists():                                  # two backups in the same second
        n += 1
        name = f"{stamp}-{label}-{n}"
        folder = backup_root() / name
    folder.mkdir(parents=True)
    try:
        dump = folder / "database.sql"
        dump_database(dump)
        count, size = _copy_storage(folder / "storage")
        manifest = {"name": name, "label": label, "created_at": datetime.now().isoformat(timespec="seconds"),
                    "database_sha256": _sha256(dump), "file_count": count, "storage_bytes": size,
                    "engine": make_url(get_settings().database_url).get_backend_name()}
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)           # never leave a half-written backup that looks complete
        raise
    return manifest


def list_backups() -> list[dict]:
    out = []
    for p in sorted(backup_root().iterdir(), reverse=True):
        mf = p / "manifest.json"
        if p.is_dir() and mf.exists():
            try:
                out.append(json.loads(mf.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
    return out


def restore_backup(name: str) -> dict:
    if not NAME_RE.fullmatch(name or ""):
        raise ValidationFailed("Invalid backup name.")
    folder = backup_root() / name
    mf, dump = folder / "manifest.json", folder / "database.sql"
    if not (folder.is_dir() and mf.exists() and dump.exists()):
        raise NotFound("That backup was not found.")
    manifest = json.loads(mf.read_text(encoding="utf-8"))
    if _sha256(dump) != manifest.get("database_sha256"):
        raise StorageError("The backup is damaged (database checksum mismatch). Nothing was changed.")
    safety = create_backup(label="pre-restore")              # a way back if the restored data is not the wanted one
    load_database(dump)
    files = _restore_storage(folder / "storage")
    return {"restored": name, "safety_backup": safety["name"], "file_count": files}
