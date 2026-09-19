"""Retry classification for distributed job execution."""

from __future__ import annotations

from ssri_model.auth.exceptions import AuthenticationError, AuthorizationError
from ssri_model.jobs.exceptions import IdempotencyConflictError
from ssri_model.service.exceptions import (
    InvalidServiceConfigError,
    InvalidServiceRequestError,
    PathSafetyError,
    ScientificGateError,
)

_NON_RETRYABLE = (
    AuthenticationError,
    AuthorizationError,
    ScientificGateError,
    PathSafetyError,
    InvalidServiceRequestError,
    InvalidServiceConfigError,
    IdempotencyConflictError,
    ValueError,
    TypeError,
)


def is_retryable_failure(exc: BaseException) -> bool:
    """Return True when an infrastructure/transient failure may be retried."""
    return not isinstance(exc, _NON_RETRYABLE)


def attempts_remaining(*, attempt: int, max_attempts: int) -> bool:
    """Return True when another execution attempt is allowed."""
    return attempt < max_attempts
