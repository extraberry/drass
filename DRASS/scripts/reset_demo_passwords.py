"""Set the password of EVERY existing account to Drass2026 and clear lockouts.
Usage:  .venv\\Scripts\\python.exe scripts\\reset_demo_passwords.py            (asks for confirmation)
        .venv\\Scripts\\python.exe scripts\\reset_demo_passwords.py --demo-only  (only the built-in demo usernames)
Needed once on an existing database: the seed only sets passwords when it first creates the accounts.
Use only for demonstration; choose real passwords before real deployment."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import select
from server.app.core.security import hash_password
from server.app.db import SessionLocal
from server.app.models import User
from server.app.seed import DEMO_PASSWORD, USERS

demo_only = "--demo-only" in sys.argv
names = {u[0] for u in USERS}
with SessionLocal() as db:
    users = [u for u in db.scalars(select(User)).all() if not demo_only or u.username in names]
    print(f"{len(users)} account(s) will get the password '{DEMO_PASSWORD}'.")
    if input("Type YES to continue: ").strip() != "YES":
        sys.exit("Cancelled.")
    h = hash_password(DEMO_PASSWORD)
    for u in users:
        u.password_hash, u.failed_login_count, u.locked_until = h, 0, None
    db.commit()
print("Done.")
