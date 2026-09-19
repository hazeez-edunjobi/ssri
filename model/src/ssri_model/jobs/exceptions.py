"""Exceptions for SSRI job execution."""


class JobError(Exception):
    """Base exception for job operations."""


class JobNotFoundError(JobError):
    """Raised when a job record cannot be found."""


class JobAccessDeniedError(JobError):
    """Raised when a principal cannot access a job."""


class JobAlreadyCompletedError(JobError):
    """Raised when an operation conflicts with a completed job."""


class JobCannotCancelError(JobError):
    """Raised when a job cannot be cancelled."""


class JobQueueFullError(JobError):
    """Raised when the job queue is at capacity."""


class AsyncDisabledError(JobError):
    """Raised when async execution is disabled."""


class IdempotencyConflictError(JobError):
    """Raised when an idempotency key conflicts with a different request."""


class InvalidJobTransitionError(JobError):
    """Raised when a job state transition is not permitted."""


class InfrastructureUnavailableError(JobError):
    """Raised when required infrastructure is unavailable."""


class JobLeaseError(JobError):
    """Raised when a worker cannot acquire a job lease."""


class StaleLeaseRecoveryError(JobError):
    """Raised when stale lease recovery cannot be applied safely."""


class HeartbeatUpdateError(JobError):
    """Raised when a heartbeat update is rejected."""
