"""Environment-driven configuration. Reads ./.env (if present) then process env."""
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[3]   # .../DRASS


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (ROOT / p).resolve()


class Settings:
    def __init__(self) -> None:
        _load_dotenv(ROOT / ".env")
        e = os.environ.get
        self.app_name = e("APP_NAME", "ResearchVault")
        self.api_host = e("API_HOST", "0.0.0.0")
        self.api_port = int(e("API_PORT", "8000"))
        self.enable_docs = e("ENABLE_DOCS", "true").lower() == "true"
        user, pw = e("MYSQL_USER", "drass_user"), e("MYSQL_PASSWORD", "")
        self.database_url = e("DATABASE_URL") or (
            f"mysql+pymysql://{quote_plus(user)}:{quote_plus(pw)}@{e('MYSQL_HOST', '127.0.0.1')}:"
            f"{e('MYSQL_PORT', '3306')}/{e('MYSQL_DATABASE', 'drass')}?charset=utf8mb4")
        self.storage_root = _path(e("FILE_STORAGE_ROOT", "./storage"))
        self.embedding_model_path = _path(e("EMBEDDING_MODEL_PATH", "./models/sentence-transformer-model"))
        self.embedder = e("EMBEDDER", "sentence-transformers")   # or "hash" (tests only)
        self.bcrypt_rounds = int(e("BCRYPT_ROUNDS", "12"))
        self.backup_dir = _path(e("BACKUP_DIR", "./backups"))
        self.client_server_url = e("DRASS_SERVER_URL", "http://127.0.0.1:8000")


@lru_cache
def get_settings() -> Settings:
    return Settings()
