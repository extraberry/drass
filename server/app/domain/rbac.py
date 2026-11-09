"""Server-side permission matrix (manuscript FR3, Table 13). Enforced by API dependencies."""
from .enums import PublicationStatus, Role, Status
from .errors import Forbidden

R = Role
_READERS = {R.STUDENT, R.FACULTY, R.LIBRARY_STAFF, R.EXTERNAL_USER}
PERMISSIONS: dict[str, set[Role]] = {
    # students
    "submission.create": {R.STUDENT},
    "submission.edit_own": {R.STUDENT},
    # library staff (the Head Librarian additionally verifies - see is_head_librarian on the account)
    "verification.view": {R.LIBRARY_STAFF},
    "verification.act": {R.LIBRARY_STAFF},
    "metadata.maintain": {R.LIBRARY_STAFF},
    "publication.manage": {R.LIBRARY_STAFF},
    "companions.access": {R.LIBRARY_STAFF, R.STUDENT},        # students only for their own work (record-level check)
    # everybody who may use the archive
    "repository.browse": set(_READERS),
    "search.semantic": set(_READERS),
    "reader.read": set(_READERS),
    # administrator
    "users.manage": {R.ADMIN},
    "settings.manage": {R.ADMIN},
    "roster.manage": {R.ADMIN},
    "integrations.manage": {R.ADMIN},
    "audit.read": {R.ADMIN},
    "activity.read": {R.ADMIN},
    "indexing.view": {R.ADMIN},
    "indexing.manage": {R.ADMIN},
    "backup.manage": {R.ADMIN},
    "reports.any": {R.ADMIN},
    "notifications.use": set(R),
}


def can(role: Role, permission: str) -> bool:
    return role in PERMISSIONS.get(permission, set())


def require(role: Role, permission: str) -> None:
    if not can(role, permission):
        raise Forbidden("You do not have permission to perform this action.")


def visible_publication_statuses(role: Role, is_owner: bool = False) -> set[str]:
    """FR10: which publication statuses of ARCHIVED research a role may see.
    PUBLIC: every reader.  RESTRICTED: signed-in Student/Faculty/Library Staff (not External Users).
    UNPUBLISHED: hidden from general users - only Library Staff and the submitting student."""
    P = PublicationStatus
    if role is R.LIBRARY_STAFF:
        return {P.PUBLIC.value, P.RESTRICTED.value, P.UNPUBLISHED.value}
    if role in (R.STUDENT, R.FACULTY):
        out = {P.PUBLIC.value, P.RESTRICTED.value}
        if role is R.STUDENT and is_owner:
            out.add(P.UNPUBLISHED.value)
        return out
    if role is R.EXTERNAL_USER:
        return {P.PUBLIC.value}
    return set()                                   # the Administrator does not read research


def can_view_work(role: Role, user_id, work_status: Status, submitted_by: int,
                  publication_status: str | None = None) -> bool:
    """Record-level visibility."""
    is_owner = user_id is not None and submitted_by == user_id
    if work_status is Status.ARCHIVED:
        return (publication_status or "") in visible_publication_statuses(role, is_owner)
    if role is R.LIBRARY_STAFF:                    # may open pending / returned submissions to check completeness
        return work_status is not Status.DRAFT
    if role is R.STUDENT:
        return is_owner
    return False


def can_access_companions(role: Role, user_id, submitted_by: int) -> bool:
    """FR15: companion files (source code, videos) are for Library Staff and the owning student only."""
    return role is R.LIBRARY_STAFF or (role is R.STUDENT and user_id is not None and submitted_by == user_id)
