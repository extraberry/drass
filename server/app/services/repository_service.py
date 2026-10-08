"""Repository browse/detail/metadata maintenance with record-level access control (PRD s16, s61)."""
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session
from ..domain import rbac
from ..domain.enums import Role, Status
from ..domain.errors import Forbidden, NotFound, ValidationFailed
from ..models import (Keyword, ResearchAuthor, ResearchKeyword, ResearchWork, ReviewAssignment, User)
from . import index_service
from .common import audit
from .serializers import work_dict
from .submission_service import _apply, _clean_keywords

SORTS = {"title": ResearchWork.title, "year": ResearchWork.year, "archived_at": ResearchWork.archived_at}


def apply_filters(stmt, f: dict):
    for col in ("program_id", "department_id", "year", "adviser_id", "category_id"):
        if f.get(col) is not None:
            stmt = stmt.where(getattr(ResearchWork, col) == f[col])
    if f.get("author"):
        stmt = stmt.where(exists().where(ResearchAuthor.work_id == ResearchWork.work_id,
                                         ResearchAuthor.author_name.ilike(f"%{f['author'].strip()}%")))
    if f.get("keyword"):
        stmt = stmt.where(exists().where(ResearchKeyword.work_id == ResearchWork.work_id,
                                         ResearchKeyword.keyword_id == Keyword.keyword_id,
                                         Keyword.keyword_text.ilike(f"%{f['keyword'].strip().lower()}%")))
    return stmt


def list_repository(db: Session, user: User, filters: dict, sort: str, order: str, page: int, page_size: int,
                    status: str | None = None) -> dict:
    if sort not in SORTS or order not in ("asc", "desc") or page < 1 or not (1 <= page_size <= 100):
        raise ValidationFailed("Invalid sorting or pagination parameters.")
    stmt = select(ResearchWork)
    if status and user.role.role_name == Role.ADMIN.value:          # admins may inspect any status
        if status not in {s.value for s in Status}:
            raise ValidationFailed("Invalid status filter.")
        stmt = stmt.where(ResearchWork.current_status == status)
    else:
        stmt = stmt.where(ResearchWork.current_status == Status.ARCHIVED.value)
    stmt = apply_filters(stmt, filters)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    col = SORTS[sort]
    stmt = stmt.order_by(col.asc() if order == "asc" else col.desc(), ResearchWork.work_id).offset((page - 1) * page_size).limit(page_size)
    items = [work_dict(db, w, detail=False) for w in db.scalars(stmt).all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def assigned_reviewers(db: Session, work_id: int) -> set[int]:
    return set(db.scalars(select(ReviewAssignment.reviewer_id).where(ReviewAssignment.work_id == work_id)).all())


def visible_or_none(db: Session, user: User, work_id: int) -> ResearchWork | None:
    w = db.get(ResearchWork, work_id)
    if w is None:
        return None
    ok = rbac.can_view_work(Role(user.role.role_name), user.user_id, Status(w.current_status),
                            w.submitted_by, assigned_reviewers(db, work_id))
    return w if ok else None


def get_work_for_user(db: Session, user: User, work_id: int, audit_denial: bool = True) -> ResearchWork:
    w = visible_or_none(db, user, work_id)
    if w is None:
        exists_ = db.get(ResearchWork, work_id) is not None
        if exists_ and audit_denial:
            audit(db, user.user_id, "PERMISSION_DENIED", "work", work_id, "DENIED", "record not accessible")
            db.commit()
        if exists_:
            raise Forbidden("You do not have permission to access this research.")
        raise NotFound("Research not found.")
    return w


def update_metadata(db: Session, user: User, work_id: int, data: dict) -> ResearchWork:
    w = db.get(ResearchWork, work_id)
    if w is None:
        raise NotFound("Research not found.")
    if w.current_status != Status.ARCHIVED.value:
        raise ValidationFailed("Only archived records can be maintained here.")
    changed_index = any(k in data for k in ("title", "abstract", "keywords"))
    clean = {k: v for k, v in data.items() if v is not None}
    _apply(db, w, clean)
    w.version += 1
    audit(db, user.user_id, "REPOSITORY_UPDATED", "work", work_id, details=",".join(sorted(clean)))
    if changed_index:
        index_service.mark_stale(db, work_id)
    db.commit()
    if changed_index:
        index_service.index_work(db, work_id, user.user_id, rebuilt=True)
    return w
