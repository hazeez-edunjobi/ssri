"""Batch collation utilities for SSRI PyTorch datasets."""

from __future__ import annotations

from typing import Any

import torch

from ssri_model.ml.exceptions import BatchShapeError


def ssri_collate_fn(batch: list[dict[str, Any]]) -> dict[str, Any]:
    """Collate SSRI samples into a fixed-shape batch."""
    if not batch:
        raise BatchShapeError("Cannot collate an empty batch")

    feature_shapes = {tuple(item["features"].shape) for item in batch}
    label_shapes = {tuple(item["label"].shape) for item in batch}
    mask_shapes = {tuple(item["mask"].shape) for item in batch}

    if len(feature_shapes) != 1:
        raise BatchShapeError(
            "All feature tensors in a batch must share the same shape; "
            f"received {sorted(feature_shapes)}"
        )
    if len(label_shapes) != 1:
        raise BatchShapeError(
            "All label tensors in a batch must share the same shape; "
            f"received {sorted(label_shapes)}"
        )
    if len(mask_shapes) != 1:
        raise BatchShapeError(
            "All mask tensors in a batch must share the same shape; "
            f"received {sorted(mask_shapes)}"
        )

    collated: dict[str, Any] = {
        "features": torch.stack([item["features"] for item in batch], dim=0),
        "label": torch.stack([item["label"] for item in batch], dim=0),
        "mask": torch.stack([item["mask"] for item in batch], dim=0),
        "sample_id": [item["sample_id"] for item in batch],
    }

    if "metadata" in batch[0]:
        collated["metadata"] = [item.get("metadata") for item in batch]

    return collated
