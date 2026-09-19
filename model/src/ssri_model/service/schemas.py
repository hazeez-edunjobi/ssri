"""Shared schema types for SSRI service contracts."""

from __future__ import annotations

from enum import Enum

from ssri_model.scientific.report import ValidationStatus


class ServiceEnvironment(str, Enum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class InferenceExecutionStatus(str, Enum):
    """Execution status for inference operations."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BatchExecutionStatus(str, Enum):
    """Execution status for batch inference operations."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class OutputFormat(str, Enum):
    """Supported prediction output formats."""

    GEOTIFF = "geotiff"
    ALL = "all"


# Stage 2.9 scientific validation statuses (do not extend or rename).
ScientificValidationStatus = ValidationStatus

SCIENTIFIC_VALIDATION_STATUSES: frozenset[str] = frozenset(
    {
        "NOT_VALIDATED",
        "DATASET_AUDITED",
        "STATISTICALLY_VALIDATED",
        "SPATIALLY_VALIDATED",
        "SCIENTIFICALLY_VALIDATED",
    }
)

GEOTIFF_ARTIFACTS: tuple[str, ...] = (
    "prediction.tif",
    "confidence.tif",
    "probabilities.tif",
    "inference.json",
)
