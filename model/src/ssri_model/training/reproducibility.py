"""Backward-compatible reproducibility helpers."""

from __future__ import annotations

from ssri_model.training.device import resolve_device
from ssri_model.training.seed import set_seed as set_global_seed

__all__ = ["resolve_device", "set_global_seed"]
