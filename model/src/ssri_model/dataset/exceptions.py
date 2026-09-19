"""Dataset pipeline exceptions."""

from __future__ import annotations


class DatasetError(Exception):
    """Base exception for dataset pipeline errors."""


class DatasetBuildError(DatasetError):
    """Raised when dataset generation fails."""


class DatasetValidationError(DatasetError):
    """Raised when dataset or sample validation fails."""


class TensorShapeError(DatasetValidationError):
    """Raised when a feature tensor has an invalid shape."""


class ChannelCountError(DatasetValidationError):
    """Raised when channel count does not match the ML contract."""


class CRSError(DatasetValidationError):
    """Raised when CRS metadata is missing or inconsistent."""


class MetadataIncompleteError(DatasetValidationError):
    """Raised when required metadata fields are absent."""


class LabelDimensionError(DatasetValidationError):
    """Raised when label raster dimensions do not match features."""


class MissingValueError(DatasetValidationError):
    """Raised when required files or values are missing."""


class CorruptFileError(DatasetValidationError):
    """Raised when a dataset artifact cannot be read."""
