"""Create an administrator. Usage: python scripts/create_admin.py <username> <full name> <email>   (password prompted)"""
import getpass, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server.app.db import SessionLocal
from server.app.models import User
from server.app.services import admin_service

if len(sys.argv) != 4:
    sys.exit(__doc__)
pw = getpass.getpass("Password: ")
with SessionLocal() as db:
    actor = db.query(User).filter(User.role.has(role_name="ADMIN")).first() or User(user_id=0)
    admin_service.create_user(db, actor, {"username": sys.argv[1], "password": pw, "role": "ADMIN", "full_name": sys.argv[2], "email": sys.argv[3]})
print("Administrator created.")
