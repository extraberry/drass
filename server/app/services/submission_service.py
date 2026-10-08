"""Student submission lifecycle: draft, validate, submit, revise, resubmit (PRD s11, s14)."""
import hashlib
import json
from datetime import datetime
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..core.timeutil import utcnow
from ..domain import duplicates, workflow as wf
from ..domain.enums import Role, Stage, Status
from ..domain.errors import DuplicateResearch, Forbidden, InvalidTransition, NotFound, ValidationFailed
from ..models import (Keyword, ResearchAuthor, ResearchKeyword, ResearchWork, Revision, ReviewAssignment,
                      Role as RoleModel, User, Department, Program, ResearchCategory)
from . import files_service
from .common import audit, notify
from .serializers import STATUS_LABELS, authors_of, keywords_of, work_dict

EDITABLE = {Status.DRAFT.value, Status.RETURNED_FOR_REVISION.value}


def _owned(db: Session, user: User, work_id: int) -> ResearchWork:
    w = db.get(ResearchWork, work_id)
    if w is None or w.submitted_by != user.user_id:
        raise NotFound("Submission not found.")      # do not reveal other users' records
    return w


def get_owned_editable(db: Session, user: User, work_id: int) -> ResearchWork:
    w = _owned(db, user, work_id)
    if w.current_status not in EDITABLE:
        raise InvalidTransition("This submission can no longer be edited.")
    return w


def _clean_keywords(items: list[str]) -> list[str]:
    seen, out = set(), []
    for k in items:
        k = " ".join((k or "").split()).lower()[:80]
        if k and k not in seen:
            seen.add(k); out.append(k)
    return out


def _dup_key(w: ResearchWork, authors: list[str]) -> Optional[str]:
    if not w.title or not authors or not w.year:
        return None
    return hashlib.sha256(repr(duplicates.duplicate_key(w.title, authors, w.year)).encode()).hexdigest()


def _apply(db: Session, w: ResearchWork, data: dict) -> None:
    for f in ("title", "abstract", "year", "program_id", "department_id", "category_id", "adviser_id"):
        if f in data:
            v = data[f].strip() if isinstance(data[f], str) else data[f]
            setattr(w, f, "" if (v is None and f in ("title", "abstract")) else v)
    if "program_id" in data and data["program_id"]:
        p = db.get(Program, data["program_id"])
        if p is None:
            raise ValidationFailed("Unknown program.", {"program_id": "Unknown program."})
        w.department_id = w.department_id or p.department_id
    if data.get("category_id") and db.get(ResearchCategory, data["category_id"]) is None:
        raise ValidationFailed("Unknown category.", {"category_id": "Unknown category."})
    if data.get("adviser_id"):
        adv = db.get(User, data["adviser_id"])
        if adv is None or adv.role.role_name != Role.ADVISER.value or adv.status != "ACTIVE":
            raise ValidationFailed("Select a valid adviser.", {"adviser_id": "Select a valid adviser."})
    if data.get("authors") is not None:
        db.query(ResearchAuthor).filter(ResearchAuthor.work_id == w.work_id).delete()
        for i, a in enumerate(data["authors"], 1):
            db.add(ResearchAuthor(work_id=w.work_id, author_name=a["name"].strip(),
                                  student_number=(a.get("student_number") or None), author_order=i))
    if data.get("keywords") is not None:
        db.query(ResearchKeyword).filter(ResearchKeyword.work_id == w.work_id).delete()
        for text in _clean_keywords(data["keywords"]):
            kw = db.scalar(select(Keyword).where(Keyword.keyword_text == text))
            if kw is None:
                kw = Keyword(keyword_text=text); db.add(kw); db.flush()
            db.add(ResearchKeyword(work_id=w.work_id, keyword_id=kw.keyword_id))
    db.flush()
    w.dup_key = _dup_key(w, [a["name"] for a in authors_of(db, w.work_id)])


def create_draft(db: Session, user: User, data: dict) -> ResearchWork:
    w = ResearchWork(submitted_by=user.user_id, current_status=Status.DRAFT.value,
                     title=(data.get("title") or "").strip(), abstract="")
    db.add(w); db.flush()
    w.reference_no = f"DRASS-{utcnow().year}-{w.work_id:05d}"
    data = {**data}
    if not data.get("authors"):
        data["authors"] = [{"name": user.full_name, "student_number": user.student_number}]
    _apply(db, w, data)
    _history(db, w, None, "DRAFT", user.user_id, "Draft created")
    audit(db, user.user_id, "SUBMISSION_CREATED", "work", w.work_id)
    return w


def update(db: Session, user: User, work_id: int, data: dict) -> ResearchWork:
    w = get_owned_editable(db, user, work_id)
    _apply(db, w, data)
    w.version += 1
    audit(db, user.user_id, "SUBMISSION_UPDATED", "work", w.work_id)
    return w


def validate_for_submit(db: Session, w: ResearchWork) -> None:
    errs = {}
    if not (w.title or "").strip(): errs["title"] = "Title is required."
    if not (w.abstract or "").strip(): errs["abstract"] = "Abstract is required."
    if not w.year: errs["year"] = "Year is required."
    if not w.program_id: errs["program_id"] = "Program is required."
    if not w.department_id: errs["department_id"] = "Department is required."
    if not w.category_id: errs["category_id"] = "Research category is required."
    if not w.adviser_id: errs["adviser_id"] = "Adviser is required."
    if not authors_of(db, w.work_id): errs["authors"] = "At least one author is required."
    if not keywords_of(db, w.work_id): errs["keywords"] = "At least one keyword is required."
    if files_service.active_manuscript(db, w.work_id) is None: errs["manuscript"] = "A manuscript PDF is required."
    if errs:
        raise ValidationFailed("Please complete the required fields.", errs)
    if w.dup_key:
        other = db.scalar(select(ResearchWork).where(
            ResearchWork.dup_key == w.dup_key, ResearchWork.work_id != w.work_id,
            ResearchWork.current_status.notin_([Status.DRAFT.value, Status.REJECTED.value])))
        if other is not None:
            raise DuplicateResearch("A research record with the same title, authors and year already exists.")


def ensure_assignments(db: Session, w: ResearchWork, stage: Stage, revision_number: int) -> list[int]:
    """Create pending assignments for a stage (idempotent per revision). Returns reviewer ids."""
    existing = db.scalars(select(ReviewAssignment).where(
        ReviewAssignment.work_id == w.work_id, ReviewAssignment.stage == stage.value,
        ReviewAssignment.revision_number == revision_number, ReviewAssignment.status != "CANCELLED")).all()
    if existing:
        return [a.reviewer_id for a in existing]
    q = select(User).join(RoleModel, User.role_id == RoleModel.role_id).where(User.status == "ACTIVE")
    if stage is Stage.ADVISER:
        reviewers = [db.get(User, w.adviser_id)]
    elif stage is Stage.PANEL:
        same = db.scalars(q.where(RoleModel.role_name == "PANELIST", User.department_id == w.department_id)).all()
        reviewers = list(same) or list(db.scalars(q.where(RoleModel.role_name == "PANELIST")).all())
    elif stage is Stage.DEAN:
        same = db.scalars(q.where(RoleModel.role_name == "DEAN", User.department_id == w.department_id)).all()
        reviewers = list(same[:1]) or list(db.scalars(q.where(RoleModel.role_name == "DEAN")).all()[:1])
    else:
        reviewers = list(db.scalars(q.where(RoleModel.role_name == "HEAD_LIBRARIAN")).all()[:1])
    reviewers = [r for r in reviewers if r is not None]
    if not reviewers:
        raise ValidationFailed(f"No active reviewer is available for the {stage.value} stage. Contact the administrator.")
    for r in reviewers:
        db.add(ReviewAssignment(work_id=w.work_id, stage=stage.value, reviewer_id=r.user_id,
                                revision_number=revision_number))
        notify(db, r.user_id, "New submission awaiting review", f"“{w.title}” is ready for your {stage.value.replace('_',' ').title()} review.",
               "REVIEW", "work", w.work_id)
    return [r.user_id for r in reviewers]


def set_panel(db: Session, actor: User, w: ResearchWork, panelist_ids: list[int]) -> None:
    rn = db.get(Revision, w.current_revision_id).revision_number if w.current_revision_id else 1
    ids = set(panelist_ids)
    users = [db.get(User, i) for i in ids]
    if any(u is None or u.role.role_name != "PANELIST" or u.status != "ACTIVE" for u in users):
        raise ValidationFailed("All selected users must be active panelists.")
    if w.current_status in (Status.UNDER_DEAN_REVIEW.value, Status.UNDER_HEAD_LIBRARIAN_REVIEW.value,
                            Status.ARCHIVED.value, Status.REJECTED.value):
        raise InvalidTransition("The panel can no longer be changed for this work.")
    for a in db.scalars(select(ReviewAssignment).where(ReviewAssignment.work_id == w.work_id,
                        ReviewAssignment.stage == "PANEL", ReviewAssignment.revision_number == rn,
                        ReviewAssignment.status == "PENDING")).all():
        if a.reviewer_id not in ids:
            a.status = "CANCELLED"
    have = set(db.scalars(select(ReviewAssignment.reviewer_id).where(
        ReviewAssignment.work_id == w.work_id, ReviewAssignment.stage == "PANEL",
        ReviewAssignment.revision_number == rn, ReviewAssignment.status != "CANCELLED")).all())
    for uid in ids - have:
        db.add(ReviewAssignment(work_id=w.work_id, stage="PANEL", reviewer_id=uid, revision_number=rn))
        notify(db, uid, "Reassigned work", f"You were assigned to review “{w.title}”.", "REVIEW", "work", w.work_id)
    audit(db, actor.user_id, "PANEL_ASSIGNED", "work", w.work_id, details=f"panelists={sorted(ids)}")


def _snapshot(db: Session, w: ResearchWork) -> str:
    d = work_dict(db, w)
    d["files"] = [{k: f[k] for k in ("file_id", "file_type", "filename", "size_bytes")} for f in d["files"]]
    return json.dumps(d, default=str)


def _new_revision(db: Session, w: ResearchWork, user: User, notes: str) -> Revision:
    n = (db.scalar(select(func.max(Revision.revision_number)).where(Revision.work_id == w.work_id)) or 0) + 1
    rev = Revision(work_id=w.work_id, revision_number=n, submitted_by=user.user_id, change_notes=notes,
                   metadata_snapshot=_snapshot(db, w))
    db.add(rev); db.flush()
    w.current_revision_id = rev.revision_id
    return rev


def _history(db, w, old, new, actor, reason=""):
    from ..models import StatusHistory
    db.add(StatusHistory(work_id=w.work_id, from_status=old, to_status=new, actor_user_id=actor, reason=reason))


def submit(db: Session, user: User, work_id: int) -> ResearchWork:
    w = _owned(db, user, work_id)
    if w.current_status != Status.DRAFT.value:
        raise InvalidTransition("Only drafts can be submitted.")
    validate_for_submit(db, w)
    rev = _new_revision(db, w, user, "Initial submission")
    dw = wf.Work(w.work_id, Status(w.current_status), w.version)
    wf.submit(dw)
    w.current_status, w.version, w.submitted_at = dw.status.value, dw.version, utcnow()
    _history(db, w, "DRAFT", "SUBMITTED", user.user_id, "Submitted")
    _history(db, w, "SUBMITTED", dw.status.value, None, "Routed to adviser")
    ensure_assignments(db, w, Stage.ADVISER, rev.revision_number)
    notify(db, user.user_id, "Submission received", f"Reference {w.reference_no} is now under adviser review.",
           "SUBMISSION", "work", w.work_id)
    audit(db, user.user_id, "SUBMISSION_SUBMITTED", "work", w.work_id, details=w.reference_no or "")
    return w


def resubmit(db: Session, user: User, work_id: int, change_notes: str) -> ResearchWork:
    w = _owned(db, user, work_id)
    if w.current_status != Status.RETURNED_FOR_REVISION.value:
        raise InvalidTransition("Only returned submissions can be resubmitted.")
    if not (change_notes or "").strip():
        raise ValidationFailed("Please describe what changed.", {"change_notes": "Required."})
    validate_for_submit(db, w)
    rev = _new_revision(db, w, user, change_notes.strip())
    dw = wf.Work(w.work_id, Status(w.current_status), w.version)
    wf.resubmit(dw)
    w.current_status, w.version = dw.status.value, dw.version
    _history(db, w, "RETURNED_FOR_REVISION", dw.status.value, user.user_id, change_notes.strip())
    ensure_assignments(db, w, Stage.ADVISER, rev.revision_number)
    audit(db, user.user_id, "SUBMISSION_RESUBMITTED", "work", w.work_id, details=f"revision {rev.revision_number}")
    return w


def list_own(db: Session, user: User) -> list[dict]:
    rows = db.scalars(select(ResearchWork).where(ResearchWork.submitted_by == user.user_id)
                      .order_by(ResearchWork.updated_at.desc())).all()
    return [work_dict(db, w, detail=False) for w in rows]
