"""Retry classification for distributed job execution."""

from __future__ import annotations

from ssri_model.auth.exceptions import AuthenticationError, AuthorizationError
from ssri_model.inference.exceptions import (
    InferenceAlignmentError,
    InferenceCheckpointError,
    InferenceInputError,
    InvalidInferenceConfigError,
)
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
    InferenceInputError,
    InferenceCheckpointError,
    InferenceAlignmentError,
    InvalidInferenceConfigError,
    ValueError,
    TypeError,
)

# Job-store error codes that must not be requeued after mark_failed.
# Keep this list narrow — transient INFERENCE_FAILED / JOB_EXECUTION_FAILED may retry.
_NON_RETRYABLE_ERROR_CODES = frozenset(
    {
        "INFERENCE_INPUT_INVALID",
        "INFERENCE_CHECKPOINT_INVALID",
        "INFERENCE_CONFIG_INVALID",
        "NON_RETRYABLE_FAILURE",
        "PLATFORM_NOT_CONFIGURED",
        "DATASET_VALIDATION_FAILED",
    }
)


def is_retryable_error_code(error_code: str | None) -> bool:
    """Return False for permanent application/input failures recorded on the job."""
    if not error_code:
        return True
    return error_code not in _NON_RETRYABLE_ERROR_CODES



def is_retryable_failure(exc: BaseException) -> bool:
    """Return True when an infrastructure/transient failure may be retried."""
    return not isinstance(exc, _NON_RETRYABLE)


def attempts_remaining(*, attempt: int, max_attempts: int) -> bool:
    """Return True when another execution attempt is allowed."""
    return attempt < max_attempts
