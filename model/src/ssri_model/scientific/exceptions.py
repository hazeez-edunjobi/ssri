"""Exceptions for SSRI scientific validation."""


class ScientificValidationError(Exception):
    """Base exception for scientific validation errors."""


class InvalidScientificConfigError(ScientificValidationError):
    """Raised when validation configuration is invalid."""


class DatasetAuditError(ScientificValidationError):
    """Raised when a dataset audit cannot be completed."""


class SpatialValidationError(ScientificValidationError):
    """Raised when spatial validation inputs are invalid."""


class LabelAuditError(ScientificValidationError):
    """Raised when label audit inputs are invalid."""


class FeatureAuditError(ScientificValidationError):
    """Raised when feature audit inputs are invalid."""


class ReviewValidationError(ScientificValidationError):
    """Raised when a scientific review record is invalid."""


class ValidationFailureError(ScientificValidationError):
    """Raised when a blocking validation failure is detected."""
