"""Review queue and decisions; persists outcomes decided by domain.workflow (PRD s13, s34, s71)."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..core.timeutil import utcnow
from ..domain import workflow as wf
from ..domain.enums import Decision, Stage, Status
from ..domain.errors import DrassError, Forbidden, NotFound, StaleState, ValidationFailed
from ..models import ResearchWork, Review, ReviewAssignment, Revision, User
from . import files_service, index_service
from .common import audit, get_setting, notify, notify_roles
from .serializers import work_dict
from .submission_service import _history, ensure_assignments

STAGE_OF_STATUS = {v: k for k, v in wf.STAGE_STATUS.items()}
AUDIT_ACTION = {"APPROVE": "REVIEW_APPROVED", "RETURN": "REVIEW_RETURNED", "REJECT": "REVIEW_REJECTED"}


def _current_rn(db: Session, w: ResearchWork) -> int:
    return db.get(Revision, w.current_revision_id).revision_number if w.current_revision_id else 1


def _domain_work(db: Session, w: ResearchWork) -> wf.Work:
    rn = _current_rn(db, w)
    rows = db.scalars(select(ReviewAssignment).where(
        ReviewAssignment.work_id == w.work_id, ReviewAssignment.revision_number == rn,
        ReviewAssignment.status != "CANCELLED")).all()
    assigns = []
    for a in rows:
        rv = db.scalar(select(Review).where(Review.assignment_id == a.assignment_id))
        assigns.append(wf.Assignment(a.reviewer_id, Stage(a.stage), Decision(rv.decision) if rv else None))
    return wf.Work(w.work_id, Status(w.current_status), w.version, assigns)


def queue(db: Session, user: User) -> list[dict]:
    rows = db.execute(select(ReviewAssignment, ResearchWork).join(ResearchWork, ResearchWork.work_id == ReviewAssignment.work_id)
                      .where(ReviewAssignment.reviewer_id == user.user_id, ReviewAssignment.status == "PENDING")
                      .order_by(ReviewAssignment.assigned_at)).all()
    out = []
    for a, w in rows:
        if wf.STAGE_STATUS[Stage(a.stage)].value != w.current_status or a.revision_number != _current_rn(db, w):
            continue
        d = work_dict(db, w, detail=False)
        d.update(assignment_id=a.assignment_id, stage=a.stage, assigned_at=a.assigned_at.isoformat())
        out.append(d)
    return out


def history_for_reviewer(db: Session, user: User) -> list[dict]:
    rows = db.execute(select(Review, ResearchWork).join(ResearchWork, ResearchWork.work_id == Review.work_id)
                      .where(Review.reviewer_id == user.user_id).order_by(Review.decided_at.desc())).all()
    return [{"work_id": w.work_id, "title": w.title, "decision": r.decision, "comments": r.comments,
             "decided_at": r.decided_at.isoformat(), "status": w.current_status} for r, w in rows]


def work_review_history(db: Session, work_id: int) -> list[dict]:
    rows = db.execute(select(Review, ReviewAssignment, User).join(ReviewAssignment, ReviewAssignment.assignment_id == Review.assignment_id)
                      .join(User, User.user_id == Review.reviewer_id).where(Review.work_id == work_id)
                      .order_by(Review.decided_at)).all()
    return [{"stage": a.stage, "revision_number": a.revision_number, "reviewer": u.full_name,
             "decision": r.decision, "comments": r.comments, "decided_at": r.decided_at.isoformat()} for r, a, u in rows]


def get_detail(db: Session, user: User, assignment_id: int) -> dict:
    a = db.get(ReviewAssignment, assignment_id)
    if a is None or a.reviewer_id != user.user_id:
        raise NotFound("Review not found.")
    w = db.get(ResearchWork, a.work_id)
    return {"assignment_id": a.assignment_id, "stage": a.stage, "assignment_status": a.status,
            "work": work_dict(db, w), "history": work_review_history(db, w.work_id)}


def act(db: Session, user: User, assignment_id: int, decision: Decision, comments: str,
        expected_version, panel_offline: bool = False, panel_offline_reference: str = "") -> dict:
    a = db.get(ReviewAssignment, assignment_id)
    if a is None:
        raise NotFound("Review not found.")
    if a.reviewer_id != user.user_id:
        audit(db, user.user_id, "PERMISSION_DENIED", "assignment", assignment_id, "DENIED", "not assigned")
        db.commit()
        raise Forbidden("You are not assigned to review this work.")
    w = db.scalar(select(ResearchWork).where(ResearchWork.work_id == a.work_id).with_for_update())
    stage = Stage(a.stage)
    if a.status != "PENDING" or a.revision_number != _current_rn(db, w):
        raise StaleState("This review is no longer pending. Please reload.")
    if decision is Decision.APPROVE and stage is Stage.HEAD_LIBRARIAN:     # validate files BEFORE changing state
        try:
            files_service.verify_manuscript_integrity(db, w.work_id)
        except DrassError as exc:
            audit(db, user.user_id, "ARCHIVE_FAILED", "work", w.work_id, "FAILED", exc.message)
            notify_roles(db, ["ADMIN"], "Storage error", f"Archiving blocked for work #{w.work_id}: {exc.message}", "STORAGE", "work", w.work_id)
            db.commit()
            raise
    offline_to, ref = None, (panel_offline_reference or "").strip()
    if panel_offline:
        if stage is not Stage.ADVISER or decision is not Decision.APPROVE:
            raise ValidationFailed("Offline panel approval can only be recorded when the adviser approves.")
        if len(ref) < 3:
            raise ValidationFailed("Enter the reference of the signed panel approval (e.g. letter date or number).",
                                   {"panel_offline_reference": "Required."})
        offline_to = wf.offline_panel_target(bool(get_setting(db, "offline_panel_skips_dean")))
    dw = _domain_work(db, w)
    old = w.current_status
    outcome = wf.review(dw, user.user_id, stage, decision, comments, expected_version, panel_offline_to=offline_to)   # raises on any rule violation
    if offline_to is not None:
        comments = f"[PANEL APPROVED OFFLINE – ref: {ref}] {(comments or '').strip()}".strip()
    now = utcnow()
    w.current_status, w.version = outcome.new_status.value, dw.version
    db.add(Review(assignment_id=a.assignment_id, work_id=w.work_id, reviewer_id=user.user_id,
                  decision=decision.value, comments=(comments or "").strip(), decided_at=now))
    a.status, a.completed_at = "DONE", now
    audit(db, user.user_id, AUDIT_ACTION[decision.value], "work", w.work_id, details=f"stage={stage.value}")
    if offline_to is not None:
        audit(db, user.user_id, "REVIEW_PANEL_OFFLINE_APPROVED", "work", w.work_id,
              details=f"{old}->{offline_to.value} ref={ref[:200]}")
    student = w.submitted_by
    label = stage.value.replace("_", " ").title()
    if outcome.stage_complete:
        for other in db.scalars(select(ReviewAssignment).where(
                ReviewAssignment.work_id == w.work_id, ReviewAssignment.stage == a.stage,
                ReviewAssignment.revision_number == a.revision_number, ReviewAssignment.status == "PENDING")).all():
            other.status = "CANCELLED"
        if w.current_status != old:
            _history(db, w, old, w.current_status, user.user_id, (comments or "").strip() or outcome.reason)
        new = outcome.new_status
        if decision is Decision.APPROVE:
            if new is Status.ARCHIVED:
                w.archived_at = now
                audit(db, user.user_id, "RESEARCH_ARCHIVED", "work", w.work_id)
                notify(db, student, "Research archived", f"“{w.title}” is now archived.", "ARCHIVE", "work", w.work_id)
            else:
                nxt_stage = STAGE_OF_STATUS[new]
                ensure_assignments(db, w, nxt_stage, a.revision_number)
                if offline_to is not None:
                    notify(db, student, "Approved by adviser", f"“{w.title}”: adviser approved and the panel's offline approval (ref: {ref}) was recorded.", "REVIEW", "work", w.work_id)
                else:
                    notify(db, student, f"Approved by {label}", f"“{w.title}” passed {label} review.", "REVIEW", "work", w.work_id)
                if nxt_stage is Stage.HEAD_LIBRARIAN:
                    notify_roles(db, ["HEAD_LIBRARIAN"], "Work waiting for archive review" if offline_to else "Dean-approved work waiting",
                                 f"“{w.title}” awaits final archive review." + (f" Panel approval was recorded offline (ref: {ref})." if offline_to else ""), "REVIEW", "work", w.work_id)
        elif decision is Decision.RETURN:
            notify(db, student, "Returned for revision", f"“{w.title}”: {(comments or '').strip()}", "REVIEW", "work", w.work_id)
        else:
            notify(db, student, "Submission rejected", f"“{w.title}”: {(comments or '').strip()}", "REVIEW", "work", w.work_id)
    db.commit()
    if outcome.new_status is Status.ARCHIVED:
        index_service.index_work(db, w.work_id, user.user_id)    # failure here never undoes the archive
    return {"work_id": w.work_id, "status": w.current_status, "stage_complete": outcome.stage_complete,
            "message": outcome.reason}


def admin_override(db: Session, admin: User, work_id: int, mode: str, reason: str, expected_version) -> dict:
    """Administrator approves a work under review without waiting for adviser/panel/etc.
    Loud by design: mandatory reason, an 'ADMIN OVERRIDE' review row, status history, audit and notifications.
    Existing review decisions are never modified."""
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationFailed("A reason of at least 5 characters is required for an administrator approval.", {"reason": "Required."})
    w = db.scalar(select(ResearchWork).where(ResearchWork.work_id == work_id).with_for_update())
    if w is None:
        raise NotFound("Research not found.")
    if expected_version is not None and expected_version != w.version:
        raise StaleState("This record changed since you opened it. Please reload.")
    src = Status(w.current_status)
    target = wf.admin_override_target(src, mode)                  # raises if not overridable
    if target is Status.ARCHIVED:
        try:
            files_service.verify_manuscript_integrity(db, w.work_id)
        except DrassError as exc:
            audit(db, admin.user_id, "ARCHIVE_FAILED", "work", w.work_id, "FAILED", exc.message)
            notify_roles(db, ["ADMIN"], "Storage error", f"Archiving blocked for work #{w.work_id}: {exc.message}", "STORAGE", "work", w.work_id)
            db.commit()
            raise
    rn, now = _current_rn(db, w), utcnow()
    stage = wf.OVERRIDABLE[src]
    skipped = []
    for a in db.scalars(select(ReviewAssignment).where(ReviewAssignment.work_id == w.work_id,
                        ReviewAssignment.revision_number == rn, ReviewAssignment.status == "PENDING")).all():
        a.status = "CANCELLED"; skipped.append(a.reviewer_id)
        notify(db, a.reviewer_id, "Review no longer required", f"An administrator approved “{w.title}”; your review is no longer needed.", "REVIEW", "work", w.work_id)
    a = ReviewAssignment(work_id=w.work_id, stage=stage.value, reviewer_id=admin.user_id, revision_number=rn,
                         status="DONE", assigned_at=now, completed_at=now)
    db.add(a); db.flush()
    db.add(Review(assignment_id=a.assignment_id, work_id=w.work_id, reviewer_id=admin.user_id, decision="APPROVE",
                  comments=f"[ADMIN OVERRIDE – {mode}] {reason}", decided_at=now))
    w.current_status, w.version = target.value, w.version + 1
    _history(db, w, src.value, target.value, admin.user_id, f"ADMIN OVERRIDE ({mode}): {reason}")
    audit(db, admin.user_id, "REVIEW_ADMIN_OVERRIDE", "work", w.work_id,
          details=f"{src.value}->{target.value} mode={mode} skipped_reviewers={sorted(set(skipped))} reason={reason[:300]}")
    if target is Status.ARCHIVED:
        w.archived_at = now
        audit(db, admin.user_id, "RESEARCH_ARCHIVED", "work", w.work_id)
        notify(db, w.submitted_by, "Research archived", f"“{w.title}” is now archived (approved by the administrator).", "ARCHIVE", "work", w.work_id)
    else:
        nxt = STAGE_OF_STATUS[target]
        ensure_assignments(db, w, nxt, rn)
        notify(db, w.submitted_by, "Approved", f"“{w.title}” was approved by the administrator and moved to {nxt.value.replace('_', ' ').title()} review.", "REVIEW", "work", w.work_id)
        if nxt is Stage.HEAD_LIBRARIAN:
            notify_roles(db, ["HEAD_LIBRARIAN"], "Work waiting for archive review", f"“{w.title}” awaits final archive review.", "REVIEW", "work", w.work_id)
    db.commit()
    if target is Status.ARCHIVED:
        index_service.index_work(db, w.work_id, admin.user_id)
    return {"work_id": w.work_id, "status": w.current_status, "message": "Approved by administrator."}
