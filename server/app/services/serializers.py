from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import (Department, FileRecord, Keyword, Program, ResearchAuthor, ResearchCategory,
                      ResearchKeyword, ResearchWork, User)

STATUS_LABELS = {
    "DRAFT": "Draft", "SUBMITTED": "Submitted", "UNDER_ADVISER_REVIEW": "Under Adviser Review",
    "UNDER_PANEL_REVIEW": "Under Panel Review", "UNDER_DEAN_REVIEW": "Under Dean Review",
    "UNDER_HEAD_LIBRARIAN_REVIEW": "Under Head Librarian Review",
    "RETURNED_FOR_REVISION": "Returned for Revision", "REJECTED": "Rejected", "ARCHIVED": "Archived",
}


def authors_of(db: Session, work_id: int) -> list[dict]:
    rows = db.scalars(select(ResearchAuthor).where(ResearchAuthor.work_id == work_id)
                      .order_by(ResearchAuthor.author_order)).all()
    return [{"name": r.author_name, "student_number": r.student_number} for r in rows]


def keywords_of(db: Session, work_id: int) -> list[str]:
    return list(db.scalars(select(Keyword.keyword_text).join(ResearchKeyword, ResearchKeyword.keyword_id == Keyword.keyword_id)
                           .where(ResearchKeyword.work_id == work_id).order_by(Keyword.keyword_text)).all())


def _name(db, model, pk, col) -> Optional[str]:
    if pk is None:
        return None
    obj = db.get(model, pk)
    return getattr(obj, col) if obj else None


def work_dict(db: Session, w: ResearchWork, detail: bool = True) -> dict:
    d = {
        "work_id": w.work_id, "reference_no": w.reference_no, "title": w.title, "year": w.year,
        "authors": authors_of(db, w.work_id),
        "program_id": w.program_id, "program": _name(db, Program, w.program_id, "program_name"),
        "department_id": w.department_id, "department": _name(db, Department, w.department_id, "department_name"),
        "category_id": w.category_id, "category": _name(db, ResearchCategory, w.category_id, "category_name"),
        "adviser_id": w.adviser_id, "adviser": _name(db, User, w.adviser_id, "full_name"),
        "status": w.current_status, "status_label": STATUS_LABELS.get(w.current_status, w.current_status),
        "version": w.version, "submitted_at": w.submitted_at.isoformat() if w.submitted_at else None,
        "archived_at": w.archived_at.isoformat() if w.archived_at else None,
    }
    if detail:
        d["abstract"] = w.abstract
        d["keywords"] = keywords_of(db, w.work_id)
        files = db.scalars(select(FileRecord).where(FileRecord.work_id == w.work_id, FileRecord.is_active.is_(True))).all()
        d["files"] = [{"file_id": f.file_id, "file_type": f.file_type, "filename": f.original_filename,
                       "size_bytes": f.size_bytes, "uploaded_at": f.uploaded_at.isoformat()} for f in files]
    return d


def user_dict(u: User) -> dict:
    return {"user_id": u.user_id, "username": u.username, "full_name": u.full_name, "email": u.email,
            "role": u.role.role_name, "student_number": u.student_number, "department_id": u.department_id,
            "status": u.status, "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None}
