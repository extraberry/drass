"""Anonymous visitor: behaves like an EXTERNAL_USER who is not logged in (ARCHIVED records only, no reader)."""
from types import SimpleNamespace


class GuestUser:
    user_id = None
    username = "guest"
    full_name = "Guest"
    status = "ACTIVE"
    role = SimpleNamespace(role_name="EXTERNAL_USER")


GUEST = GuestUser()
