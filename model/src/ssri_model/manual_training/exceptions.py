"""Exceptions for the manual training workflow."""

from __future__ import annotations


class ManualTrainingError(Exception):
    """Base error with an operator-facing message."""

    def __init__(self, message: str, *, code: str = "TRAINING_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class DatasetValidationFailed(ManualTrainingError):
    def __init__(self, message: str, *, errors: list[str] | None = None) -> None:
        super().__init__(message, code="DATASET_VALIDATION_FAILED")
        self.errors = list(errors or [])


class DatasetNotFoundError(ManualTrainingError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="DATASET_NOT_FOUND")


class ModelNotFoundError(ManualTrainingError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="MODEL_NOT_FOUND")


class UnsafePathError(ManualTrainingError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="UNSAFE_PATH")
