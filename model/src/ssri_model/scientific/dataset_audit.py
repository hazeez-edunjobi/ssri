"""Dataset integrity audit for SSRI scientific validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ssri_model.dataset.catalog import load_catalog_manifest
from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES
from ssri_model.ml.dataset_spec import DatasetManifest
from ssri_model.ml.statistics_loader import load_feature_statistics
from ssri_model.scientific.exceptions import DatasetAuditError

AuditStatus = Literal["PASS", "WARNING", "FAIL"]


@dataclass
class DatasetAuditResult:
    """Structured dataset audit output."""

    dataset_name: str
    dataset_version: str
    sample_count: int = 0
    train_count: int = 0
    validation_count: int = 0
    test_count: int = 0
    channel_count: int = CHANNEL_COUNT
    channel_order: tuple[str, ...] = CHANNEL_NAMES
    resolution: float | None = None
    crs: str | None = None
    label_classes: tuple[str, ...] = field(default_factory=tuple)
    duplicate_sample_ids: list[str] = field(default_factory=list)
    duplicate_feature_paths: list[tuple[str, str]] = field(default_factory=list)
    duplicate_label_paths: list[tuple[str, str]] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    unreadable_files: list[str] = field(default_factory=list)
    malformed_metadata: list[str] = field(default_factory=list)
    feature_statistics_present: bool = False
    warnings: list[str] = field(default_factory=list)
    status: AuditStatus = "PASS"


def _resolve_dataset_root(manifest_path: Path) -> Path:
    if manifest_path.is_file():
        return manifest_path.parent
    return manifest_path


def audit_dataset(
    *,
    manifest_path: Path | str,
    statistics_path: Path | str | None = None,
) -> DatasetAuditResult:
    """Audit dataset integrity without modifying source files."""
    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        raise DatasetAuditError(f"Manifest not found: {manifest_file}")

    dataset_root = _resolve_dataset_root(manifest_file)
    try:
        payload = load_catalog_manifest(manifest_file)
        manifest = DatasetManifest.load(manifest_file)
    except Exception as exc:
        raise DatasetAuditError(f"Unable to load manifest: {manifest_file}") from exc

    stats_path = Path(statistics_path) if statistics_path else dataset_root / "statistics.json"
    result = DatasetAuditResult(
        dataset_name=manifest.dataset_name,
        dataset_version=manifest.version,
        resolution=manifest.resolution,
        crs=manifest.crs,
        label_classes=manifest.label_classes,
        train_count=manifest.train_count,
        validation_count=manifest.validation_count,
        test_count=manifest.test_count,
    )

    if tuple(manifest.channels) != CHANNEL_NAMES:
        result.warnings.append("Manifest channel order differs from canonical CHANNEL_NAMES")
        result.status = "FAIL"

    splits = payload.get("splits")
    if not isinstance(splits, dict):
        result.warnings.append("Manifest missing splits section")
        result.status = "FAIL"
        return result

    seen_ids: dict[str, str] = {}
    feature_paths: dict[str, str] = {}
    label_paths: dict[str, str] = {}

    for split_name, sample_ids in splits.items():
        if not isinstance(sample_ids, list):
            continue
        for sample_id in sample_ids:
            result.sample_count += 1
            sid = str(sample_id)
            if sid in seen_ids:
                result.duplicate_sample_ids.append(sid)
                result.status = "FAIL"
            seen_ids[sid] = str(split_name)

            sample_dir = dataset_root / str(split_name) / sid
            required = ("feature_stack.npy", "label.tif", "metadata.json")
            for filename in required:
                path = sample_dir / filename
                if not path.exists():
                    result.missing_files.append(str(path))
                    result.status = "FAIL"

            feature_path = sample_dir / "feature_stack.npy"
            label_path = sample_dir / "label.tif"
            metadata_path = sample_dir / "metadata.json"

            feature_key = str(feature_path.resolve()) if feature_path.exists() else ""
            if feature_key:
                if feature_key in feature_paths.values():
                    other = next(
                        key for key, value in feature_paths.items() if value == feature_key
                    )
                    result.duplicate_feature_paths.append((sid, other))
                    result.status = "WARNING"
                feature_paths[sid] = feature_key

            label_key = str(label_path.resolve()) if label_path.exists() else ""
            if label_key:
                if label_key in label_paths.values():
                    other = next(
                        key for key, value in label_paths.items() if value == label_key
                    )
                    result.duplicate_label_paths.append((sid, other))
                    result.status = "WARNING"
                label_paths[sid] = label_key

            if metadata_path.exists():
                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    if not metadata.get("sample_id"):
                        result.malformed_metadata.append(sid)
                        result.status = "WARNING"
                except (OSError, json.JSONDecodeError):
                    result.unreadable_files.append(str(metadata_path))
                    result.status = "FAIL"

            if feature_path.exists():
                try:
                    import numpy as np

                    tensor = np.load(feature_path, mmap_mode="r")
                    if tensor.shape[0] != CHANNEL_COUNT:
                        result.warnings.append(
                            f"{sid}: feature stack has {tensor.shape[0]} channels"
                        )
                        result.status = "FAIL"
                except (OSError, ValueError):
                    result.unreadable_files.append(str(feature_path))
                    result.status = "FAIL"

    if stats_path.exists():
        try:
            load_feature_statistics(stats_path)
            result.feature_statistics_present = True
        except Exception as exc:
            result.warnings.append(f"Statistics file invalid: {exc}")
            result.status = "WARNING"
    else:
        result.warnings.append(f"Statistics file missing: {stats_path}")
        result.status = "WARNING"

    return result
