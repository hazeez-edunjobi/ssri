"""Label audit utilities for SSRI scientific validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import rasterio

from ssri_model.ml.constants import FEATURE_NODATA, LABEL_NODATA
from ssri_model.ml.labels import label_class_names
from ssri_model.scientific.exceptions import LabelAuditError

AuditStatus = Literal["PASS", "WARNING", "FAIL"]
VALID_CLASS_IDS = {0, 1, 2}


@dataclass
class SampleLabelAudit:
    """Label audit for one sample."""

    sample_id: str
    split: str
    total_pixels: int = 0
    valid_pixels: int = 0
    nodata_pixels: int = 0
    class_pixel_counts: dict[int, int] = field(default_factory=dict)
    invalid_class_values: list[float] = field(default_factory=list)
    crs_match: bool = True
    transform_match: bool = True
    dimension_match: bool = True
    warnings: list[str] = field(default_factory=list)
    status: AuditStatus = "PASS"


@dataclass
class LabelAuditResult:
    """Aggregate label audit output."""

    samples: list[SampleLabelAudit] = field(default_factory=list)
    class_names: tuple[str, ...] = field(default_factory=label_class_names)
    total_pixels: int = 0
    valid_pixels: int = 0
    per_class_pixels: dict[int, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    status: AuditStatus = "PASS"


def _normalize_label_value(value: float) -> int | None:
    if value == FEATURE_NODATA or value == LABEL_NODATA or np.isnan(value):
        return None
    if value in VALID_CLASS_IDS:
        return int(value)
    if value in {1.0, 2.0, 3.0}:
        return int(value) - 1
    return None


def audit_sample_labels(
    sample_dir: Path,
    *,
    split: str,
    expected_crs: str,
    expected_shape: tuple[int, int] | None = None,
    config: object | None = None,
) -> SampleLabelAudit:
    from ssri_model.scientific.config import ScientificValidationConfig

    cfg = config if isinstance(config, ScientificValidationConfig) else ScientificValidationConfig()
    sample_id = sample_dir.name
    label_path = sample_dir / "label.tif"
    if not label_path.exists():
        raise LabelAuditError(f"Missing label raster: {label_path}")

    audit = SampleLabelAudit(sample_id=sample_id, split=split)
    try:
        with rasterio.open(label_path) as dataset:
            label = dataset.read(1)
            audit.total_pixels = int(label.size)
            if expected_shape is not None:
                audit.dimension_match = (dataset.height, dataset.width) == expected_shape
                if not audit.dimension_match:
                    audit.warnings.append("Label dimensions do not match feature shape")
                    audit.status = "FAIL"
            if str(dataset.crs) != expected_crs:
                audit.crs_match = False
                audit.warnings.append(
                    f"Label CRS '{dataset.crs}' does not match expected '{expected_crs}'"
                )
                audit.status = "FAIL"
    except rasterio.errors.RasterioIOError as exc:
        raise LabelAuditError(f"Unable to read label raster: {label_path}") from exc

    for value in np.unique(label):
        class_id = _normalize_label_value(float(value))
        count = int(np.sum(label == value))
        if class_id is None:
            audit.nodata_pixels += count
            if value not in (FEATURE_NODATA, LABEL_NODATA) and not np.isnan(value):
                audit.invalid_class_values.append(float(value))
        else:
            audit.valid_pixels += count
            audit.class_pixel_counts[class_id] = (
                audit.class_pixel_counts.get(class_id, 0) + count
            )

    if audit.valid_pixels == 0:
        audit.warnings.append("Sample has zero labelled pixels")
        audit.status = "WARNING"

    nodata_fraction = audit.nodata_pixels / audit.total_pixels if audit.total_pixels else 1.0
    if nodata_fraction > cfg.max_nodata_fraction:
        audit.warnings.append(
            f"Excessive label nodata fraction: {nodata_fraction:.3f}"
        )
        if audit.status == "PASS":
            audit.status = "WARNING"

    if audit.invalid_class_values:
        audit.warnings.append(f"Invalid class values: {audit.invalid_class_values}")
        audit.status = "FAIL"

    if audit.valid_pixels > 0:
        dominant = max(audit.class_pixel_counts.values()) / audit.valid_pixels
        if dominant >= cfg.max_class_dominance_fraction:
            audit.warnings.append(
                f"Sample dominated by one class ({dominant:.3f} fraction)"
            )
            if audit.status == "PASS":
                audit.status = "WARNING"

    if audit.valid_pixels > 0 and len(audit.class_pixel_counts) == 1:
        audit.warnings.append("Suspiciously uniform labels")
        if audit.status == "PASS":
            audit.status = "WARNING"

    return audit


def audit_labels(
    dataset_root: Path,
    manifest_payload: dict[str, object],
    *,
    config: object | None = None,
) -> LabelAuditResult:
    from ssri_model.scientific.config import ScientificValidationConfig

    cfg = config if isinstance(config, ScientificValidationConfig) else ScientificValidationConfig()
    result = LabelAuditResult()
    splits = manifest_payload.get("splits")
    if not isinstance(splits, dict):
        raise LabelAuditError("Manifest is missing splits section")

    dataset_crs = str(manifest_payload.get("crs", ""))
    for split_name, sample_ids in splits.items():
        if not isinstance(sample_ids, list):
            continue
        for sample_id in sample_ids:
            sample_dir = dataset_root / str(split_name) / str(sample_id)
            feature_path = sample_dir / "feature_stack.npy"
            expected_shape = None
            if feature_path.exists():
                tensor = np.load(feature_path, mmap_mode="r")
                expected_shape = (int(tensor.shape[1]), int(tensor.shape[2]))
            sample_audit = audit_sample_labels(
                sample_dir,
                split=str(split_name),
                expected_crs=dataset_crs,
                expected_shape=expected_shape,
                config=cfg,
            )
            result.samples.append(sample_audit)
            result.total_pixels += sample_audit.total_pixels
            result.valid_pixels += sample_audit.valid_pixels
            for class_id, count in sample_audit.class_pixel_counts.items():
                result.per_class_pixels[class_id] = (
                    result.per_class_pixels.get(class_id, 0) + count
                )
            result.warnings.extend(
                f"{sample_id}: {warning}" for warning in sample_audit.warnings
            )
            if sample_audit.status == "FAIL":
                result.status = "FAIL"
            elif sample_audit.status == "WARNING" and result.status == "PASS":
                result.status = "WARNING"

    for class_id in VALID_CLASS_IDS:
        if result.per_class_pixels.get(class_id, 0) == 0:
            result.warnings.append(f"Class {class_id} absent from dataset labels")
            if result.status == "PASS":
                result.status = "WARNING"

    samples_with_class = {class_id: 0 for class_id in VALID_CLASS_IDS}
    for sample in result.samples:
        for class_id in sample.class_pixel_counts:
            samples_with_class[class_id] = samples_with_class.get(class_id, 0) + 1

    for class_id, count in samples_with_class.items():
        if count < cfg.min_samples_per_class:
            result.warnings.append(
                f"Class {class_id} present in fewer than "
                f"{cfg.min_samples_per_class} samples ({count})"
            )
            if result.status == "PASS":
                result.status = "WARNING"

    return result
