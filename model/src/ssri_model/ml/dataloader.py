"""DataLoader factory for SSRI PyTorch datasets."""

from __future__ import annotations

from torch.utils.data import DataLoader

from ssri_model.ml.collate import ssri_collate_fn
from ssri_model.ml.dataset import SSRIDataset


def create_dataloader(
    dataset: SSRIDataset,
    *,
    batch_size: int = 4,
    shuffle: bool | None = None,
    num_workers: int = 0,
    pin_memory: bool = False,
    drop_last: bool = False,
) -> DataLoader:
    """Create a device-agnostic DataLoader for an ``SSRIDataset``."""
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")

    if shuffle is None:
        shuffle = dataset.split == "train"

    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=pin_memory,
        drop_last=drop_last,
        collate_fn=ssri_collate_fn,
    )
