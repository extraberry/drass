"""Workflow engine: the only place status changes are decided (manuscript FR4-FR8, Figures 6-7).

Student submits ONE final PDF (manuscript + completed approval sheet)  ->  PENDING_VERIFICATION
Head Librarian checks the signatory checklist (Adviser, Panelists, Dean, Researchers + approval sheet):
    incomplete  -> RETURNED with remarks; the student corrects and resubmits  -> PENDING_VERIFICATION
    complete    -> final archival approval -> ARCHIVED (with a publication status)
The Adviser, Panelists and Dean sign OUTSIDE the system; DRASS records no academic evaluation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .enums import Decision, PublicationStatus, Status
from .errors import InvalidTransition, StaleState, ValidationFailed

S = Status
TRANSITIONS: dict[Status, set[Status]] = {
    S.DRAFT: {S.PENDING_VERIFICATION},
    S.PENDING_VERIFICATION: {S.ARCHIVED, S.RETURNED},
    S.RETURNED: {S.PENDING_VERIFICATION},
    S.ARCHIVED: set(),
}
EDITABLE = {S.DRAFT, S.RETURNED}

# FR6: the checklist the Head Librarian completes.  key -> label shown on screen.
CHECKLIST_ITEMS = {
    "adviser_signed": "Adviser has signed",
    "panelists_signed": "Panelists have signed",
    "dean_signed": "Dean has signed",
    "researchers_signed": "Researchers have signed",
    "sheet_complete": "Approval sheet and required documents are complete",
}


def assert_transition(src: Status, dst: Status) -> None:
    if dst not in TRANSITIONS[src]:
        raise InvalidTransition(f"Cannot change status from {src.value} to {dst.value}.")


@dataclass
class Work:
    work_id: int
    status: Status
    version: int = 0                      # optimistic lock


@dataclass
class Outcome:
    new_status: Status
    reason: str
    publication_status: Optional[PublicationStatus] = None


def missing_items(checklist: dict) -> list[str]:
    """Labels of the checklist items that are not ticked."""
    return [label for key, label in CHECKLIST_ITEMS.items() if not bool(checklist.get(key))]


def submit(work: Work) -> Status:
    assert_transition(work.status, Status.PENDING_VERIFICATION)
    work.status = Status.PENDING_VERIFICATION
    work.version += 1
    return work.status


def resubmit(work: Work) -> Status:
    if work.status is not Status.RETURNED:
        raise InvalidTransition("Only returned research can be resubmitted.")
    return submit(work)


def verify(work: Work, decision: Decision, checklist: dict, remarks: str = "",
           publication_status: Optional[str] = None, expected_version: Optional[int] = None) -> Outcome:
    """Apply the Head Librarian's verification. APPROVE needs every checklist item ticked (FR5) and gives the work
    a publication status; RETURN needs remarks (FR6). Raises on any rule violation without changing `work`."""
    if expected_version is not None and expected_version != work.version:
        raise StaleState("This record changed since you opened it. Please reload.")
    if work.status is not Status.PENDING_VERIFICATION:
        raise InvalidTransition("This submission is not awaiting verification.")
    remarks = (remarks or "").strip()
    if decision is Decision.RETURN:
        if not remarks:
            raise ValidationFailed("Remarks are required when returning a submission.", {"remarks": "Required."})
        assert_transition(work.status, Status.RETURNED)
        work.status = Status.RETURNED
        work.version += 1
        return Outcome(Status.RETURNED, remarks)
    if decision is Decision.APPROVE:
        missing = missing_items(checklist)
        if missing:
            raise ValidationFailed("Final approval needs every checklist item verified. Missing: " + "; ".join(missing) +
                                   ". Return the submission with remarks instead.", {"checklist": "Incomplete."})
        try:
            pub = PublicationStatus(publication_status or PublicationStatus.PUBLIC.value)
        except ValueError:
            raise ValidationFailed("Choose a valid publication status.", {"publication_status": "Invalid."})
        assert_transition(work.status, Status.ARCHIVED)
        work.status = Status.ARCHIVED
        work.version += 1
        return Outcome(Status.ARCHIVED, remarks or "Verified and archived.", pub)
    raise ValidationFailed("Unknown decision.")
