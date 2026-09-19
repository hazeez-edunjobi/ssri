"""Tests for retry classification."""

from __future__ import annotations

from ssri_model.auth.exceptions import AuthenticationError, AuthorizationError
from ssri_model.infrastructure.retry import attempts_remaining, is_retryable_failure
from ssri_model.jobs.exceptions import IdempotencyConflictError
from ssri_model.service.exceptions import (
    InvalidServiceConfigError,
    InvalidServiceRequestError,
    PathSafetyError,
    ScientificGateError,
)


def test_scientific_gate_not_retryable() -> None:
    assert is_retryable_failure(ScientificGateError("blocked")) is False


def test_auth_errors_not_retryable() -> None:
    assert is_retryable_failure(AuthenticationError("bad key")) is False
    assert is_retryable_failure(AuthorizationError("forbidden")) is False


def test_path_and_config_not_retryable() -> None:
    assert is_retryable_failure(PathSafetyError("unsafe path")) is False
    assert is_retryable_failure(InvalidServiceConfigError("bad config")) is False
    assert is_retryable_failure(InvalidServiceRequestError("bad request")) is False
    assert is_retryable_failure(IdempotencyConflictError("conflict")) is False


def test_transient_failures_retryable() -> None:
    assert is_retryable_failure(RuntimeError("connection reset")) is True
    assert is_retryable_failure(OSError("temporary failure")) is True


def test_attempts_remaining_respects_max() -> None:
    assert attempts_remaining(attempt=1, max_attempts=3) is True
    assert attempts_remaining(attempt=3, max_attempts=3) is False
