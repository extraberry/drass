"""Repository browse/detail/metadata maintenance with record-level access control (manuscript FR9, FR10, FR12)."""
from sqlalchemy import and_, exists, false, func, or_, select
from sqlalchemy.orm import Session
from ..domain import rbac
from ..domain.enums import PublicationStatus, Role, Status
from ..domain.errors import Forbidden, NotFound, ValidationFailed
from ..models import Keyword, ResearchAuthor, ResearchKeyword, ResearchWork, User
from . import index_service
from .common import audit
from .serializers import authors_of, keywords_of, work_dict
from .submission_service import _apply, _history

SORTS = {"title": ResearchWork.title, "year": ResearchWork.year, "archived_at": ResearchWork.archived_at}
METADATA_FIELDS = ("title", "abstract", "year", "program_id", "department_id", "category_id", "adviser_id", "dean_id")


def role_of(user) -> Role:
    return Role(user.role.role_name)


def archived_visibility(user):
    """SQL condition: ARCHIVED works this user may see, by publication status (FR10)."""
    W = ResearchWork
    role = role_of(user)
    base = W.current_status == Status.ARCHIVED.value
    general = rbac.visible_publication_statuses(role, False)
    if not general and not (role is Role.STUDENT):
        return false()
    cond = W.publication_status.in_(sorted(general)) if general else false()
    if role is Role.STUDENT and user.user_id is not None:       # a student also sees their own unpublished work
        cond = or_(cond, and_(W.publication_status == PublicationStatus.UNPUBLISHED.value, W.submitted_by == user.user_id))
    return and_(base, cond)


def apply_filters(stmt, f: dict):
    for col in ("program_id", "department_id", "year", "adviser_id", "dean_id", "category_id"):
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
                    publication_status: str | None = None) -> dict:
    if sort not in SORTS or order not in ("asc", "desc") or page < 1 or not (1 <= page_size <= 100):
        raise ValidationFailed("Invalid sorting or pagination parameters.")
    stmt = select(ResearchWork).where(archived_visibility(user))
    if publication_status:
        if publication_status not in {p.value for p in PublicationStatus}:
            raise ValidationFailed("Invalid publication status filter.")
        stmt = stmt.where(ResearchWork.publication_status == publication_status)
    stmt = apply_filters(stmt, filters)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    col = SORTS[sort]
    stmt = stmt.order_by(col.asc() if order == "asc" else col.desc(), ResearchWork.work_id).offset((page - 1) * page_size).limit(page_size)
    items = [work_dict(db, w, detail=False) for w in db.scalars(stmt).all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def visible_or_none(db: Session, user: User, work_id: int) -> ResearchWork | None:
    w = db.get(ResearchWork, work_id)
    if w is None:
        return None
    ok = rbac.can_view_work(role_of(user), user.user_id, Status(w.current_status), w.submitted_by, w.publication_status)
    return w if ok else None


def get_work_for_user(db: Session, user: User, work_id: int, audit_denial: bool = True) -> ResearchWork:
    w = visible_or_none(db, user, work_id)
    if w is None:
        exists_ = db.get(ResearchWork, work_id) is not None
        if exists_ and audit_denial and user.user_id is not None:
            audit(db, user.user_id, "PERMISSION_DENIED", "work", work_id, "DENIED", "record not accessible")
            db.commit()
        if exists_:
            raise Forbidden("You do not have permission to access this research.")
        raise NotFound("Research not found.")
    return w


def detail_for_user(db: Session, user: User, w: ResearchWork) -> dict:
    """work_dict with companion files only for the roles allowed to see them (FR15)."""
    return work_dict(db, w, include_companions=rbac.can_access_companions(role_of(user), user.user_id, w.submitted_by))


def update_metadata(db: Session, user: User, work_id: int, data: dict) -> ResearchWork:
    """FR9: Library Staff edit the metadata of archived research. Each change is recorded (old -> new) and the search index is updated."""
    w = db.get(ResearchWork, work_id)
    if w is None:
        raise NotFound("Research not found.")
    if w.current_status != Status.ARCHIVED.value:
        raise ValidationFailed("Only archived records can be maintained here.")
    clean = {k: v for k, v in data.items() if v is not None}
    before = {f: getattr(w, f) for f in METADATA_FIELDS}
    before["authors"] = [a["name"] for a in authors_of(db, work_id)]
    before["keywords"] = keywords_of(db, work_id)
    _apply(db, w, clean)
    changes = []
    for f in METADATA_FIELDS:
        if f in clean and getattr(w, f) != before[f]:
            changes.append(f"{f}: {str(before[f])[:60]!r} -> {str(getattr(w, f))[:60]!r}")
    if "authors" in clean and [a["name"] for a in authors_of(db, work_id)] != before["authors"]:
        changes.append("authors changed")
    if "keywords" in clean and keywords_of(db, work_id) != before["keywords"]:
        changes.append("keywords changed")
    changed_index = any(k in clean for k in ("title", "abstract", "keywords"))
    w.version += 1
    audit(db, user.user_id, "REPOSITORY_UPDATED", "work", work_id, details="; ".join(changes)[:1900] or "no field changed")
    if changed_index:
        index_service.mark_stale(db, work_id)
    db.commit()
    if changed_index:
        index_service.index_work(db, work_id, user.user_id, rebuilt=True)
    return w


def set_publication_status(db: Session, user: User, work_id: int, new_status: str) -> ResearchWork:
    """FR10: Library Staff assign Public / Restricted / Unpublished to an archived work."""
    if new_status not in {p.value for p in PublicationStatus}:
        raise ValidationFailed("Choose Public, Restricted or Unpublished.", {"publication_status": "Invalid."})
    w = db.get(ResearchWork, work_id)
    if w is None:
        raise NotFound("Research not found.")
    if w.current_status != Status.ARCHIVED.value:
        raise ValidationFailed("Only archived records have a publication status.")
    old = w.publication_status
    w.publication_status = new_status
    w.version += 1
    _history(db, w, w.current_status, w.current_status, user.user_id, f"Publication status {old} -> {new_status}")
    audit(db, user.user_id, "PUBLICATION_STATUS_CHANGED", "work", work_id, details=f"{old} -> {new_status}")
    db.commit()
    return w
