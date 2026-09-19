"""Exceptions for SSRI batch orchestration."""


class OrchestrationError(Exception):
    """Base exception for orchestration errors."""


class InvalidJobSpecError(OrchestrationError):
    """Raised when a job specification is invalid."""


class InvalidBatchConfigError(OrchestrationError):
    """Raised when batch configuration is invalid."""


class DuplicateJobIdError(OrchestrationError):
    """Raised when a batch contains duplicate job IDs."""


class PathTraversalError(OrchestrationError):
    """Raised when a job ID or path attempts directory traversal."""


class BatchExistsError(OrchestrationError):
    """Raised when a batch output directory already exists without resume/overwrite."""


class BatchManifestError(OrchestrationError):
    """Raised when a batch manifest cannot be read or written."""


class JobValidationError(OrchestrationError):
    """Raised when job inputs fail validation before inference."""


class CheckpointCompatibilityError(OrchestrationError):
    """Raised when a checkpoint is incompatible with the SSRI contract."""
