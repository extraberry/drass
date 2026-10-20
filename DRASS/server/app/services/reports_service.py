"""Seven required reports, RBAC-scoped (PRD s30, s63)."""
import csv
import io
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from ..domain.errors import Forbidden, ValidationFailed
from ..models import (ActivityLog, AuditLog, Department, Program, ResearchWork, Review, ReviewAssignment,
                      Role as RoleModel, User)
from ..core.timeutil import utcnow
from .common import activity
from .serializers import STATUS_LABELS

KINDS = ("submissions", "approvals", "rejections", "pending-reviews", "archived", "user-activity", "system-activity")
ADMIN_ONLY = {"user-activity", "system-activity"}
MAX_ROWS = 5000


def _date(s, end=False):
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise ValidationFailed("Dates must use YYYY-MM-DD.")
    return d + timedelta(days=1) if end else d


def _scope(db: Session, user: User):
    """SQL condition limiting which works a role may see in reports."""
    r = user.role.role_name
    if r in ("ADMIN", "LIBRARY_STAFF", "HEAD_LIBRARIAN"):
        return None
    if r == "DEAN":
        return ResearchWork.department_id == user.department_id
    if r == "ADVISER":
        return ResearchWork.adviser_id == user.user_id
    if r == "PANELIST":
        return ResearchWork.work_id.in_(select(ReviewAssignment.work_id).where(ReviewAssignment.reviewer_id == user.user_id))
    if r == "STUDENT":
        return ResearchWork.submitted_by == user.user_id
    raise Forbidden("You do not have permission to view reports.")


def _name(db, model, pk, col):
    o = db.get(model, pk) if pk else None
    return getattr(o, col) if o else ""


def run(db: Session, user: User, kind: str, f: dict) -> dict:
    if kind not in KINDS:
        raise ValidationFailed("Unknown report.")
    if kind in ADMIN_ONLY and user.role.role_name != "ADMIN":
        raise Forbidden("You do not have permission to view this report.")
    scope = _scope(db, user)
    d_from, d_to = _date(f.get("date_from")), _date(f.get("date_to"), end=True)
    fn = globals()["_" + kind.replace("-", "_")]
    cols, rows = fn(db, scope, f, d_from, d_to)
    activity(db, user.user_id, "REPORT_VIEWED", "report", None, kind)
    db.commit()
    return {"report": kind, "columns": cols, "rows": rows[:MAX_ROWS], "count": len(rows)}


def _work_filters(stmt, scope, f):
    if scope is not None:
        stmt = stmt.where(scope)
    for k in ("program_id", "department_id"):
        if f.get(k):
            stmt = stmt.where(getattr(ResearchWork, k) == int(f[k]))
    if f.get("status"):
        stmt = stmt.where(ResearchWork.current_status == f["status"])
    return stmt


def _submissions(db, scope, f, d_from, d_to):
    stmt = _work_filters(select(ResearchWork).where(ResearchWork.submitted_at.is_not(None)), scope, f)
    if d_from: stmt = stmt.where(ResearchWork.submitted_at >= d_from)
    if d_to: stmt = stmt.where(ResearchWork.submitted_at < d_to)
    cols = ["Reference", "Title", "Submitted by", "Program", "Department", "Status", "Submitted at"]
    return cols, [[w.reference_no, w.title, _name(db, User, w.submitted_by, "full_name"),
                   _name(db, Program, w.program_id, "program_name"), _name(db, Department, w.department_id, "department_name"),
                   STATUS_LABELS.get(w.current_status), w.submitted_at.isoformat(timespec="minutes")]
                  for w in db.scalars(stmt.order_by(ResearchWork.submitted_at.desc())).all()]


def _approvals(db, scope, f, d_from, d_to):
    stmt = (select(Review, ReviewAssignment, ResearchWork).join(ReviewAssignment, ReviewAssignment.assignment_id == Review.assignment_id)
            .join(ResearchWork, ResearchWork.work_id == Review.work_id).where(Review.decision == "APPROVE"))
    stmt = _work_filters(stmt, scope, {k: v for k, v in f.items() if k != "status"})
    if f.get("stage"): stmt = stmt.where(ReviewAssignment.stage == f["stage"])
    if d_from: stmt = stmt.where(Review.decided_at >= d_from)
    if d_to: stmt = stmt.where(Review.decided_at < d_to)
    cols = ["Reference", "Title", "Stage", "Reviewer", "Decided at"]
    return cols, [[w.reference_no, w.title, a.stage, _name(db, User, r.reviewer_id, "full_name"),
                   r.decided_at.isoformat(timespec="minutes")] for r, a, w in db.execute(stmt.order_by(Review.decided_at.desc())).all()]


def _rejections(db, scope, f, d_from, d_to):
    stmt = (select(Review, ResearchWork).join(ResearchWork, ResearchWork.work_id == Review.work_id).where(Review.decision == "REJECT"))
    stmt = _work_filters(stmt, scope, {k: v for k, v in f.items() if k != "status"})
    if d_from: stmt = stmt.where(Review.decided_at >= d_from)
    if d_to: stmt = stmt.where(Review.decided_at < d_to)
    cols = ["Reference", "Title", "Rejected by", "Reason", "Decided at"]
    return cols, [[w.reference_no, w.title, _name(db, User, r.reviewer_id, "full_name"), r.comments,
                   r.decided_at.isoformat(timespec="minutes")] for r, w in db.execute(stmt.order_by(Review.decided_at.desc())).all()]


def _pending_reviews(db, scope, f, d_from, d_to):
    stmt = (select(ReviewAssignment, ResearchWork).join(ResearchWork, ResearchWork.work_id == ReviewAssignment.work_id)
            .where(ReviewAssignment.status == "PENDING"))
    stmt = _work_filters(stmt, scope, {k: v for k, v in f.items() if k != "status"})
    if f.get("stage"): stmt = stmt.where(ReviewAssignment.stage == f["stage"])
    if d_from: stmt = stmt.where(ReviewAssignment.assigned_at >= d_from)
    if d_to: stmt = stmt.where(ReviewAssignment.assigned_at < d_to)
    now = utcnow()
    cols = ["Reference", "Title", "Stage", "Reviewer", "Assigned at", "Days waiting"]
    rows = []
    for a, w in db.execute(stmt.order_by(ReviewAssignment.assigned_at)).all():
        if w.current_status.startswith("UNDER_"):
            rows.append([w.reference_no, w.title, a.stage, _name(db, User, a.reviewer_id, "full_name"),
                         a.assigned_at.isoformat(timespec="minutes"), (now - a.assigned_at).days])
    return cols, rows


def _archived(db, scope, f, d_from, d_to):
    stmt = _work_filters(select(ResearchWork).where(ResearchWork.current_status == "ARCHIVED"), scope,
                         {k: v for k, v in f.items() if k != "status"})
    if d_from: stmt = stmt.where(ResearchWork.archived_at >= d_from)
    if d_to: stmt = stmt.where(ResearchWork.archived_at < d_to)
    cols = ["Reference", "Title", "Year", "Program", "Department", "Archived at"]
    return cols, [[w.reference_no, w.title, w.year, _name(db, Program, w.program_id, "program_name"),
                   _name(db, Department, w.department_id, "department_name"),
                   w.archived_at.isoformat(timespec="minutes") if w.archived_at else ""]
                  for w in db.scalars(stmt.order_by(ResearchWork.archived_at.desc())).all()]


def _user_activity(db, scope, f, d_from, d_to):
    stmt = select(AuditLog, User).outerjoin(User, User.user_id == AuditLog.user_id)
    if f.get("user_id"): stmt = stmt.where(AuditLog.user_id == int(f["user_id"]))
    if f.get("role"):
        stmt = stmt.join(RoleModel, RoleModel.role_id == User.role_id).where(RoleModel.role_name == f["role"])
    if d_from: stmt = stmt.where(AuditLog.timestamp >= d_from)
    if d_to: stmt = stmt.where(AuditLog.timestamp < d_to)
    cols = ["Time", "User", "Action", "Target", "Result", "Details"]
    return cols, [[a.timestamp.isoformat(timespec="seconds"), u.username if u else "(anonymous)", a.action,
                   f"{a.target_type or ''} {a.target_id or ''}".strip(), a.result, a.details]
                  for a, u in db.execute(stmt.order_by(AuditLog.timestamp.desc()).limit(MAX_ROWS)).all()]


def _system_activity(db, scope, f, d_from, d_to):
    stmt = select(ActivityLog, User).outerjoin(User, User.user_id == ActivityLog.user_id)
    if f.get("user_id"): stmt = stmt.where(ActivityLog.user_id == int(f["user_id"]))
    if d_from: stmt = stmt.where(ActivityLog.timestamp >= d_from)
    if d_to: stmt = stmt.where(ActivityLog.timestamp < d_to)
    cols = ["Time", "User", "Event", "Target", "Details"]
    return cols, [[a.timestamp.isoformat(timespec="seconds"), u.username if u else "", a.event_type,
                   f"{a.target_type or ''} {a.target_id or ''}".strip(), a.details]
                  for a, u in db.execute(stmt.order_by(ActivityLog.timestamp.desc()).limit(MAX_ROWS)).all()]


def to_csv(result: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(result["columns"])
    for row in result["rows"]:
        w.writerow(["'" + c if isinstance(c, str) and c[:1] in "=+-@" else c for c in row])   # CSV-injection guard
    return buf.getvalue()
