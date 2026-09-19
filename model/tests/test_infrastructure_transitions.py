"""Tests for job state transitions."""

from __future__ import annotations

import pytest

from ssri_model.jobs.exceptions import InvalidJobTransitionError
from ssri_model.jobs.models import JobStatus
from ssri_model.jobs.transitions import validate_transition


def test_valid_transitions() -> None:
    validate_transition(JobStatus.QUEUED, JobStatus.RUNNING)
    validate_transition(JobStatus.RUNNING, JobStatus.COMPLETED)
    validate_transition(JobStatus.RUNNING, JobStatus.QUEUED)
    validate_transition(JobStatus.FAILED, JobStatus.QUEUED)


def test_invalid_transition_raises() -> None:
    with pytest.raises(InvalidJobTransitionError):
        validate_transition(JobStatus.COMPLETED, JobStatus.RUNNING)
