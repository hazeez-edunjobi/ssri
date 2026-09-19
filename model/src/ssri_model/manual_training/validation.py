"""Validate Stage 2.5 training datasets with operator-facing messages."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES, LABEL_NODATA
from ssri_model.ml.labels import label_class_names
from ssri_model.training.safety import check_split_leakage


@dataclass
class DatasetPreview:
    dataset_name: str | None
    version: str | None
    sample_count: int
    train_count: int
    validation_count: int
    test_count: int
    channel_count: int
    channels: list[str]
    spatial_size: dict[str, int] | None
    crs: str | None
    label_classes: list[str]
    class_distribution: dict[str, int]
    missing_label_pixels: int
    non_finite_feature_samples: int
    resolution_m: float | None
    validation_status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _collect_sample_dirs(root: Path, split: str) -> list[Path]:
    split_dir = root / split
    if not split_dir.exists():
        return []
    return sorted(path for path in split_dir.iterdir() if path.is_dir())


def validate_training_dataset(dataset_root: Path | str) -> DatasetPreview:
    """Validate a Stage 2.5 on-disk dataset and return a preview summary."""
    root = Path(dataset_root)
    errors: list[str] = []
    warnings: list[str] = []

    if not root.exists() or not root.is_dir():
        return DatasetPreview(
            dataset_name=None,
            version=None,
            sample_count=0,
            train_count=0,
            validation_count=0,
            test_count=0,
            channel_count=0,
            channels=[],
            spatial_size=None,
            crs=None,
            label_classes=[],
            class_distribution={},
            missing_label_pixels=0,
            non_finite_feature_samples=0,
            resolution_m=None,
            validation_status="failed",
            errors=[f"Dataset directory does not exist: {root}"],
        )

    manifest_path = root / "manifest.json"
    statistics_path = root / "statistics.json"
    if not manifest_path.exists():
        errors.append("Missing manifest.json at the dataset root.")
    if not statistics_path.exists():
        errors.append("Missing statistics.json at the dataset root.")

    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append("manifest.json is not valid JSON.")

    splits = manifest.get("splits") if isinstance(manifest, dict) else None
    train_ids = list((splits or {}).get("train") or [])
    val_ids = list((splits or {}).get("validation") or [])
    test_ids = list((splits or {}).get("test") or [])

    if not train_ids:
        errors.append("Training split is empty. Provide at least one train sample.")
    if not val_ids:
        errors.append(
            "Validation split is empty. The SSRI trainer requires a non-empty validation split."
        )

    if manifest_path.exists() and train_ids and val_ids:
        try:
            check_split_leakage(manifest_path)
        except Exception as exc:  # noqa: BLE001 — surface as readable error
            errors.append(str(exc))

    channels = list(manifest.get("channels") or CHANNEL_NAMES)
    if channels and len(channels) != CHANNEL_COUNT:
        errors.append(
            f"Feature stack contains {len(channels)} channels in the manifest, "
            f"but the current SSRI model expects {CHANNEL_COUNT} channels "
            f"({', '.join(CHANNEL_NAMES)})."
        )

    label_classes = list(manifest.get("label_classes") or label_class_names())
    expected_labels = list(label_class_names())
    if label_classes and list(label_classes) != expected_labels:
        warnings.append(
            f"Label classes are {label_classes}; SSRI Stage 2.5 assessments use "
            f"{expected_labels}."
        )

    class_counts: Counter[str] = Counter()
    missing_label_pixels = 0
    non_finite_feature_samples = 0
    spatial_size: dict[str, int] | None = None
    crs: str | None = manifest.get("crs")
    checked_samples = 0

    for split_name, sample_ids in (
        ("train", train_ids),
        ("validation", val_ids),
        ("test", test_ids),
    ):
        for sample_id in sample_ids:
            sample_dir = root / split_name / str(sample_id)
            if not sample_dir.exists():
                errors.append(
                    f"Sample '{sample_id}' is listed in the '{split_name}' split "
                    f"but the folder is missing: {sample_dir}"
                )
                continue

            feature_path = sample_dir / "feature_stack.npy"
            label_path = sample_dir / "label.tif"
            metadata_path = sample_dir / "metadata.json"
            preview_path = sample_dir / "preview.png"

            if not feature_path.exists():
                errors.append(
                    f"Sample '{sample_id}' is missing feature_stack.npy "
                    "(expected a 13-channel NumPy array)."
                )
                continue
            if not label_path.exists():
                errors.append(
                    f"Sample '{sample_id}' is missing label.tif "
                    "(expected a GeoTIFF with class indices)."
                )
                continue
            if not metadata_path.exists():
                errors.append(f"Sample '{sample_id}' is missing metadata.json.")
            if not preview_path.exists():
                warnings.append(
                    f"Sample '{sample_id}' is missing preview.png "
                    "(recommended for dataset QA; not required by the trainer)."
                )

            try:
                features = np.load(feature_path)
            except Exception:  # noqa: BLE001
                errors.append(f"Sample '{sample_id}' feature_stack.npy could not be read.")
                continue

            if features.ndim != 3:
                errors.append(
                    f"Sample '{sample_id}' feature stack must be shaped "
                    f"(channels, height, width); received shape {features.shape}."
                )
                continue
            channels_found, height, width = features.shape
            if channels_found != CHANNEL_COUNT:
                errors.append(
                    f"Sample '{sample_id}' feature stack contains {channels_found} channels, "
                    f"but the current SSRI model expects {CHANNEL_COUNT} channels."
                )
            if height < 8 or width < 8:
                warnings.append(
                    f"Sample '{sample_id}' spatial size is {height}×{width}; "
                    "very small tiles may train poorly."
                )
            if not np.isfinite(features).all():
                non_finite_feature_samples += 1
                errors.append(
                    f"Sample '{sample_id}' feature stack contains NaN or Inf values."
                )
            if spatial_size is None:
                spatial_size = {"height": int(height), "width": int(width)}

            try:
                with rasterio.open(label_path) as dataset:
                    label = dataset.read(1)
                    if crs is None and dataset.crs is not None:
                        crs = str(dataset.crs)
                    if (dataset.height, dataset.width) != (height, width):
                        errors.append(
                            f"Sample '{sample_id}' label size is "
                            f"{dataset.height}×{dataset.width}, but features are "
                            f"{height}×{width}. They must match."
                        )
            except Exception:  # noqa: BLE001
                errors.append(f"Sample '{sample_id}' label.tif could not be read.")
                continue

            valid = label != LABEL_NODATA
            missing_label_pixels += int((~valid).sum())
            unique_vals = set(int(v) for v in np.unique(label[valid]).tolist()) if valid.any() else set()
            if unique_vals and unique_vals.issubset({1, 2, 3}):
                for class_index, class_name in enumerate(expected_labels):
                    class_counts[class_name] += int(((label == class_index + 1) & valid).sum())
            elif unique_vals and not unique_vals.issubset({0, 1, 2}):
                errors.append(
                    f"Sample '{sample_id}' has label values outside the expected "
                    f"classes 0–2 ({', '.join(expected_labels)}) or nodata {LABEL_NODATA}."
                )
            else:
                for class_index, class_name in enumerate(expected_labels):
                    class_counts[class_name] += int(((label == class_index) & valid).sum())

            checked_samples += 1

    if statistics_path.exists():
        try:
            stats = json.loads(statistics_path.read_text(encoding="utf-8"))
            channel_stats = stats.get("channel_stats") or {}
            if channel_stats and len(channel_stats) != CHANNEL_COUNT:
                warnings.append(
                    f"statistics.json describes {len(channel_stats)} channels; "
                    f"expected {CHANNEL_COUNT}."
                )
        except json.JSONDecodeError:
            errors.append("statistics.json is not valid JSON.")

    if checked_samples == 0 and not errors:
        errors.append("No readable samples were found in the dataset.")

    if sum(class_counts.values()) == 0 and checked_samples > 0:
        warnings.append(
            "No labeled pixels were found after excluding nodata. "
            "Training may fail or learn nothing useful."
        )

    status = "passed" if not errors else "failed"
    return DatasetPreview(
        dataset_name=manifest.get("dataset_name"),
        version=manifest.get("version"),
        sample_count=len(train_ids) + len(val_ids) + len(test_ids),
        train_count=len(train_ids),
        validation_count=len(val_ids),
        test_count=len(test_ids),
        channel_count=CHANNEL_COUNT,
        channels=list(channels) if channels else list(CHANNEL_NAMES),
        spatial_size=spatial_size,
        crs=crs,
        label_classes=list(label_classes) if label_classes else expected_labels,
        class_distribution=dict(class_counts),
        missing_label_pixels=missing_label_pixels,
        non_finite_feature_samples=non_finite_feature_samples,
        resolution_m=float(manifest["resolution"]) if manifest.get("resolution") else None,
        validation_status=status,
        errors=errors,
        warnings=warnings,
    )
