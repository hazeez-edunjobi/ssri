"""Optimizer factory for SSRI training."""

from __future__ import annotations

import torch
import torch.nn as nn

from ssri_model.training.config import TrainingConfig
from ssri_model.training.exceptions import InvalidTrainingConfigError


def create_optimizer(
    model: nn.Module,
    config: TrainingConfig,
) -> torch.optim.Optimizer:
    """Create an optimizer for SSRI model training."""
    parameters = (parameter for parameter in model.parameters() if parameter.requires_grad)
    if config.optimizer == "adam":
        return torch.optim.Adam(
            parameters,
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )
    if config.optimizer == "adamw":
        return torch.optim.AdamW(
            parameters,
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )
    if config.optimizer == "sgd":
        return torch.optim.SGD(
            parameters,
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
            momentum=0.9,
        )
    raise InvalidTrainingConfigError(f"Unsupported optimizer: {config.optimizer}")
