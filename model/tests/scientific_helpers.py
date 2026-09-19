"""Shared helpers for SSRI scientific validation tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ssri_model.dataset.catalog import write_manifest
from ssri_model.ml.constants import CHANNEL_COUNT
from ssri_model.ml.splits import DatasetSplit
from ssri_model.ml.statistics_loader import compute_feature_statistics_from_arrays
from tests.evaluation_helpers import grid_spec, write_label, write_sample


def write_evaluation_dataset_with_manifest(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    train_ids = ["train-a", "train-b"]
    val_ids = ["val-a"]
    test_ids = ["test-a", "test-b"]
    train_tensors = []
    for index, sample_id in enumerate(train_ids):
        train_tensors.append(
            write_sample(
                root / "train" / sample_id,
                label_value=float(index % 3),
                channel_offset=float(index),
            )
        )
    for index, sample_id in enumerate(val_ids):
        write_sample(
            root / "validation" / sample_id,
            label_value=float(index % 3),
            channel_offset=float(index + 10),
        )
    for index, sample_id in enumerate(test_ids):
        write_sample(
            root / "test" / sample_id,
            label_value=float(index % 3),
            channel_offset=float(index + 20),
        )

    split = DatasetSplit(train=tuple(train_ids), validation=tuple(val_ids), test=tuple(test_ids))
    manifest_path = write_manifest(
        root,
        dataset_name="scientific-eval",
        version="0.1.0",
        split=split,
        crs="EPSG:32613",
    )
    stats = compute_feature_statistics_from_arrays(train_tensors)
    statistics_payload = {
        "sample_count": len(train_ids) + len(val_ids) + len(test_ids),
        "train_count": len(train_ids),
        "validation_count": len(val_ids),
        "test_count": len(test_ids),
        "channel_names": list(stats.channel_names),
        "channel_stats": {
            name: {
                "min": stat.min,
                "max": stat.max,
                "mean": stat.mean,
                "std": stat.std,
                "valid_count": stat.valid_count,
                "nodata_count": stat.nodata_count,
            }
            for name, stat in stats.channels.items()
        },
        "label_present_count": len(train_ids) + len(val_ids) + len(test_ids),
        "created_at": "2026-08-08T09:00:00+00:00",
    }
    statistics_path = root / "statistics.json"
    statistics_path.write_text(json.dumps(statistics_payload), encoding="utf-8")
    return manifest_path, statistics_path


def write_spatial_sample(
    sample_dir: Path,
    *,
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    label_value: float = 0.0,
) -> None:
    sample_dir.mkdir(parents=True, exist_ok=True)
    spec = grid_spec()
    tensor = np.stack(
        [
            np.full((spec.height, spec.width), float(index + 1), dtype=np.float64)
            for index in range(CHANNEL_COUNT)
        ],
        axis=0,
    )
    np.save(sample_dir / "feature_stack.npy", tensor)
    write_label(sample_dir / "label.tif", spec, value=label_value)
    metadata = {
        "sample_id": sample_dir.name,
        "aoi": {
            "bbox_wgs84": {
                "min_lon": min_lon,
                "min_lat": min_lat,
                "max_lon": max_lon,
                "max_lat": max_lat,
            }
        },
        "acquisition": {"start_date": "2024-01-01", "end_date": "2024-02-01"},
        "resolution_m": 30.0,
        "crs": str(spec.crs),
        "sources": {"dem": "COP30"},
        "package_version": "0.1.0",
        "created_at": "2026-08-08T09:00:00+00:00",
    }
    (sample_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (sample_dir / "preview.png").write_bytes(b"png")


def write_spatial_dataset(root: Path, *, overlapping: bool = False) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    if overlapping:
        write_spatial_sample(
            root / "train" / "train-a",
            min_lon=-1.0,
            min_lat=50.0,
            max_lon=1.0,
            max_lat=52.0,
        )
        write_spatial_sample(
            root / "test" / "test-a",
            min_lon=-0.5,
            min_lat=50.5,
            max_lon=0.5,
            max_lat=51.5,
        )
    else:
        write_spatial_sample(
            root / "train" / "train-a",
            min_lon=-2.0,
            min_lat=50.0,
            max_lon=-1.0,
            max_lat=51.0,
        )
        write_spatial_sample(
            root / "test" / "test-a",
            min_lon=1.0,
            min_lat=50.0,
            max_lon=2.0,
            max_lat=51.0,
        )
    split = DatasetSplit(train=("train-a",), validation=(), test=("test-a",))
    manifest_path = write_manifest(
        root,
        dataset_name="spatial-eval",
        version="0.1.0",
        split=split,
        crs="EPSG:32613",
    )
    statistics_path = root / "statistics.json"
    tensor = np.load(root / "train" / "train-a" / "feature_stack.npy")
    stats = compute_feature_statistics_from_arrays([tensor])
    statistics_path.write_text(
        json.dumps(
            {
                "channel_stats": {
                    name: {
                        "min": stat.min,
                        "max": stat.max,
                        "mean": stat.mean,
                        "std": stat.std,
                        "valid_count": stat.valid_count,
                        "nodata_count": stat.nodata_count,
                    }
                    for name, stat in stats.channels.items()
                }
            }
        ),
        encoding="utf-8",
    )
    return manifest_path, statistics_path
