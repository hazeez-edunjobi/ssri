"""Learning-rate scheduler factory for SSRI training."""

from __future__ import annotations

import torch

from ssri_model.training.config import TrainingConfig
from ssri_model.training.exceptions import InvalidTrainingConfigError


def create_scheduler(
    optimizer: torch.optim.Optimizer,
    config: TrainingConfig,
) -> torch.optim.lr_scheduler.LRScheduler | None:
    """Create a per-epoch learning-rate scheduler.

    Schedulers are stepped once per epoch after the training pass completes.
    ``reduce_on_plateau`` is stepped with the validation metric after validation.
    """
    if config.scheduler == "none":
        return None
    if config.scheduler == "cosine":
        return torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=config.epochs,
        )
    if config.scheduler == "reduce_on_plateau":
        return torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode="min",
            factor=0.5,
            patience=2,
        )
    raise InvalidTrainingConfigError(f"Unsupported scheduler: {config.scheduler}")
