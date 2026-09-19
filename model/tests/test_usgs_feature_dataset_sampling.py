"""Unit tests for USGS FeatureStack dataset sampling (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ssri_model.scripts.build_usgs_feature_dataset import (
    TrainingPoint,
    generate_pseudo_absences,
    spatial_block_split,
    stratified_positive_sample,
)


def test_stratified_positive_sample_conus_only(tmp_path: Path) -> None:
    rows = [
        {
            "sample_id": "ak",
            "latitude": 61.0,
            "longitude": -149.0,
            "labels": {"landslide": 1},
            "dataset_name": "usgs",
            "dataset_version": "3.0",
            "quality_flags": [],
        },
        {
            "sample_id": "az1",
            "latitude": 36.0,
            "longitude": -112.0,
            "labels": {"landslide": 1},
            "dataset_name": "usgs",
            "dataset_version": "3.0",
            "quality_flags": ["confidence=5"],
        },
        {
            "sample_id": "ca1",
            "latitude": 37.5,
            "longitude": -119.0,
            "labels": {"landslide": 1},
            "dataset_name": "usgs",
            "dataset_version": "3.0",
            "quality_flags": [],
        },
    ]
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )
    selected = stratified_positive_sample(catalog, n_positives=2, seed=0)
    assert len(selected) == 2
    assert all(p.sample_id != "ak" for p in selected)
    assert all(p.landslide == 1 for p in selected)


def test_pseudo_absences_respect_full_inventory_buffer() -> None:
    positives = [
        TrainingPoint(
            sample_id="p1",
            latitude=40.0,
            longitude=-105.0,
            landslide=1,
            provenance={"spatial_block": "b20_-53"},
        )
    ]
    # Inventory includes the positive and a nearby point
    inventory = np.array([[40.0, -105.0], [40.05, -105.05]], dtype=np.float64)
    absences = generate_pseudo_absences(
        positives,
        inventory,
        n_absences=5,
        seed=1,
        min_distance_km=15.0,
        max_distance_km=40.0,
        min_inter_absence_km=3.0,
    )
    assert len(absences) == 5
    assert all(a.landslide == 0 for a in absences)
    assert all("pseudo_absence=true" in a.provenance["quality_flags"] for a in absences)
    assert all(
        a.provenance.get("method")
        == "offset_from_inventory_positive_full_inventory_buffer"
        for a in absences
    )


def test_spatial_block_split_disjoint() -> None:
    points = [
        TrainingPoint(
            f"s{i}",
            30.0 + i,
            -100.0,
            1 if i % 2 == 0 else 0,
            {"spatial_block": f"block{i // 2}"},
        )
        for i in range(8)
    ]
    splits = spatial_block_split(points, seed=3)
    train, val, test = set(splits["train"]), set(splits["validation"]), set(splits["test"])
    assert not (train & val)
    assert not (train & test)
    assert not (val & test)
    assert train | val | test == {p.sample_id for p in points}
