"""Audit, activity, notification and settings helpers shared by all services."""
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..core.timeutil import utcnow
from ..domain.auth_rules import AuthPolicy
from ..domain.errors import ValidationFailed
from ..models import ActivityLog, AuditLog, Notification, Role as RoleModel, SystemSetting, User

log = logging.getLogger("drass.app")
audit_log = logging.getLogger("drass.audit")

# key: (default, type, min, max)
SETTING_SPECS = {
    "min_password_length": ("8", int, 6, 128),
    "failed_login_limit": ("5", int, 1, 50),
    "lockout_minutes": ("15", int, 1, 1440),
    "idle_timeout_minutes": ("20", int, 1, 1440),
    "max_manuscript_mb": ("100", int, 1, 2048),
    "max_companion_mb": ("500", int, 1, 4096),
    "semantic_threshold": ("0.35", float, 0.0, 1.0),
    "recommendation_count": ("5", int, 1, 20),
    "log_search_queries": ("true", bool, None, None),
}


def audit(db: Session, user_id: Optional[int], action: str, target_type: Optional[str] = None,
          target_id=None, result: str = "SUCCESS", details: str = "") -> None:
    """Append-only audit row. Caller commits (or the request commit does)."""
    db.add(AuditLog(user_id=user_id, action=action, target_type=target_type,
                    target_id=None if target_id is None else str(target_id),
                    result=result, details=details[:2000], timestamp=utcnow()))
    audit_log.info("%s user=%s target=%s:%s result=%s", action, user_id, target_type, target_id, result)


def activity(db: Session, user_id: Optional[int], event_type: str, target_type: Optional[str] = None,
             target_id=None, details: str = "") -> None:
    db.add(ActivityLog(user_id=user_id, event_type=event_type, target_type=target_type,
                       target_id=None if target_id is None else str(target_id),
                       details=details[:500], timestamp=utcnow()))


def notify(db: Session, user_id: int, title: str, message: str, type_: str = "INFO",
           target_type: Optional[str] = None, target_id: Optional[int] = None) -> None:
    db.add(Notification(user_id=user_id, title=title[:200], message=message, type=type_,
                        target_type=target_type, target_id=target_id))


def notify_roles(db: Session, role_names: list[str], title: str, message: str, type_: str = "INFO",
                 target_type: Optional[str] = None, target_id: Optional[int] = None) -> None:
    ids = db.scalars(select(User.user_id).join(RoleModel, User.role_id == RoleModel.role_id)
                     .where(RoleModel.role_name.in_(role_names), User.status == "ACTIVE")).all()
    for uid in ids:
        notify(db, uid, title, message, type_, target_type, target_id)


# ---- settings ----
def get_all_settings(db: Session) -> dict:
    out = {k: v[0] for k, v in SETTING_SPECS.items()}
    for row in db.scalars(select(SystemSetting)).all():
        if row.setting_key in out:
            out[row.setting_key] = row.setting_value
    return out


def _cast(key: str, raw: str):
    typ = SETTING_SPECS[key][1]
    if typ is bool:
        return str(raw).lower() == "true"
    return typ(raw)


def get_setting(db: Session, key: str):
    return _cast(key, get_all_settings(db)[key])


def set_setting(db: Session, actor: User, key: str, value) -> None:
    if key not in SETTING_SPECS:
        raise ValidationFailed(f"Unknown setting: {key}")
    default, typ, lo, hi = SETTING_SPECS[key]
    try:
        if typ is bool:
            if str(value).lower() not in ("true", "false"):
                raise ValueError
            norm = str(value).lower()
        else:
            num = typ(value)
            if num < lo or num > hi:
                raise ValueError
            norm = str(num)
    except (ValueError, TypeError):
        raise ValidationFailed(f"Invalid value for {key}.", {key: "Out of range or wrong type."})
    row = db.scalar(select(SystemSetting).where(SystemSetting.setting_key == key))
    old = row.setting_value if row else default
    if row is None:
        db.add(SystemSetting(setting_key=key, setting_value=norm, updated_by=actor.user_id))
    else:
        row.setting_value, row.updated_by = norm, actor.user_id
    audit(db, actor.user_id, "SETTING_CHANGED", "setting", key, details=f"{old} -> {norm}")


def auth_policy(db: Session) -> AuthPolicy:
    s = get_all_settings(db)
    return AuthPolicy(int(s["min_password_length"]), int(s["failed_login_limit"]),
                      int(s["lockout_minutes"]), int(s["idle_timeout_minutes"]))
