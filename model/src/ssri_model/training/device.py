"""Device selection utilities for SSRI training."""

from __future__ import annotations

import torch

from ssri_model.training.config import DeviceType
from ssri_model.training.exceptions import DeviceNotAvailableError, InvalidTrainingConfigError


def resolve_device(device: DeviceType) -> torch.device:
    """Resolve a training device from a configuration string."""
    if device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device == "cpu":
        return torch.device("cpu")
    if device == "cuda":
        if not torch.cuda.is_available():
            raise DeviceNotAvailableError(
                "CUDA was requested but is not available on this system"
            )
        return torch.device("cuda")
    raise InvalidTrainingConfigError(f"Unsupported device value: {device}")
