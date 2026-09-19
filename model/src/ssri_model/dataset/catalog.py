"""Dataset catalog and statistics generation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ssri_model import __version__
from ssri_model.ml.constants import CHANNEL_NAMES, DEFAULT_RESOLUTION, FEATURE_NODATA
from ssri_model.ml.dataset_spec import DatasetManifest
from ssri_model.ml.normalization import NormalizationConfig
from ssri_model.ml.splits import DatasetSplit, SplitName

ML_CONTRACT_VERSION = "2.0"
STAGE1_VERSION = __version__


@dataclass(frozen=True)
class DatasetStatistics:
    """Aggregate dataset statistics for QA and training prep."""

    sample_count: int
    train_count: int
    validation_count: int
    test_count: int
    channel_names: tuple[str, ...]
    channel_stats: dict[str, dict[str, float]]
    label_present_count: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        """Convert statistics to a JSON-serializable dictionary."""
        return asdict(self)


def _channel_statistics(samples: Sequence[Path]) -> dict[str, dict[str, float]]:
    """Compute per-channel summary statistics across samples."""
    if not samples:
        return {
            name: {
                "min": 0.0,
                "max": 0.0,
                "mean": 0.0,
                "std": 0.0,
                "valid_count": 0,
                "nodata_count": 0,
            }
            for name in CHANNEL_NAMES
        }

    stacked = []
    for sample_dir in samples:
        tensor = np.load(sample_dir / "feature_stack.npy")
        stacked.append(tensor)

    array = np.stack(stacked, axis=0)
    stats: dict[str, dict[str, float]] = {}
    for index, name in enumerate(CHANNEL_NAMES):
        channel = array[:, index, :, :]
        valid = channel[channel != FEATURE_NODATA]
        total = int(channel.size)
        valid_count = int(valid.size)
        nodata_count = total - valid_count
        if valid_count == 0:
            stats[name] = {
                "min": 0.0,
                "max": 0.0,
                "mean": 0.0,
                "std": 0.0,
                "valid_count": 0.0,
                "nodata_count": float(nodata_count),
            }
            continue
        stats[name] = {
            "min": float(np.min(valid)),
            "max": float(np.max(valid)),
            "mean": float(np.mean(valid)),
            "std": float(np.std(valid)),
            "valid_count": float(valid_count),
            "nodata_count": float(nodata_count),
        }
    return stats


def _collect_sample_dirs(root: Path, split: SplitName) -> list[Path]:
    split_dir = root / split
    if not split_dir.exists():
        return []
    return sorted(path for path in split_dir.iterdir() if path.is_dir())


def write_statistics(
    dataset_root: Path | str,
    *,
    split: DatasetSplit,
    created_at: str | None = None,
) -> Path:
    """Write ``statistics.json`` for a generated dataset."""
    root = Path(dataset_root)
    all_samples = (
        _collect_sample_dirs(root, "train")
        + _collect_sample_dirs(root, "validation")
        + _collect_sample_dirs(root, "test")
    )

    label_present_count = sum(
        1 for sample_dir in all_samples if (sample_dir / "label.tif").exists()
    )

    statistics = DatasetStatistics(
        sample_count=len(all_samples),
        train_count=len(split.train),
        validation_count=len(split.validation),
        test_count=len(split.test),
        channel_names=CHANNEL_NAMES,
        channel_stats=_channel_statistics(all_samples),
        label_present_count=label_present_count,
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
    )

    destination = root / "statistics.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(statistics.to_dict(), handle, indent=2)
    return destination


def write_manifest(
    dataset_root: Path | str,
    *,
    dataset_name: str,
    version: str,
    split: DatasetSplit,
    crs: str,
    resolution_m: float = DEFAULT_RESOLUTION,
    normalization: NormalizationConfig | None = None,
    created_at: str | None = None,
) -> Path:
    """Write ``manifest.json`` for a generated dataset."""
    root = Path(dataset_root)
    manifest = DatasetManifest.create(
        dataset_name=dataset_name,
        version=version,
        resolution=resolution_m,
        crs=crs,
        normalization=normalization,
        train_count=len(split.train),
        validation_count=len(split.validation),
        test_count=len(split.test),
        created_at=created_at,
    )

    payload: dict[str, Any] = manifest.to_dict()
    payload.update(
        {
            "stage1_version": STAGE1_VERSION,
            "ml_contract_version": ML_CONTRACT_VERSION,
            "splits": {
                "train": list(split.train),
                "validation": list(split.validation),
                "test": list(split.test),
            },
        }
    )

    destination = root / "manifest.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return destination


def load_catalog_manifest(path: Path | str) -> Mapping[str, Any]:
    """Load a catalog manifest JSON document."""
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)
