"""Tests for SSRI spatial scientific validation."""

from __future__ import annotations

from pathlib import Path

from ssri_model.scientific.spatial import (
    BoundingBox,
    check_spatial_overlap,
    compute_spatial_distance,
    validate_spatial_splits,
)
from ssri_model.scientific.validation import audit_spatial_only
from tests.scientific_helpers import write_spatial_dataset


class TestSpatialValidation:
    def test_overlapping_tiles(self) -> None:
        a = {"aoi": {"bbox_wgs84": {"min_lon": -1, "min_lat": 50, "max_lon": 1, "max_lat": 52}}}
        b = {"aoi": {"bbox_wgs84": {"min_lon": -0.5, "min_lat": 50.5, "max_lon": 0.5, "max_lat": 51.5}}}
        assert check_spatial_overlap(a, b) is True

    def test_separated_tiles(self) -> None:
        a = {"aoi": {"bbox_wgs84": {"min_lon": -2, "min_lat": 50, "max_lon": -1, "max_lat": 51}}}
        b = {"aoi": {"bbox_wgs84": {"min_lon": 1, "min_lat": 50, "max_lon": 2, "max_lat": 51}}}
        assert check_spatial_overlap(a, b) is False
        distance = compute_spatial_distance(a, b)
        assert distance is not None
        assert distance > 0.0

    def test_spatial_buffer_violation(self) -> None:
        a = {"aoi": {"bbox_wgs84": {"min_lon": -1, "min_lat": 50, "max_lon": -0.9, "max_lat": 50.1}}}
        b = {"aoi": {"bbox_wgs84": {"min_lon": -0.89, "min_lat": 50, "max_lon": -0.8, "max_lat": 50.1}}}
        result = validate_spatial_splits(
            {"train": {"a": a}, "validation": {}, "test": {"b": b}},
            spatial_buffer_m=50_000.0,
        )
        assert result.status in ("WARNING", "FAIL")

    def test_dataset_spatial_audit_overlapping(self, tmp_path: Path) -> None:
        manifest_path, _ = write_spatial_dataset(tmp_path / "dataset", overlapping=True)
        result = audit_spatial_only(manifest_path=manifest_path)
        assert result.overlapping_samples

    def test_dataset_spatial_audit_separated(self, tmp_path: Path) -> None:
        manifest_path, _ = write_spatial_dataset(tmp_path / "dataset", overlapping=False)
        result = audit_spatial_only(manifest_path=manifest_path)
        assert result.status == "PASS"

    def test_bbox_helpers(self) -> None:
        box = BoundingBox(min_lon=0, min_lat=0, max_lon=1, max_lat=1)
        assert box.overlaps(BoundingBox(min_lon=0.5, min_lat=0.5, max_lon=1.5, max_lat=1.5))
