"""Auth, lookups, notifications, dashboard, submissions, reviews."""
import hashlib
import os
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..core.deps import bearer_token, current_user, require, role_of
from ..db import get_db
from ..domain import rbac
from ..domain.enums import Decision, FileType, Role, Status
from ..domain.errors import Forbidden, NotFound, ValidationFailed
from ..domain.file_validation import new_stored_name, sanitize_filename, validate_upload
from ..models import Notification, ResearchWork, Revision, StatusHistory, User
from ..schemas.schemas import (LoginIn, PanelIn, PasswordChangeIn, ProfilePatchIn, ResubmitIn, ReviewActionIn,
                               SubmissionIn)
from ..services import (admin_service, auth_service, files_service, review_service, submission_service)
from ..services.common import audit, get_setting
from ..services.repository_service import get_work_for_user
from ..services.serializers import STATUS_LABELS, user_dict, work_dict

router = APIRouter()


# ---------- auth ----------
@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    token, user = auth_service.login(db, body.username, body.password)
    return {"success": True, "token": token, "user": user_dict(user)}


@router.post("/auth/logout")
def logout(token: str = Depends(bearer_token), user: User = Depends(current_user), db: Session = Depends(get_db)):
    auth_service.logout(db, token, user)
    return {"success": True}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return user_dict(user)


@router.patch("/auth/me")
def patch_me(body: ProfilePatchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = body.model_dump(exclude_unset=True)
    if d.get("email") and db.scalar(select(User).where(User.email == d["email"], User.user_id != user.user_id)):
        raise ValidationFailed("That email is already in use.", {"email": "Already in use."})
    for k, v in d.items():
        if v:
            setattr(user, k, v)
    audit(db, user.user_id, "PROFILE_UPDATED", "user", user.user_id)
    db.commit()
    return user_dict(user)


@router.post("/auth/change-password")
def change_password(body: PasswordChangeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    auth_service.change_password(db, user, body.old_password, body.new_password)
    return {"success": True}


# ---------- lookups / dashboard / notifications ----------
@router.get("/lookups")
def lookups(user: User = Depends(current_user), db: Session = Depends(get_db)):
    advisers = db.scalars(select(User).where(User.status == "ACTIVE", User.role.has(role_name="ADVISER"))).all()
    panelists = db.scalars(select(User).where(User.status == "ACTIVE", User.role.has(role_name="PANELIST"))).all()
    return {"departments": admin_service.lookup_rows(db, "departments"), "programs": admin_service.lookup_rows(db, "programs"),
            "categories": admin_service.lookup_rows(db, "categories"),
            "advisers": [{"id": a.user_id, "name": a.full_name, "department_id": a.department_id} for a in advisers],
            "panelists": [{"id": a.user_id, "name": a.full_name} for a in panelists],
            "statuses": [{"id": k, "name": v} for k, v in STATUS_LABELS.items()],
            "roles": [r.value for r in Role]}


@router.get("/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return admin_service.dashboard(db, user)


@router.get("/notifications")
def notifications(unread_only: bool = False, limit: int = Query(50, ge=1, le=200),
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Notification).where(Notification.user_id == user.user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    rows = db.scalars(stmt.order_by(Notification.created_at.desc()).limit(limit)).all()
    return {"items": [{"notification_id": n.notification_id, "title": n.title, "message": n.message, "type": n.type,
                       "target_type": n.target_type, "target_id": n.target_id, "is_read": n.is_read,
                       "created_at": n.created_at.isoformat()} for n in rows],
            "unread": db.scalar(select(func.count()).select_from(Notification).where(
                Notification.user_id == user.user_id, Notification.is_read.is_(False))) or 0}


@router.post("/notifications/{nid}/read")
def read_notification(nid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if n is None or n.user_id != user.user_id:
        raise NotFound("Notification not found.")
    n.is_read = True
    db.commit()
    return {"success": True}


@router.post("/notifications/read-all")
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    for n in db.scalars(select(Notification).where(Notification.user_id == user.user_id, Notification.is_read.is_(False))).all():
        n.is_read = True
    db.commit()
    return {"success": True}


# ---------- submissions ----------
def _detail(db: Session, user: User, w: ResearchWork) -> dict:
    d = work_dict(db, w)
    is_owner = w.submitted_by == user.user_id
    if is_owner or user.role.role_name == "ADMIN":
        d["review_history"] = review_service.work_review_history(db, w.work_id)
        d["revisions"] = [{"revision_number": r.revision_number, "change_notes": r.change_notes,
                           "created_at": r.created_at.isoformat()} for r in
                          db.scalars(select(Revision).where(Revision.work_id == w.work_id).order_by(Revision.revision_number)).all()]
        d["status_history"] = [{"from": h.from_status, "to": h.to_status, "reason": h.reason, "at": h.created_at.isoformat()}
                               for h in db.scalars(select(StatusHistory).where(StatusHistory.work_id == w.work_id).order_by(StatusHistory.history_id)).all()]
    return d


@router.get("/submissions")
def my_submissions(user: User = Depends(require("submission.create")), db: Session = Depends(get_db)):
    return {"items": submission_service.list_own(db, user)}


@router.post("/submissions")
def create_submission(body: SubmissionIn, user: User = Depends(require("submission.create")), db: Session = Depends(get_db)):
    w = submission_service.create_draft(db, user, body.model_dump(exclude_unset=True))
    db.commit()
    return _detail(db, user, w)


@router.get("/submissions/{work_id}")
def get_submission(work_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    w = get_work_for_user(db, user, work_id)
    return _detail(db, user, w)


@router.patch("/submissions/{work_id}")
def patch_submission(work_id: int, body: SubmissionIn, user: User = Depends(require("submission.edit_own")),
                     db: Session = Depends(get_db)):
    w = submission_service.update(db, user, work_id, body.model_dump(exclude_unset=True))
    db.commit()
    return _detail(db, user, w)


@router.post("/submissions/{work_id}/submit")
def submit_submission(work_id: int, user: User = Depends(require("submission.create")), db: Session = Depends(get_db)):
    w = submission_service.submit(db, user, work_id)
    db.commit()
    return _detail(db, user, w)


@router.post("/submissions/{work_id}/resubmit")
def resubmit_submission(work_id: int, body: ResubmitIn, user: User = Depends(require("submission.create")),
                        db: Session = Depends(get_db)):
    w = submission_service.resubmit(db, user, work_id, body.change_notes)
    db.commit()
    return _detail(db, user, w)


@router.post("/submissions/{work_id}/panel")
def assign_panel(work_id: int, body: PanelIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    w = db.get(ResearchWork, work_id)
    if w is None:
        raise NotFound("Research not found.")
    r = role_of(user)
    if not (r is Role.ADMIN or (r is Role.ADVISER and w.adviser_id == user.user_id)):
        audit(db, user.user_id, "PERMISSION_DENIED", "work", work_id, "DENIED", "panel assignment")
        db.commit()
        raise Forbidden("You do not have permission to assign the panel.")
    submission_service.set_panel(db, user, w, body.panelist_ids)
    db.commit()
    return {"success": True}


@router.put("/submissions/{work_id}/files/{file_type}")
async def upload_file(work_id: int, file_type: FileType, request: Request, filename: str = Query(..., max_length=255),
                      user: User = Depends(require("submission.edit_own")), db: Session = Depends(get_db)):
    """Streamed upload (raw body). Validates size/signature, writes atomically, cleans up on any failure."""
    w = submission_service.get_owned_editable(db, user, work_id)
    files_service.ensure_dirs()
    limit_mb = get_setting(db, "max_manuscript_mb" if file_type is FileType.MANUSCRIPT else "max_companion_mb")
    tmp, final = files_service.temp_path(), None
    try:
        size, head, h = 0, b"", hashlib.sha256()
        with open(tmp, "wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit_mb * 1024 * 1024:
                    raise ValidationFailed(f"File exceeds the {limit_mb} MB limit.")
                if len(head) < 64:
                    head += chunk[: 64 - len(head)]
                h.update(chunk)
                f.write(chunk)
        clean = sanitize_filename(filename)
        ext = validate_upload(file_type, clean, head, size, {file_type: limit_mb})
        if file_type is FileType.MANUSCRIPT:
            try:
                import fitz
                with fitz.open(str(tmp)) as doc:
                    if doc.page_count < 1:
                        raise ValueError("no pages")
            except ImportError:
                pass
            except Exception:   # noqa: BLE001
                raise ValidationFailed("The PDF appears to be corrupted or unreadable.")
        stored = new_stored_name(ext)
        final = files_service.dest_path(file_type, stored)
        os.replace(tmp, final)                                    # atomic placement
        rec, replaced = files_service.add_record(db, w.work_id, w.current_revision_id, file_type, clean, stored, size, h.hexdigest(), user.user_id)
        audit(db, user.user_id, "FILE_REPLACED" if replaced else "FILE_UPLOADED", "work", w.work_id, details=f"{file_type.value} {size}B")
        db.commit()
        return {"file_id": rec.file_id, "file_type": rec.file_type, "filename": rec.original_filename, "size_bytes": size}
    except BaseException:
        db.rollback()
        for p in (tmp, final):
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        raise


# ---------- reviews ----------
@router.get("/reviews/queue")
def review_queue(user: User = Depends(require("review.act")), db: Session = Depends(get_db)):
    return {"items": review_service.queue(db, user)}


@router.get("/reviews/history")
def review_history(user: User = Depends(require("review.act")), db: Session = Depends(get_db)):
    return {"items": review_service.history_for_reviewer(db, user)}


@router.get("/reviews/{assignment_id}")
def review_detail(assignment_id: int, user: User = Depends(require("review.act")), db: Session = Depends(get_db)):
    return review_service.get_detail(db, user, assignment_id)


def _decide(decision: Decision):
    def handler(assignment_id: int, body: ReviewActionIn, user: User = Depends(require("review.act")),
                db: Session = Depends(get_db)):
        return review_service.act(db, user, assignment_id, decision, body.comments, body.expected_version)
    return handler


router.add_api_route("/reviews/{assignment_id}/approve", _decide(Decision.APPROVE), methods=["POST"])
router.add_api_route("/reviews/{assignment_id}/return", _decide(Decision.RETURN), methods=["POST"])
router.add_api_route("/reviews/{assignment_id}/reject", _decide(Decision.REJECT), methods=["POST"])
