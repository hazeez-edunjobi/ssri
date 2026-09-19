"""Exceptions for the SSRI inference pipeline."""


class InferenceError(Exception):
    """Base exception for inference pipeline errors."""


class InvalidInferenceConfigError(InferenceError):
    """Raised when inference configuration values are invalid."""


class InferenceCheckpointError(InferenceError):
    """Raised when a checkpoint cannot be used for inference."""


class InferenceInputError(InferenceError):
    """Raised when input features or metadata are invalid."""


class InferenceAlignmentError(InferenceError):
    """Raised when outputs cannot be aligned to the input grid."""
