"""Safety checks for SSRI test-set evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from ssri_model.architecture.model import SSRIModel
from ssri_model.dataset.catalog import load_catalog_manifest
from ssri_model.ml.constants import CHANNEL_COUNT
from ssri_model.ml.dataset_spec import DatasetManifest
from ssri_model.evaluation.config import EvaluationConfig
from ssri_model.evaluation.exceptions import (
    EvaluationDataLeakageError,
    InvalidEvaluationConfigError,
)


def _split_sets(manifest_payload: Mapping[str, object]) -> tuple[set[str], set[str], set[str]]:
    splits = manifest_payload.get("splits")
    if not isinstance(splits, Mapping):
        raise InvalidEvaluationConfigError(
            "Dataset manifest is missing a valid 'splits' section"
        )
    train = {str(sample_id) for sample_id in splits.get("train", [])}
    validation = {str(sample_id) for sample_id in splits.get("validation", [])}
    test = {str(sample_id) for sample_id in splits.get("test", [])}
    return train, validation, test


def check_test_split_leakage(manifest_path: Path | str) -> None:
    """Ensure test sample IDs do not overlap train or validation splits."""
    payload = load_catalog_manifest(manifest_path)
    train, validation, test = _split_sets(payload)

    overlaps = {
        "train/test": train & test,
        "validation/test": validation & test,
    }
    for label, sample_ids in overlaps.items():
        if sample_ids:
            raise EvaluationDataLeakageError(
                f"Sample IDs overlap between {label}: {sorted(sample_ids)}"
            )


def validate_evaluation_setup(
    config: EvaluationConfig,
    *,
    model: SSRIModel | None = None,
) -> DatasetManifest:
    """Validate evaluation configuration and test-split safety."""
    config.validate_paths()
    manifest = DatasetManifest.load(config.manifest_path)
    payload = load_catalog_manifest(config.manifest_path)
    train, validation, test = _split_sets(payload)

    if not test:
        raise InvalidEvaluationConfigError("Test split is empty or missing")

    check_test_split_leakage(config.manifest_path)

    if len(manifest.channels) != CHANNEL_COUNT:
        raise InvalidEvaluationConfigError(
            f"Expected {CHANNEL_COUNT} channels in manifest, "
            f"received {len(manifest.channels)}"
        )

    if model is not None:
        if model.in_channels != CHANNEL_COUNT:
            raise InvalidEvaluationConfigError(
                f"Model in_channels must be {CHANNEL_COUNT}, "
                f"received {model.in_channels}"
            )
        if model.num_classes != 3:
            raise InvalidEvaluationConfigError(
                f"Model num_classes must be 3, received {model.num_classes}"
            )

    if train or validation:
        # Explicitly document that only test will be consumed; leakage already checked.
        pass

    return manifest
