"""Explicit job state transition rules."""

from __future__ import annotations

from ssri_model.jobs.exceptions import InvalidJobTransitionError
from ssri_model.jobs.models import JobStatus

_VALID_TRANSITIONS: frozenset[tuple[JobStatus, JobStatus]] = frozenset(
    {
        (JobStatus.QUEUED, JobStatus.RUNNING),
        (JobStatus.QUEUED, JobStatus.CANCELLED),
        (JobStatus.RUNNING, JobStatus.COMPLETED),
        (JobStatus.RUNNING, JobStatus.FAILED),
        (JobStatus.RUNNING, JobStatus.CANCELLED),
        (JobStatus.RUNNING, JobStatus.QUEUED),
        (JobStatus.FAILED, JobStatus.QUEUED),
    }
)

_TERMINAL: frozenset[JobStatus] = frozenset(
    {JobStatus.COMPLETED, JobStatus.CANCELLED}
)


def is_terminal(status: JobStatus) -> bool:
    return status in _TERMINAL


def validate_transition(current: JobStatus, target: JobStatus) -> None:
    """Raise InvalidJobTransitionError when a transition is not permitted."""
    if current == target:
        return
    if (current, target) not in _VALID_TRANSITIONS:
        raise InvalidJobTransitionError(
            f"Invalid job transition from {current.value} to {target.value}"
        )
