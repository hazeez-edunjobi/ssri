"""Feature audit utilities for SSRI scientific validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np

from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES, FEATURE_NODATA
from ssri_model.scientific.exceptions import FeatureAuditError

AuditStatus = Literal["PASS", "WARNING", "FAIL"]


@dataclass
class ChannelFeatureAudit:
    """Feature audit for one channel."""

    channel_name: str
    min: float = 0.0
    max: float = 0.0
    mean: float = 0.0
    std: float = 0.0
    valid_count: int = 0
    nodata_count: int = 0
    nodata_fraction: float = 0.0
    finite_count: int = 0
    nan_count: int = 0
    inf_count: int = 0
    constant_value: bool = False
    warnings: list[str] = field(default_factory=list)
    status: AuditStatus = "PASS"


@dataclass
class FeatureAuditResult:
    """Aggregate feature audit output."""

    channels: list[ChannelFeatureAudit] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: AuditStatus = "PASS"


def _audit_channel(
    values: np.ndarray,
    channel_name: str,
    *,
    constant_std_threshold: float,
    max_nodata_fraction: float,
) -> ChannelFeatureAudit:
    audit = ChannelFeatureAudit(channel_name=channel_name)
    total = int(values.size)
    nodata_mask = values == FEATURE_NODATA
    audit.nodata_count = int(np.sum(nodata_mask))
    audit.nodata_fraction = audit.nodata_count / total if total else 1.0
    finite_mask = np.isfinite(values) & ~nodata_mask
    audit.finite_count = int(np.sum(finite_mask))
    audit.nan_count = int(np.sum(np.isnan(values)))
    audit.inf_count = int(np.sum(np.isinf(values)))
    audit.valid_count = audit.finite_count

    if audit.nan_count > 0:
        audit.warnings.append("NaN values detected")
        audit.status = "WARNING"
    if audit.inf_count > 0:
        audit.warnings.append("Inf values detected")
        audit.status = "WARNING"
    if audit.valid_count == 0:
        audit.warnings.append("All-nodata channel")
        audit.status = "FAIL"
    else:
        valid = values[finite_mask].astype(np.float64)
        audit.min = float(np.min(valid))
        audit.max = float(np.max(valid))
        audit.mean = float(np.mean(valid))
        audit.std = float(np.std(valid))
        if audit.std <= constant_std_threshold:
            audit.constant_value = True
            audit.warnings.append("Near-constant channel")
            if audit.status == "PASS":
                audit.status = "WARNING"

    if audit.nodata_fraction > max_nodata_fraction:
        audit.warnings.append(
            f"Nodata fraction {audit.nodata_fraction:.3f} exceeds threshold"
        )
        if audit.status == "PASS":
            audit.status = "WARNING"

    return audit


def audit_sample_features(
    sample_dir: Path,
    *,
    config: object | None = None,
) -> list[ChannelFeatureAudit]:
    from ssri_model.scientific.config import ScientificValidationConfig

    cfg = config if isinstance(config, ScientificValidationConfig) else ScientificValidationConfig()
    feature_path = sample_dir / "feature_stack.npy"
    if not feature_path.exists():
        raise FeatureAuditError(f"Missing feature stack: {feature_path}")

    tensor = np.load(feature_path, mmap_mode="r")
    if tensor.shape[0] != CHANNEL_COUNT:
        raise FeatureAuditError(
            f"Expected {CHANNEL_COUNT} channels, received {tensor.shape[0]}"
        )

    audits: list[ChannelFeatureAudit] = []
    for index, channel_name in enumerate(CHANNEL_NAMES):
        audits.append(
            _audit_channel(
                np.asarray(tensor[index]),
                channel_name,
                constant_std_threshold=cfg.constant_channel_std_threshold,
                max_nodata_fraction=cfg.max_nodata_fraction,
            )
        )
    return audits


def audit_features(
    dataset_root: Path,
    manifest_payload: dict[str, object],
    *,
    config: object | None = None,
) -> FeatureAuditResult:
    from ssri_model.scientific.config import ScientificValidationConfig

    cfg = config if isinstance(config, ScientificValidationConfig) else ScientificValidationConfig()
    result = FeatureAuditResult()
    splits = manifest_payload.get("splits")
    if not isinstance(splits, dict):
        raise FeatureAuditError("Manifest is missing splits section")

    for split_name, sample_ids in splits.items():
        if not isinstance(sample_ids, list):
            continue
        for sample_id in sample_ids:
            sample_dir = dataset_root / str(split_name) / str(sample_id)
            sample_audits = audit_sample_features(sample_dir, config=cfg)
            for audit in sample_audits:
                if audit.status == "FAIL":
                    result.status = "FAIL"
                elif audit.status == "WARNING" and result.status == "PASS":
                    result.status = "WARNING"
                result.warnings.extend(
                    f"{sample_id}/{audit.channel_name}: {warning}"
                    for warning in audit.warnings
                )

    for channel_name in CHANNEL_NAMES:
        channel_values: list[float] = []
        nodata_total = 0
        valid_total = 0
        for split_name, sample_ids in splits.items():
            if not isinstance(sample_ids, list):
                continue
            for sample_id in sample_ids:
                feature_path = dataset_root / str(split_name) / str(sample_id) / "feature_stack.npy"
                if not feature_path.exists():
                    continue
                tensor = np.load(feature_path, mmap_mode="r")
                index = CHANNEL_NAMES.index(channel_name)
                channel = np.asarray(tensor[index])
                valid = channel[channel != FEATURE_NODATA]
                nodata_total += int(channel.size - valid.size)
                valid_total += int(valid.size)
                if valid.size:
                    channel_values.append(float(np.mean(valid)))

        if not channel_values:
            audit = ChannelFeatureAudit(channel_name=channel_name)
            audit.warnings.append("No valid pixels aggregated for channel")
            audit.status = "FAIL"
        else:
            values_array = np.array(channel_values, dtype=np.float64)
            audit = ChannelFeatureAudit(
                channel_name=channel_name,
                min=float(np.min(values_array)),
                max=float(np.max(values_array)),
                mean=float(np.mean(values_array)),
                std=float(np.std(values_array)),
                valid_count=valid_total,
                nodata_count=nodata_total,
                nodata_fraction=nodata_total / (valid_total + nodata_total)
                if (valid_total + nodata_total)
                else 1.0,
                finite_count=valid_total,
            )
            if audit.std <= cfg.constant_channel_std_threshold:
                audit.constant_value = True
                audit.warnings.append("Near-constant channel across samples")
                audit.status = "WARNING"

        result.channels.append(audit)
        if audit.status == "FAIL":
            result.status = "FAIL"
        elif audit.status == "WARNING" and result.status == "PASS":
            result.status = "WARNING"

    return result
