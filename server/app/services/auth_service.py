"""Login, logout, session validation (PRD s7)."""
from datetime import timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..core.security import hash_password, hash_token, new_token, verify_password
from ..core.timeutil import utcnow
from ..domain import auth_rules as ar
from ..domain.errors import (AccountDisabled, AccountLocked, AuthFailed, SessionExpired,
                             ValidationFailed)
from ..models import SessionRecord, User
from .common import audit, auth_policy, notify_roles

ABSOLUTE_SESSION_HOURS = 12
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def login(db: Session, username: str, password: str) -> tuple[str, User]:
    now, pol = utcnow(), auth_policy(db)
    username = (username or "").strip()
    user = db.scalar(select(User).where(User.username == username)) if username else None
    if user is None:
        verify_password(password or "", _DUMMY_HASH)          # equalise timing
        audit(db, None, "LOGIN_FAILED", "user", None, "FAILED", "unknown credentials")
        db.commit()
        raise AuthFailed(ar.GENERIC_AUTH_ERROR)
    if ar.is_locked(user.locked_until, now):
        audit(db, user.user_id, "LOGIN_FAILED", "user", user.user_id, "FAILED", "account locked")
        db.commit()
        raise AccountLocked("Too many failed attempts. The account is temporarily locked. Try again later.")
    if not verify_password(password or "", user.password_hash):
        user.failed_login_count, user.locked_until = ar.register_failure(user.failed_login_count, now, pol)
        audit(db, user.user_id, "LOGIN_FAILED", "user", user.user_id, "FAILED", "bad credentials")
        if user.locked_until:
            audit(db, user.user_id, "ACCOUNT_LOCKED", "user", user.user_id, "SUCCESS",
                  f"locked until {user.locked_until.isoformat()}")
            notify_roles(db, ["ADMIN"], "Failed-login threshold reached",
                         f"Account '{user.username}' was temporarily locked.", "SECURITY", "user", user.user_id)
        db.commit()
        raise AuthFailed(ar.GENERIC_AUTH_ERROR)
    if user.status != "ACTIVE":
        audit(db, user.user_id, "LOGIN_FAILED", "user", user.user_id, "FAILED", "deactivated")
        db.commit()
        raise AccountDisabled("This account has been deactivated. Contact the administrator.")
    user.failed_login_count, user.locked_until, user.last_login_at = 0, None, now
    token = new_token()
    db.add(SessionRecord(user_id=user.user_id, session_token_hash=hash_token(token), created_at=now,
                         expires_at=now + timedelta(hours=ABSOLUTE_SESSION_HOURS), last_activity_at=now))
    audit(db, user.user_id, "LOGIN_SUCCESS", "user", user.user_id)
    db.commit()
    return token, user


def authenticate_token(db: Session, token: Optional[str]) -> User:
    if not token:
        raise SessionExpired("Session expired. Please log in again.")
    now, pol = utcnow(), auth_policy(db)
    sess = db.scalar(select(SessionRecord).where(SessionRecord.session_token_hash == hash_token(token)))
    if sess is None or now >= sess.expires_at or not ar.session_valid(sess.last_activity_at, sess.revoked_at, now, pol):
        if sess is not None and sess.revoked_at is None:
            sess.revoked_at = now
            db.commit()
        raise SessionExpired("Session expired. Please log in again.")
    user = db.get(User, sess.user_id)
    if user is None or user.status != "ACTIVE":
        raise SessionExpired("Session expired. Please log in again.")
    sess.last_activity_at = now
    db.commit()
    return user


def logout(db: Session, token: str, user: User) -> None:
    sess = db.scalar(select(SessionRecord).where(SessionRecord.session_token_hash == hash_token(token)))
    if sess and sess.revoked_at is None:
        sess.revoked_at = utcnow()
    audit(db, user.user_id, "LOGOUT", "user", user.user_id)
    db.commit()


def revoke_all_sessions(db: Session, user_id: int) -> None:
    for s in db.scalars(select(SessionRecord).where(SessionRecord.user_id == user_id,
                                                    SessionRecord.revoked_at.is_(None))).all():
        s.revoked_at = utcnow()


def change_password(db: Session, user: User, old: str, new: str) -> None:
    if not verify_password(old or "", user.password_hash):
        raise ValidationFailed("Current password is incorrect.", {"old_password": "Incorrect."})
    problems = ar.password_problems(new, auth_policy(db))
    if problems:
        raise ValidationFailed(problems[0], {"new_password": problems[0]})
    user.password_hash = hash_password(new)
    audit(db, user.user_id, "PASSWORD_CHANGED", "user", user.user_id)
    db.commit()
