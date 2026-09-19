"""Spatially synchronized transforms for SSRI tensors."""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Protocol

import numpy as np
import torch


class SampleTensors(Protocol):
    """Minimal sample tensor bundle used by transforms."""

    features: torch.Tensor
    label: torch.Tensor
    mask: torch.Tensor


class SpatialTransform(ABC):
    """Base class for synchronized spatial transforms."""

    @abstractmethod
    def __call__(self, sample: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        """Apply a synchronized transform to a sample dictionary."""


class HorizontalFlip(SpatialTransform):
    """Flip features, labels, and mask horizontally."""

    def __init__(self, probability: float = 0.5) -> None:
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability must be between 0 and 1")
        self.probability = probability
        self._rng = random.Random()

    def set_seed(self, seed: int) -> None:
        self._rng.seed(seed)

    def __call__(self, sample: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        if self._rng.random() >= self.probability:
            return sample
        return {
            **sample,
            "features": torch.flip(sample["features"], dims=(-1,)),
            "label": torch.flip(sample["label"], dims=(-1,)),
            "mask": torch.flip(sample["mask"], dims=(-1,)),
        }


class VerticalFlip(SpatialTransform):
    """Flip features, labels, and mask vertically."""

    def __init__(self, probability: float = 0.5) -> None:
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability must be between 0 and 1")
        self.probability = probability
        self._rng = random.Random()

    def set_seed(self, seed: int) -> None:
        self._rng.seed(seed)

    def __call__(self, sample: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        if self._rng.random() >= self.probability:
            return sample
        return {
            **sample,
            "features": torch.flip(sample["features"], dims=(-2,)),
            "label": torch.flip(sample["label"], dims=(-2,)),
            "mask": torch.flip(sample["mask"], dims=(-2,)),
        }


class Rotate90(SpatialTransform):
    """Rotate features, labels, and mask by 90 degrees clockwise."""

    def __init__(self, probability: float = 0.5) -> None:
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability must be between 0 and 1")
        self.probability = probability
        self._rng = random.Random()

    def set_seed(self, seed: int) -> None:
        self._rng.seed(seed)

    def __call__(self, sample: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        if self._rng.random() >= self.probability:
            return sample
        features = torch.rot90(sample["features"], k=-1, dims=(-2, -1))
        label = torch.rot90(sample["label"], k=-1, dims=(-2, -1))
        mask = torch.rot90(sample["mask"], k=-1, dims=(-2, -1))
        return {
            **sample,
            "features": features,
            "label": label,
            "mask": mask,
        }


class Compose(SpatialTransform):
    """Apply multiple synchronized transforms in order."""

    def __init__(self, transforms: list[SpatialTransform]) -> None:
        self.transforms = transforms

    def set_seed(self, seed: int) -> None:
        for index, transform in enumerate(self.transforms):
            if hasattr(transform, "set_seed"):
                transform.set_seed(seed + index)

    def __call__(self, sample: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        output = sample
        for transform in self.transforms:
            output = transform(output)
        return output


def apply_numpy_spatial_transform(
    features: np.ndarray,
    label: np.ndarray,
    mask: np.ndarray,
    *,
    horizontal_flip: bool = False,
    vertical_flip: bool = False,
    rotate_k: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Apply deterministic spatial transforms to numpy arrays for tests."""
    out_features = features
    out_label = label
    out_mask = mask

    if horizontal_flip:
        out_features = np.flip(out_features, axis=-1)
        out_label = np.flip(out_label, axis=-1)
        out_mask = np.flip(out_mask, axis=-1)

    if vertical_flip:
        out_features = np.flip(out_features, axis=-2)
        out_label = np.flip(out_label, axis=-2)
        out_mask = np.flip(out_mask, axis=-2)

    if rotate_k % 4 != 0:
        out_features = np.rot90(out_features, k=rotate_k, axes=(-2, -1))
        out_label = np.rot90(out_label, k=rotate_k, axes=(-2, -1))
        out_mask = np.rot90(out_mask, k=rotate_k, axes=(-2, -1))

    return out_features, out_label, out_mask
