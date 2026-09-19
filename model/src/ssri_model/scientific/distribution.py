"""Class and feature distribution analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np

from ssri_model.ml.constants import CHANNEL_NAMES, FEATURE_NODATA
from ssri_model.scientific.labels import LabelAuditResult, SampleLabelAudit, VALID_CLASS_IDS

AuditStatus = Literal["PASS", "WARNING", "FAIL"]


@dataclass
class ClassDistributionResult:
    """Class distribution summary."""

    total_pixels: int = 0
    valid_pixels: int = 0
    per_class_pixels: dict[int, int] = field(default_factory=dict)
    per_class_fraction: dict[int, float] = field(default_factory=dict)
    samples_containing_class: dict[int, int] = field(default_factory=dict)
    samples_without_class: dict[int, int] = field(default_factory=dict)
    max_min_class_ratio: float | None = None
    warnings: list[str] = field(default_factory=list)
    status: AuditStatus = "PASS"


@dataclass
class FeatureDistributionShift:
    """Feature distribution comparison between splits."""

    channel_name: str
    train_mean: float | None = None
    validation_mean: float | None = None
    test_mean: float | None = None
    train_std: float | None = None
    validation_std: float | None = None
    test_std: float | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class DistributionAnalysisResult:
    """Combined distribution analysis."""

    class_distribution: ClassDistributionResult
    feature_shifts: list[FeatureDistributionShift] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: AuditStatus = "PASS"


def analyze_class_distribution(
    label_audit_samples: list[SampleLabelAudit],
) -> ClassDistributionResult:
    result = ClassDistributionResult()
    sample_count = len(label_audit_samples)
    for sample in label_audit_samples:
        result.total_pixels += sample.total_pixels
        result.valid_pixels += sample.valid_pixels
        for class_id, count in sample.class_pixel_counts.items():
            result.per_class_pixels[class_id] = (
                result.per_class_pixels.get(class_id, 0) + count
            )
            if count > 0:
                result.samples_containing_class[class_id] = (
                    result.samples_containing_class.get(class_id, 0) + 1
                )

    for class_id in VALID_CLASS_IDS:
        pixels = result.per_class_pixels.get(class_id, 0)
        result.per_class_fraction[class_id] = (
            pixels / result.valid_pixels if result.valid_pixels else 0.0
        )
        result.samples_without_class[class_id] = sample_count - result.samples_containing_class.get(
            class_id, 0
        )

    counts = [result.per_class_pixels.get(class_id, 0) for class_id in VALID_CLASS_IDS]
    positive = [count for count in counts if count > 0]
    if len(positive) >= 2:
        result.max_min_class_ratio = max(positive) / min(positive)
        if result.max_min_class_ratio > 100.0:
            result.warnings.append(
                f"High class imbalance ratio: {result.max_min_class_ratio:.1f}"
            )
            result.status = "WARNING"

    return result


def _split_channel_means(
    dataset_root: Path | str,
    manifest_payload: dict[str, object],
    split_name: str,
) -> dict[str, tuple[float, float, int]]:
    root = Path(dataset_root)
    splits = manifest_payload.get("splits")
    if not isinstance(splits, dict):
        return {}
    sample_ids = splits.get(split_name, [])
    if not isinstance(sample_ids, list):
        return {}

    stats: dict[str, list[float]] = {name: [] for name in CHANNEL_NAMES}
    for sample_id in sample_ids:
        feature_path = root / str(split_name) / str(sample_id) / "feature_stack.npy"
        if not feature_path.exists():
            continue
        tensor = np.load(feature_path, mmap_mode="r")
        for index, channel_name in enumerate(CHANNEL_NAMES):
            channel = np.asarray(tensor[index])
            valid = channel[channel != FEATURE_NODATA]
            if valid.size:
                stats[channel_name].append(float(np.mean(valid)))

    return {
        name: (float(np.mean(values)), float(np.std(values)), len(values))
        for name, values in stats.items()
        if values
    }


def analyze_feature_distribution_shift(
    dataset_root: Path | str,
    manifest_payload: dict[str, object],
    *,
    z_threshold: float = 3.0,
) -> list[FeatureDistributionShift]:
    train_stats = _split_channel_means(dataset_root, manifest_payload, "train")
    val_stats = _split_channel_means(dataset_root, manifest_payload, "validation")
    test_stats = _split_channel_means(dataset_root, manifest_payload, "test")
    shifts: list[FeatureDistributionShift] = []

    for channel_name in CHANNEL_NAMES:
        shift = FeatureDistributionShift(channel_name=channel_name)
        if channel_name in train_stats:
            shift.train_mean, shift.train_std, _ = train_stats[channel_name]
        if channel_name in val_stats:
            shift.validation_mean, shift.validation_std, _ = val_stats[channel_name]
        if channel_name in test_stats:
            shift.test_mean, shift.test_std, _ = test_stats[channel_name]

        if (
            shift.train_mean is not None
            and shift.test_mean is not None
            and shift.train_std is not None
            and shift.train_std > 0.0
        ):
            z_score = abs(shift.test_mean - shift.train_mean) / shift.train_std
            if z_score >= z_threshold:
                shift.warnings.append(
                    f"Test {channel_name} mean differs from train "
                    f"(z≈{z_score:.2f}, threshold={z_threshold})"
                )

        if (
            shift.train_mean is not None
            and shift.validation_mean is not None
            and shift.train_std is not None
            and shift.train_std > 0.0
        ):
            z_score = abs(shift.validation_mean - shift.train_mean) / shift.train_std
            if z_score >= z_threshold:
                shift.warnings.append(
                    f"Validation {channel_name} mean differs from train "
                    f"(z≈{z_score:.2f}, threshold={z_threshold})"
                )

        shifts.append(shift)

    return shifts


def analyze_class_distribution_from_labels(
    label_result: LabelAuditResult,
) -> ClassDistributionResult:
    return analyze_class_distribution(label_result.samples)


def analyze_distributions(
    dataset_root: Path | str,
    manifest_payload: dict[str, object],
    label_result: LabelAuditResult,
    *,
    config: object | None = None,
) -> DistributionAnalysisResult:
    from ssri_model.scientific.config import ScientificValidationConfig

    cfg = config if isinstance(config, ScientificValidationConfig) else ScientificValidationConfig()
    class_distribution = analyze_class_distribution(label_result.samples)
    feature_shifts = analyze_feature_distribution_shift(
        dataset_root,
        manifest_payload,
        z_threshold=cfg.distribution_shift_z_threshold,
    )
    result = DistributionAnalysisResult(
        class_distribution=class_distribution,
        feature_shifts=feature_shifts,
    )
    result.warnings.extend(class_distribution.warnings)
    for shift in feature_shifts:
        result.warnings.extend(shift.warnings)
    if class_distribution.status != "PASS":
        result.status = class_distribution.status
    elif any(shift.warnings for shift in feature_shifts):
        result.status = "WARNING"
    return result
