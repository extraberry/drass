"""Seed roles/lookups/demo users; add --demo for demo research. Same as setup_db.py."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import text
from server.app.db import Base, SessionLocal, engine
from server.app import models  # noqa: F401  (register tables)
from server.app.seed import seed_core, seed_demo, seed_roster
from server.app.services import files_service

try:
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
except Exception as exc:
    sys.exit(f"Cannot connect to the database: {exc}\nCheck MYSQL_* values in .env and that MySQL is running (see docs/DEBUGGING.md).")
Base.metadata.create_all(engine)
files_service.ensure_dirs()
with SessionLocal() as db:
    seed_core(db)
    seed_roster(db)
    n = seed_demo(db) if "--demo" in sys.argv else 0
print(f"Database ready. Demo records created: {n}")
