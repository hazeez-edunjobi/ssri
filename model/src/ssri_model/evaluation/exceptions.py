"""Exceptions for the SSRI evaluation pipeline."""


class EvaluationError(Exception):
    """Base exception for evaluation pipeline errors."""


class InvalidEvaluationConfigError(EvaluationError):
    """Raised when evaluation configuration values are invalid."""


class EvaluationCheckpointError(EvaluationError):
    """Raised when a checkpoint cannot be used for evaluation."""


class EvaluationDataLeakageError(EvaluationError):
    """Raised when dataset splits leak into the test evaluation set."""


class PredictionAlignmentError(EvaluationError):
    """Raised when prediction rasters are not aligned with source grids."""
