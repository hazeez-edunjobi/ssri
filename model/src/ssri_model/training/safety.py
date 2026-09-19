"""Pre-training safety and data-leakage checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ssri_model.architecture.model import SSRIModel
from ssri_model.dataset.catalog import load_catalog_manifest
from ssri_model.ml.constants import CHANNEL_COUNT
from ssri_model.ml.dataset_spec import DatasetManifest
from ssri_model.training.exceptions import (
    DatasetValidationError,
    InvalidTrainingConfigError,
    SplitLeakageError,
)


def _split_sets(manifest_payload: Mapping[str, Any]) -> tuple[set[str], set[str], set[str]]:
    splits = manifest_payload.get("splits")
    if not isinstance(splits, Mapping):
        raise DatasetValidationError("Dataset manifest is missing a valid 'splits' section")

    train = set(str(sample_id) for sample_id in splits.get("train", []))
    validation = set(str(sample_id) for sample_id in splits.get("validation", []))
    test = set(str(sample_id) for sample_id in splits.get("test", []))
    return train, validation, test


def check_split_leakage(manifest_path: Path | str) -> None:
    """Reject manifests where sample IDs appear in more than one split."""
    payload = load_catalog_manifest(manifest_path)
    train, validation, test = _split_sets(payload)

    overlaps = {
        "train/validation": train & validation,
        "train/test": train & test,
        "validation/test": validation & test,
    }
    for label, sample_ids in overlaps.items():
        if sample_ids:
            raise SplitLeakageError(
                f"Sample IDs overlap between {label}: {sorted(sample_ids)}"
            )


def load_dataset_manifest(manifest_path: Path | str) -> DatasetManifest:
    """Load and return the typed dataset manifest."""
    path = Path(manifest_path)
    if not path.exists():
        raise DatasetValidationError(f"Dataset manifest not found: {path}")
    return DatasetManifest.load(path)


def validate_training_setup(
    *,
    manifest_path: Path | str,
    model: SSRIModel,
) -> DatasetManifest:
    """Validate dataset and model contracts before training begins."""
    path = Path(manifest_path)
    if not path.exists():
        raise DatasetValidationError(f"Dataset manifest not found: {path}")

    manifest = load_dataset_manifest(path)
    payload = load_catalog_manifest(path)
    train, validation, _test = _split_sets(payload)

    if not train:
        raise DatasetValidationError("Training split is empty")
    if not validation:
        raise DatasetValidationError("Validation split is empty")

    check_split_leakage(path)

    if len(manifest.channels) != CHANNEL_COUNT:
        raise DatasetValidationError(
            f"Expected {CHANNEL_COUNT} channels in manifest, "
            f"received {len(manifest.channels)}"
        )

    if model.in_channels != CHANNEL_COUNT:
        raise InvalidTrainingConfigError(
            f"Model in_channels must be {CHANNEL_COUNT}, "
            f"received {model.in_channels}"
        )

    if model.num_classes != 3:
        raise InvalidTrainingConfigError(
            f"Model num_classes must be 3, received {model.num_classes}"
        )

    return manifest


def dataset_manifest_identity(manifest: DatasetManifest) -> dict[str, str]:
    """Return the dataset identity stored in checkpoints."""
    return {
        "dataset_name": manifest.dataset_name,
        "version": manifest.version,
    }
