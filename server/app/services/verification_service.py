"""Head Librarian signatory verification and final archival approval (manuscript FR5-FR7, Figures 6-7).
Persists outcomes decided by domain.workflow. One commit saves the decision and its activity record together (NFR6)."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..core.timeutil import utcnow
from ..domain import workflow as wf
from ..domain.enums import Decision, Status
from ..domain.errors import DrassError, Forbidden, NotFound
from ..models import ResearchWork, Revision, SignatoryVerification, User
from . import files_service, index_service
from .common import audit, notify, notify_roles
from .serializers import work_dict
from .submission_service import _history


def _current_rn(db: Session, w: ResearchWork) -> int:
    return db.get(Revision, w.current_revision_id).revision_number if w.current_revision_id else 1


def _require_head_librarian(db: Session, user: User) -> None:
    """Only the Head Librarian (a Library Staff account designated as such) may verify and approve."""
    if not user.is_head_librarian:
        audit(db, user.user_id, "PERMISSION_DENIED", "verification", None, "DENIED", "not the Head Librarian")
        db.commit()
        raise Forbidden("Only the Head Librarian can verify signatories and give the final archival approval.")


def queue(db: Session) -> list[dict]:
    """Submissions waiting for verification, oldest first."""
    rows = db.scalars(select(ResearchWork).where(ResearchWork.current_status == Status.PENDING_VERIFICATION.value)
                      .order_by(ResearchWork.submitted_at, ResearchWork.work_id)).all()
    return [work_dict(db, w, detail=False) for w in rows]


def work_verification_history(db: Session, work_id: int) -> list[dict]:
    rows = db.execute(select(SignatoryVerification, User).join(User, User.user_id == SignatoryVerification.verified_by)
                      .where(SignatoryVerification.work_id == work_id).order_by(SignatoryVerification.verified_at)).all()
    out = []
    for v, u in rows:
        out.append({"revision_number": v.revision_number, "verified_by": u.full_name, "result": v.result,
                    "remarks": v.remarks, "verified_at": v.verified_at.isoformat(),
                    "checklist": {k: bool(getattr(v, k)) for k in wf.CHECKLIST_ITEMS}})
    return out


def history_for_librarian(db: Session, user: User) -> list[dict]:
    rows = db.execute(select(SignatoryVerification, ResearchWork)
                      .join(ResearchWork, ResearchWork.work_id == SignatoryVerification.work_id)
                      .where(SignatoryVerification.verified_by == user.user_id)
                      .order_by(SignatoryVerification.verified_at.desc())).all()
    return [{"work_id": w.work_id, "title": w.title, "result": v.result, "remarks": v.remarks,
             "verified_at": v.verified_at.isoformat(), "status": w.current_status} for v, w in rows]


def get_detail(db: Session, work_id: int) -> dict:
    w = db.get(ResearchWork, work_id)
    if w is None or w.current_status == Status.DRAFT.value:
        raise NotFound("Submission not found.")
    return {"work": work_dict(db, w), "history": work_verification_history(db, w.work_id),
            "checklist_items": [{"key": k, "label": v} for k, v in wf.CHECKLIST_ITEMS.items()]}


def verify(db: Session, user: User, work_id: int, decision: Decision, checklist: dict, remarks: str,
           publication_status, expected_version) -> dict:
    _require_head_librarian(db, user)
    w = db.scalar(select(ResearchWork).where(ResearchWork.work_id == work_id).with_for_update())
    if w is None:
        raise NotFound("Submission not found.")
    if decision is Decision.APPROVE and w.current_status == Status.PENDING_VERIFICATION.value:
        try:                                                   # NFR2: the checksum is verified before archiving
            files_service.verify_manuscript_integrity(db, w.work_id)
        except DrassError as exc:
            audit(db, user.user_id, "ARCHIVE_FAILED", "work", w.work_id, "FAILED", exc.message)
            notify_roles(db, ["ADMIN"], "Storage error", f"Archiving blocked for work #{w.work_id}: {exc.message}", "STORAGE", "work", w.work_id)
            db.commit()
            raise
    dw = wf.Work(w.work_id, Status(w.current_status), w.version)
    old = w.current_status
    outcome = wf.verify(dw, decision, checklist, remarks, publication_status, expected_version)   # raises on any rule violation
    now = utcnow()
    remarks = (remarks or "").strip()
    w.current_status, w.version = outcome.new_status.value, dw.version
    db.add(SignatoryVerification(
        work_id=w.work_id, revision_number=_current_rn(db, w), verified_by=user.user_id,
        result=decision.value, remarks=remarks, verified_at=now,
        **{k: bool(checklist.get(k)) for k in wf.CHECKLIST_ITEMS}))
    _history(db, w, old, w.current_status, user.user_id, remarks or outcome.reason)
    if decision is Decision.APPROVE:
        w.archived_at, w.archived_by, w.publication_status = now, user.user_id, outcome.publication_status.value
        audit(db, user.user_id, "VERIFICATION_APPROVED", "work", w.work_id, details=f"publication={w.publication_status}")
        audit(db, user.user_id, "RESEARCH_ARCHIVED", "work", w.work_id)
        notify(db, w.submitted_by, "Research archived", f"“{w.title}” was verified and is now archived by the Head Librarian.",
               "ARCHIVE", "work", w.work_id)
    else:
        audit(db, user.user_id, "VERIFICATION_RETURNED", "work", w.work_id, details=remarks[:300])
        notify(db, w.submitted_by, "Returned for correction", f"“{w.title}”: {remarks}", "VERIFICATION", "work", w.work_id)
    db.commit()
    if decision is Decision.APPROVE:
        index_service.index_work(db, w.work_id, user.user_id)      # a failure here never undoes the archive
    return {"work_id": w.work_id, "status": w.current_status, "message": outcome.reason}
