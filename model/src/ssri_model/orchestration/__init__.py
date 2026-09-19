"""SSRI batch inference orchestration."""

from ssri_model.orchestration.cli import main
from ssri_model.orchestration.config import BatchConfig, BatchJobsFile, JobSpec
from ssri_model.orchestration.exceptions import (
    BatchExistsError,
    BatchManifestError,
    CheckpointCompatibilityError,
    DuplicateJobIdError,
    InvalidBatchConfigError,
    InvalidJobSpecError,
    JobValidationError,
    OrchestrationError,
    PathTraversalError,
)
from ssri_model.orchestration.jobs import load_jobs_file, sanitize_job_id, validate_job_spec
from ssri_model.orchestration.manifest import (
    BATCH_MANIFEST_NAME,
    BatchManifest,
    JobRecord,
    load_batch_manifest,
    save_batch_manifest,
)
from ssri_model.orchestration.runner import BatchResult, BatchRunner, JobResult
from ssri_model.orchestration.status import (
    BatchStatusResult,
    BatchSummary,
    JobStatusResult,
    get_batch_status,
    get_job_status,
    summarize_batch,
)

__all__ = [
    "BATCH_MANIFEST_NAME",
    "BatchConfig",
    "BatchExistsError",
    "BatchJobsFile",
    "BatchManifest",
    "BatchManifestError",
    "BatchResult",
    "BatchRunner",
    "BatchStatusResult",
    "BatchSummary",
    "CheckpointCompatibilityError",
    "DuplicateJobIdError",
    "InvalidBatchConfigError",
    "InvalidJobSpecError",
    "JobRecord",
    "JobResult",
    "JobSpec",
    "JobStatusResult",
    "JobValidationError",
    "OrchestrationError",
    "PathTraversalError",
    "get_batch_status",
    "get_job_status",
    "load_batch_manifest",
    "load_jobs_file",
    "main",
    "sanitize_job_id",
    "save_batch_manifest",
    "summarize_batch",
    "validate_job_spec",
]
