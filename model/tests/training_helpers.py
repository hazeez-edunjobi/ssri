"""Shared helpers for SSRI training tests."""

from __future__ import annotations

from torch.utils.data import DataLoader, Dataset

import torch

from ssri_model.ml.constants import CHANNEL_COUNT, LABEL_NODATA
from ssri_model.ml.collate import ssri_collate_fn


class SyntheticSegmentationDataset(Dataset[dict[str, torch.Tensor | str]]):
    """In-memory segmentation dataset for offline training tests."""

    def __init__(
        self,
        *,
        num_samples: int,
        height: int = 32,
        width: int = 32,
        seed: int = 0,
        masked_fraction: float = 0.0,
    ) -> None:
        generator = torch.Generator().manual_seed(seed)
        self._samples: list[dict[str, torch.Tensor | str]] = []

        for index in range(num_samples):
            features = torch.randn(
                CHANNEL_COUNT,
                height,
                width,
                generator=generator,
                dtype=torch.float32,
            )
            labels = torch.randint(
                0,
                3,
                (height, width),
                generator=generator,
                dtype=torch.int64,
            )
            mask = torch.ones(height, width, dtype=torch.bool)
            if masked_fraction > 0.0:
                invalid_count = int(height * width * masked_fraction)
                flat_indices = torch.randperm(height * width, generator=generator)[
                    :invalid_count
                ]
                mask.view(-1)[flat_indices] = False
                labels.view(-1)[flat_indices] = LABEL_NODATA

            self._samples.append(
                {
                    "features": features,
                    "label": labels,
                    "mask": mask,
                    "sample_id": f"sample-{index}",
                }
            )

    def __len__(self) -> int:
        return len(self._samples)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor | str]:
        return self._samples[index]


def make_dataloader(
    dataset: Dataset[dict[str, torch.Tensor | str]],
    *,
    batch_size: int = 2,
    shuffle: bool = False,
) -> DataLoader[dict[str, torch.Tensor | str]]:
    """Create a collated dataloader for synthetic training tests."""
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        collate_fn=ssri_collate_fn,
    )
