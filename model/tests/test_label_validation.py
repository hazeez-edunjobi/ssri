"""Tests for SSRI label scientific validation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio

from ssri_model.ml.constants import FEATURE_NODATA
from ssri_model.scientific.exceptions import LabelAuditError
from ssri_model.scientific.labels import audit_labels, audit_sample_labels
from ssri_model.scientific.validation import audit_labels_only
from tests.evaluation_helpers import grid_spec, write_label
from tests.scientific_helpers import write_evaluation_dataset_with_manifest


class TestLabelValidation:
    def test_valid_labels(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        result = audit_labels_only(manifest_path=manifest_path)
        assert result.status in ("PASS", "WARNING")
        assert result.valid_pixels > 0

    def test_invalid_class(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        sample_dir = tmp_path / "dataset" / "train" / "train-a"
        spec = grid_spec()
        write_label(sample_dir / "label.tif", spec, value=99.0)
        result = audit_labels_only(manifest_path=manifest_path)
        assert result.status == "FAIL"

    def test_missing_label(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        sample_dir = tmp_path / "dataset" / "train" / "train-a"
        (sample_dir / "label.tif").unlink()
        with pytest.raises(LabelAuditError):
            audit_sample_labels(sample_dir, split="train", expected_crs="EPSG:32613")

    def test_excessive_nodata(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        sample_dir = tmp_path / "dataset" / "train" / "train-a"
        spec = grid_spec()
        profile = {
            "driver": "GTiff",
            "height": spec.height,
            "width": spec.width,
            "count": 1,
            "dtype": "float32",
            "crs": spec.crs,
            "transform": spec.transform,
            "nodata": FEATURE_NODATA,
        }
        with rasterio.open(sample_dir / "label.tif", "w", **profile) as dataset:
            dataset.write(np.full(spec.shape, FEATURE_NODATA, dtype=np.float32), 1)
        result = audit_labels(manifest_path.parent, json.loads(manifest_path.read_text()))
        assert any("zero labelled pixels" in warning for warning in result.warnings)

    def test_label_crs_mismatch(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        sample_dir = tmp_path / "dataset" / "train" / "train-a"
        spec = grid_spec()
        profile = {
            "driver": "GTiff",
            "height": spec.height,
            "width": spec.width,
            "count": 1,
            "dtype": "float32",
            "crs": rasterio.crs.CRS.from_epsg(4326),
            "transform": spec.transform,
            "nodata": FEATURE_NODATA,
        }
        with rasterio.open(sample_dir / "label.tif", "w", **profile) as dataset:
            dataset.write(np.zeros(spec.shape, dtype=np.float32), 1)
        result = audit_labels_only(manifest_path=manifest_path)
        assert result.status == "FAIL"
