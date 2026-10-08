"""Back up the database to BACKUP_DIR. MySQL uses mysqldump (must be on PATH); SQLite copies the file."""
import datetime, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server.app.core.config import get_settings

s = get_settings(); s.backup_dir.mkdir(parents=True, exist_ok=True)
stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
if s.database_url.startswith("sqlite"):
    src = s.database_url.replace("sqlite:///", ""); dst = s.backup_dir / f"drass_{stamp}.db"; shutil.copy(src, dst)
else:
    from sqlalchemy.engine import make_url
    u = make_url(s.database_url); dst = s.backup_dir / f"drass_{stamp}.sql"
    env = {**os.environ, "MYSQL_PWD": u.password or ""}          # keeps the password off the command line
    with open(dst, "wb") as f:
        r = subprocess.run(["mysqldump", "-h", u.host or "127.0.0.1", "-P", str(u.port or 3306), "-u", u.username, "--single-transaction", u.database], stdout=f, env=env)
    if r.returncode != 0:
        dst.unlink(missing_ok=True); sys.exit("mysqldump failed. Is it installed and on PATH?")
print(f"Backup written: {dst}\nCopy backups to a separate machine/drive — the institution is responsible for off-machine storage.")
