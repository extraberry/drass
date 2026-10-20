"""Workflow engine: the only place status changes are decided (PRD s12-14, s34)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .enums import Decision, Stage, Status
from .errors import Forbidden, InvalidTransition, StaleState, ValidationFailed

S = Status
TRANSITIONS: dict[Status, set[Status]] = {
    S.DRAFT: {S.SUBMITTED},
    S.SUBMITTED: {S.UNDER_ADVISER_REVIEW},
    S.UNDER_ADVISER_REVIEW: {S.UNDER_PANEL_REVIEW, S.RETURNED_FOR_REVISION, S.REJECTED},
    S.UNDER_PANEL_REVIEW: {S.UNDER_DEAN_REVIEW, S.RETURNED_FOR_REVISION, S.REJECTED},
    S.UNDER_DEAN_REVIEW: {S.UNDER_HEAD_LIBRARIAN_REVIEW, S.RETURNED_FOR_REVISION, S.REJECTED},
    S.UNDER_HEAD_LIBRARIAN_REVIEW: {S.ARCHIVED, S.RETURNED_FOR_REVISION, S.REJECTED},
    S.RETURNED_FOR_REVISION: {S.UNDER_ADVISER_REVIEW},
    S.REJECTED: set(),
    S.ARCHIVED: set(),
}
STAGE_STATUS = {
    Stage.ADVISER: S.UNDER_ADVISER_REVIEW, Stage.PANEL: S.UNDER_PANEL_REVIEW,
    Stage.DEAN: S.UNDER_DEAN_REVIEW, Stage.HEAD_LIBRARIAN: S.UNDER_HEAD_LIBRARIAN_REVIEW,
}
NEXT_ON_APPROVE = {
    Stage.ADVISER: S.UNDER_PANEL_REVIEW, Stage.PANEL: S.UNDER_DEAN_REVIEW,
    Stage.DEAN: S.UNDER_HEAD_LIBRARIAN_REVIEW, Stage.HEAD_LIBRARIAN: S.ARCHIVED,
}


def assert_transition(src: Status, dst: Status) -> None:
    if dst not in TRANSITIONS[src]:
        raise InvalidTransition(f"Cannot change status from {src.value} to {dst.value}.")


@dataclass
class Assignment:
    reviewer_id: int
    stage: Stage
    decision: Optional[Decision] = None   # None == pending


@dataclass
class Work:
    work_id: int
    status: Status
    version: int = 0                       # optimistic lock (PRD s34)
    assignments: list[Assignment] = field(default_factory=list)


@dataclass
class Outcome:
    new_status: Status
    stage_complete: bool
    reason: str


def submit(work: Work) -> Status:
    assert_transition(work.status, Status.SUBMITTED)
    work.status = Status.SUBMITTED
    work.version += 1
    assert_transition(work.status, Status.UNDER_ADVISER_REVIEW)  # auto-route to adviser
    work.status = Status.UNDER_ADVISER_REVIEW
    return work.status


def resubmit(work: Work) -> Status:
    if work.status is not Status.RETURNED_FOR_REVISION:
        raise InvalidTransition("Only returned research can be resubmitted.")
    for a in work.assignments:             # fresh round; old reviews stay in history tables
        a.decision = None
    assert_transition(work.status, Status.UNDER_ADVISER_REVIEW)
    work.status = Status.UNDER_ADVISER_REVIEW
    work.version += 1
    return work.status


def offline_panel_target(skip_dean: bool) -> Status:
    """Where an adviser approval goes when the panel already approved OUTSIDE the system (e.g. a signed letter).
    The panel stage is skipped; the Dean stage is skipped too when `skip_dean` (admin setting, default on)."""
    return S.UNDER_HEAD_LIBRARIAN_REVIEW if skip_dean else S.UNDER_DEAN_REVIEW


def review(work: Work, reviewer_id: int, stage: Stage, decision: Decision,
           comments: str = "", expected_version: Optional[int] = None,
           panel_offline_to: Optional[Status] = None) -> Outcome:
    """Apply one review decision. Panel stage requires ALL_ASSIGNED approvals.
    `panel_offline_to` (adviser APPROVE only) records that the panel approved offline and jumps past the panel stage."""
    if panel_offline_to is not None:
        if stage is not Stage.ADVISER or decision is not Decision.APPROVE:
            raise ValidationFailed("Offline panel approval can only be recorded with an adviser approval.")
        if panel_offline_to not in (S.UNDER_DEAN_REVIEW, S.UNDER_HEAD_LIBRARIAN_REVIEW):
            raise ValidationFailed("Invalid destination for offline panel approval.")
    if expected_version is not None and expected_version != work.version:
        raise StaleState("This record changed since you opened it. Please reload.")
    if work.status is not STAGE_STATUS[stage]:
        raise InvalidTransition(f"Work is not awaiting {stage.value} review.")
    mine = next((a for a in work.assignments
                 if a.stage is stage and a.reviewer_id == reviewer_id), None)
    if mine is None:
        raise Forbidden("You are not assigned to review this work.")
    if mine.decision is not None:
        raise StaleState("You have already submitted a decision for this stage.")
    comments = (comments or "").strip()
    if decision is Decision.REJECT and not comments:
        raise ValidationFailed("A reason is required to reject research.")
    if decision is Decision.RETURN and not comments:
        raise ValidationFailed("Comments are required when returning for revision.")

    mine.decision = decision
    work.version += 1
    if decision is Decision.REJECT:
        assert_transition(work.status, Status.REJECTED)
        work.status = Status.REJECTED
        return Outcome(work.status, True, comments)
    if decision is Decision.RETURN:
        assert_transition(work.status, Status.RETURNED_FOR_REVISION)
        work.status = Status.RETURNED_FOR_REVISION
        return Outcome(work.status, True, comments)

    stage_assignments = [a for a in work.assignments if a.stage is stage]
    if any(a.decision is not Decision.APPROVE for a in stage_assignments):
        return Outcome(work.status, False, "Awaiting remaining approvals.")
    if panel_offline_to is not None:                      # explicit, audited shortcut; panel assignments are never created
        work.status = panel_offline_to
        return Outcome(panel_offline_to, True, "Adviser approved; panel approval recorded offline.")
    nxt = NEXT_ON_APPROVE[stage]
    assert_transition(work.status, nxt)
    work.status = nxt
    return Outcome(nxt, True, "Stage approved.")


OVERRIDABLE = {S.UNDER_ADVISER_REVIEW: Stage.ADVISER, S.UNDER_PANEL_REVIEW: Stage.PANEL,
               S.UNDER_DEAN_REVIEW: Stage.DEAN, S.UNDER_HEAD_LIBRARIAN_REVIEW: Stage.HEAD_LIBRARIAN}


def admin_override_target(status: Status, mode: str) -> Status:
    """Administrator approval without waiting for the pending reviewers.
    mode 'next'    -> approve the current stage and move to the following stage;
    mode 'archive' -> approve everything that remains and archive now.
    Only works under review can be overridden; this never edits earlier review decisions."""
    if status not in OVERRIDABLE:
        raise InvalidTransition("Only research that is under review can be approved by an administrator.")
    if mode == "archive":
        return S.ARCHIVED
    if mode == "next":
        return NEXT_ON_APPROVE[OVERRIDABLE[status]]
    raise ValidationFailed("Override mode must be 'next' or 'archive'.")
