"""Exceptions for the SSRI training pipeline."""


class TrainingError(Exception):
    """Base exception for training pipeline errors."""


class InvalidTrainingConfigError(TrainingError):
    """Raised when training configuration values are invalid."""


class DeviceNotAvailableError(TrainingError):
    """Raised when a requested compute device is unavailable."""


class LossComputationError(TrainingError):
    """Raised when a loss cannot be computed for the provided tensors."""


class NoValidPixelsError(LossComputationError):
    """Raised when no valid pixels remain after applying the training mask."""


class MetricsComputationError(TrainingError):
    """Raised when segmentation metrics cannot be computed."""


class CheckpointError(TrainingError):
    """Raised when checkpoint save or load fails."""


class CheckpointCompatibilityError(CheckpointError):
    """Raised when a checkpoint is incompatible with the current model."""


class ExperimentExistsError(TrainingError):
    """Raised when an experiment directory already exists."""


class DatasetValidationError(TrainingError):
    """Raised when a dataset fails pre-training validation."""


class SplitLeakageError(TrainingError):
    """Raised when sample identifiers overlap across dataset splits."""
