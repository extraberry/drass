"""Pure login/session/password rules; hashing itself (bcrypt) lives in the auth service."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

GENERIC_AUTH_ERROR = "Invalid username or password."


@dataclass
class AuthPolicy:
    min_password_length: int = 8
    failed_login_limit: int = 5
    lockout_minutes: int = 15
    idle_timeout_minutes: int = 20


def password_problems(pw: str, policy: AuthPolicy) -> list[str]:
    return [] if len(pw or "") >= policy.min_password_length else \
        [f"Password must be at least {policy.min_password_length} characters."]


def is_locked(locked_until: Optional[datetime], now: datetime) -> bool:
    return locked_until is not None and now < locked_until


def register_failure(count: int, now: datetime, policy: AuthPolicy):
    """Return (new_count, locked_until). Count resets when a lockout is applied."""
    count += 1
    if count >= policy.failed_login_limit:
        return 0, now + timedelta(minutes=policy.lockout_minutes)
    return count, None


def session_valid(last_activity: datetime, revoked_at: Optional[datetime],
                  now: datetime, policy: AuthPolicy) -> bool:
    if revoked_at is not None:
        return False
    return now - last_activity <= timedelta(minutes=policy.idle_timeout_minutes)
