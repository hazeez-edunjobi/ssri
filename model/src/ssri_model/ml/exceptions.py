"""Typed exceptions for SSRI PyTorch dataset loading."""

from __future__ import annotations


class MLDatasetError(Exception):
    """Base exception for ML dataset loading errors."""


class InvalidFeatureTensorError(MLDatasetError):
    """Raised when a feature tensor violates the SSRI contract."""


class InvalidLabelError(MLDatasetError):
    """Raised when a label raster violates the SSRI contract."""


class NormalizationError(MLDatasetError):
    """Raised when normalization cannot be applied safely."""


class StatisticsError(MLDatasetError):
    """Raised when dataset statistics are missing or invalid."""


class SplitError(MLDatasetError):
    """Raised when split definitions are invalid or samples are mixed."""


class BatchShapeError(MLDatasetError):
    """Raised when batch collation encounters incompatible sample shapes."""


class EmptyDatasetError(MLDatasetError):
    """Raised when an empty dataset is accessed."""
