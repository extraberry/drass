"""User management, lookups CRUD, dashboards (PRD s28-29, s39)."""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from ..core.security import hash_password
from ..domain import auth_rules as ar
from ..domain.enums import Role, Status
from ..domain.errors import Conflict, NotFound, ValidationFailed
from ..models import (AuditLog, Department, Embedding, Notification, Program, ResearchCategory, ResearchWork,
                      Review, ReviewAssignment, Role as RoleModel, User)
from . import auth_service
from .common import audit, auth_policy


def _role(db: Session, name: str) -> RoleModel:
    r = db.scalar(select(RoleModel).where(RoleModel.role_name == name))
    if r is None or name not in {x.value for x in Role}:
        raise ValidationFailed("Invalid role.", {"role": "Invalid role."})
    return r


def create_user(db: Session, actor: User, d: dict) -> User:
    problems = ar.password_problems(d["password"], auth_policy(db))
    if problems:
        raise ValidationFailed(problems[0], {"password": problems[0]})
    role = _role(db, d["role"])
    if db.scalar(select(User).where(or_(User.username == d["username"], User.email == d["email"]))):
        raise Conflict("An account with that username or email already exists.")
    if d.get("student_number") and db.scalar(select(User).where(User.student_number == d["student_number"])):
        raise Conflict("An account already exists for this student number.")
    u = User(username=d["username"], password_hash=hash_password(d["password"]), role_id=role.role_id,
             full_name=d["full_name"], email=d["email"], student_number=d.get("student_number"),
             department_id=d.get("department_id"))
    db.add(u); db.flush()
    audit(db, actor.user_id, "USER_CREATED", "user", u.user_id, details=f"role={role.role_name}")
    db.commit()
    return db.get(User, u.user_id)


def patch_user(db: Session, actor: User, user_id: int, d: dict) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise NotFound("User not found.")
    if d.get("role") and d["role"] != u.role.role_name:
        if u.user_id == actor.user_id:
            raise ValidationFailed("You cannot change your own role.")
        old = u.role.role_name
        u.role_id = _role(db, d["role"]).role_id
        audit(db, actor.user_id, "ROLE_CHANGED", "user", u.user_id, details=f"{old} -> {d['role']}")
    for f in ("full_name", "email", "student_number", "department_id"):
        if d.get(f) is not None:
            if f == "email" and db.scalar(select(User).where(User.email == d[f], User.user_id != u.user_id)):
                raise Conflict("That email is already in use.")
            setattr(u, f, d[f])
    audit(db, actor.user_id, "USER_UPDATED", "user", u.user_id)
    db.commit()
    db.refresh(u)
    return u


def set_active(db: Session, actor: User, user_id: int, active: bool) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise NotFound("User not found.")
    if not active and u.user_id == actor.user_id:
        raise ValidationFailed("You cannot deactivate your own account.")
    u.status = "ACTIVE" if active else "INACTIVE"
    if active:
        u.failed_login_count, u.locked_until = 0, None
    else:
        auth_service.revoke_all_sessions(db, u.user_id)
    audit(db, actor.user_id, "USER_ACTIVATED" if active else "USER_DEACTIVATED", "user", u.user_id)
    db.commit()
    return u


def reset_password(db: Session, actor: User, user_id: int, new_password: str) -> None:
    u = db.get(User, user_id)
    if u is None:
        raise NotFound("User not found.")
    problems = ar.password_problems(new_password, auth_policy(db))
    if problems:
        raise ValidationFailed(problems[0], {"new_password": problems[0]})
    u.password_hash, u.failed_login_count, u.locked_until = hash_password(new_password), 0, None
    auth_service.revoke_all_sessions(db, u.user_id)
    audit(db, actor.user_id, "USER_PASSWORD_RESET", "user", u.user_id)
    db.commit()


def list_users(db: Session, q: str | None, role: str | None, status: str | None, page: int, page_size: int) -> dict:
    stmt = select(User).join(RoleModel, RoleModel.role_id == User.role_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.username.ilike(like), User.full_name.ilike(like), User.email.ilike(like)))
    if role: stmt = stmt.where(RoleModel.role_name == role)
    if status: stmt = stmt.where(User.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(User.username).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


LOOKUPS = {
    "departments": (Department, "department_name"),
    "programs": (Program, "program_name"),
    "categories": (ResearchCategory, "category_name"),
}


def lookup_rows(db: Session, kind: str, include_inactive=False) -> list[dict]:
    model, col = LOOKUPS[kind]
    stmt = select(model)
    if not include_inactive:
        stmt = stmt.where(model.status == "ACTIVE")
    out = []
    for o in db.scalars(stmt.order_by(getattr(model, col))).all():
        d = {"id": getattr(o, model.__table__.primary_key.columns.keys()[0]), "name": getattr(o, col), "status": o.status}
        if kind == "programs":
            d["department_id"] = o.department_id
        out.append(d)
    return out


def upsert_lookup(db: Session, actor: User, kind: str, d: dict, item_id: int | None = None) -> dict:
    model, col = LOOKUPS[kind]
    if item_id is None:
        if kind == "programs" and not d.get("department_id"):
            raise ValidationFailed("A department is required for a program.")
        obj = model(**{col: d["name"].strip()})
        if kind == "programs":
            obj.department_id = d["department_id"]
        db.add(obj)
    else:
        obj = db.get(model, item_id)
        if obj is None:
            raise NotFound("Item not found.")
        setattr(obj, col, d["name"].strip())
        if d.get("status"): obj.status = d["status"]
        if kind == "programs" and d.get("department_id"): obj.department_id = d["department_id"]
    try:
        db.flush()
    except Exception:   # unique violation
        db.rollback()
        raise Conflict("An item with that name already exists.")
    audit(db, actor.user_id, "LOOKUP_CHANGED", kind, getattr(obj, model.__table__.primary_key.columns.keys()[0]), details=d["name"])
    db.commit()
    return {"id": getattr(obj, model.__table__.primary_key.columns.keys()[0]), "name": d["name"].strip()}


def _count(db, stmt):
    return db.scalar(stmt) or 0


def dashboard(db: Session, user: User) -> dict:
    role = user.role.role_name
    unread = _count(db, select(func.count()).select_from(Notification).where(Notification.user_id == user.user_id, Notification.is_read.is_(False)))
    out = {"role": role, "unread_notifications": unread}
    W = ResearchWork
    by_status = dict(db.execute(select(W.current_status, func.count()).group_by(W.current_status)).all())
    if role == "STUDENT":
        mine = db.scalars(select(W).where(W.submitted_by == user.user_id).order_by(W.updated_at.desc())).all()
        out["submissions"] = [{"work_id": w.work_id, "title": w.title or "(untitled)", "status": w.current_status} for w in mine]
    elif role in ("ADVISER", "PANELIST", "DEAN", "HEAD_LIBRARIAN"):
        pend = _count(db, select(func.count()).select_from(ReviewAssignment).where(
            ReviewAssignment.reviewer_id == user.user_id, ReviewAssignment.status == "PENDING"))
        out["pending_reviews"] = pend
        out["reviewed_total"] = _count(db, select(func.count()).select_from(Review).where(Review.reviewer_id == user.user_id))
        if role == "DEAN":
            out["department_archived"] = _count(db, select(func.count()).select_from(W).where(
                W.current_status == "ARCHIVED", W.department_id == user.department_id))
        if role == "ADVISER":
            out["advisees"] = _count(db, select(func.count(func.distinct(W.submitted_by))).where(W.adviser_id == user.user_id))
    if role in ("LIBRARY_STAFF", "HEAD_LIBRARIAN", "ADMIN"):
        out["archived"] = by_status.get("ARCHIVED", 0)
        out["indexing_failures"] = _count(db, select(func.count()).select_from(Embedding).where(Embedding.status == "FAILED"))
    if role == "EXTERNAL_USER":
        out["archived"] = by_status.get("ARCHIVED", 0)
    if role == "ADMIN":
        out.update(total_works=sum(by_status.values()), by_status=by_status,
                   pending_submissions=by_status.get("SUBMITTED", 0),
                   pending_adviser=by_status.get("UNDER_ADVISER_REVIEW", 0), pending_panel=by_status.get("UNDER_PANEL_REVIEW", 0),
                   pending_dean=by_status.get("UNDER_DEAN_REVIEW", 0), pending_librarian=by_status.get("UNDER_HEAD_LIBRARIAN_REVIEW", 0),
                   rejected=by_status.get("REJECTED", 0),
                   active_users=_count(db, select(func.count()).select_from(User).where(User.status == "ACTIVE")),
                   inactive_users=_count(db, select(func.count()).select_from(User).where(User.status != "ACTIVE")),
                   failed_logins=_count(db, select(func.count()).select_from(AuditLog).where(AuditLog.action == "LOGIN_FAILED")))
    return out
