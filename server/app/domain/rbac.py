"""Server-side permission matrix (PRD s5-6, s61). Enforced by API dependencies."""
from .enums import Role, Status
from .errors import Forbidden

R = Role
PERMISSIONS: dict[str, set[Role]] = {
    "submission.create": {R.STUDENT},
    "submission.edit_own": {R.STUDENT},
    "review.act": {R.ADVISER, R.PANELIST, R.DEAN, R.HEAD_LIBRARIAN},
    "repository.browse": {R.STUDENT, R.ADVISER, R.PANELIST, R.DEAN, R.LIBRARY_STAFF,
                          R.HEAD_LIBRARIAN, R.ADMIN, R.EXTERNAL_USER},
    "search.semantic": {R.STUDENT, R.ADVISER, R.PANELIST, R.DEAN, R.LIBRARY_STAFF,
                        R.HEAD_LIBRARIAN, R.ADMIN, R.EXTERNAL_USER},
    "reader.read": {R.STUDENT, R.ADVISER, R.PANELIST, R.DEAN, R.LIBRARY_STAFF,
                    R.HEAD_LIBRARIAN, R.ADMIN, R.EXTERNAL_USER},
    "metadata.maintain": {R.LIBRARY_STAFF, R.HEAD_LIBRARIAN, R.ADMIN},
    "users.manage": {R.ADMIN},
    "settings.manage": {R.ADMIN},
    "audit.read": {R.ADMIN},
    "indexing.manage": {R.ADMIN},
    "indexing.view": {R.ADMIN, R.HEAD_LIBRARIAN, R.LIBRARY_STAFF},
    "activity.read": {R.ADMIN},
    "reports.any": {R.STUDENT, R.ADVISER, R.PANELIST, R.DEAN, R.LIBRARY_STAFF, R.HEAD_LIBRARIAN, R.ADMIN},
    "notifications.use": set(R),
    "reports.library": {R.LIBRARY_STAFF, R.HEAD_LIBRARIAN, R.ADMIN},
    "reports.department": {R.DEAN, R.ADMIN},
    "reports.all": {R.ADMIN},
}
REVIEWER_STAGE_ROLE = {"ADVISER": R.ADVISER, "PANEL": R.PANELIST,
                       "DEAN": R.DEAN, "HEAD_LIBRARIAN": R.HEAD_LIBRARIAN}


def can(role: Role, permission: str) -> bool:
    return role in PERMISSIONS.get(permission, set())


def require(role: Role, permission: str) -> None:
    if not can(role, permission):
        raise Forbidden("You do not have permission to perform this action.")


def can_view_work(role: Role, user_id: int, work_status: Status,
                  submitted_by: int, assigned_reviewer_ids: set[int]) -> bool:
    """Record-level visibility. ARCHIVED is the only status visible to everyone."""
    if work_status is Status.ARCHIVED:
        return True
    if role is Role.EXTERNAL_USER:
        return False
    if role is Role.ADMIN:
        return True
    if role is Role.STUDENT:
        return submitted_by == user_id
    if role in (Role.ADVISER, Role.PANELIST, Role.DEAN, Role.HEAD_LIBRARIAN):
        return user_id in assigned_reviewer_ids and work_status is not Status.DRAFT
    return False   # LIBRARY_STAFF: archived only
