"""Pre-flight check: python scripts/setup.py  — reports what is missing before you start the server."""
import importlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ok = True
for m in ("fastapi", "uvicorn", "sqlalchemy", "pymysql", "bcrypt", "fitz", "numpy", "sentence_transformers", "PySide6", "requests"):
    try: importlib.import_module(m); print(f"[ok]   {m}")
    except Exception as e: ok = False; print(f"[MISSING] {m}: {e}")
from server.app.core.config import get_settings
s = get_settings()
print("Model folder:", s.embedding_model_path, "->", "found" if s.embedding_model_path.exists() and any(s.embedding_model_path.iterdir()) else "EMPTY (see README step 6)")
print("Database URL host:", s.database_url.split("@")[-1])
sys.exit(0 if ok else 1)
