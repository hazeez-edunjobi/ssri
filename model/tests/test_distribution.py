"""Tests for SSRI distribution and leakage analysis."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ssri_model.scientific.distribution import analyze_distributions
from ssri_model.scientific.leakage import validate_dataset_independence
from ssri_model.scientific.validation import audit_labels_only
from tests.scientific_helpers import write_evaluation_dataset_with_manifest


class TestDistribution:
    def test_balanced_dataset(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        label_result = audit_labels_only(manifest_path=manifest_path)
        result = analyze_distributions(
            manifest_path.parent,
            json.loads(manifest_path.read_text(encoding="utf-8")),
            label_result,
        )
        assert result.class_distribution.valid_pixels > 0

    def test_train_test_distribution_shift(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        test_sample = tmp_path / "dataset" / "test" / "test-a" / "feature_stack.npy"
        tensor = __import__("numpy").load(test_sample)
        tensor += 1000.0
        __import__("numpy").save(test_sample, tensor)
        label_result = audit_labels_only(manifest_path=manifest_path)
        result = analyze_distributions(
            manifest_path.parent,
            json.loads(manifest_path.read_text(encoding="utf-8")),
            label_result,
            config=__import__(
                "ssri_model.scientific.config", fromlist=["ScientificValidationConfig"]
            ).ScientificValidationConfig(distribution_shift_z_threshold=0.1),
        )
        assert any(shift.warnings for shift in result.feature_shifts)


class TestLeakage:
    def test_duplicate_ids(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["splits"]["test"].append("train-a")
        report = validate_dataset_independence(manifest_path.parent, payload)
        assert report.independent is False

    def test_duplicate_paths(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        source = tmp_path / "dataset" / "train" / "train-a"
        target = tmp_path / "dataset" / "test" / "test-a"
        shutil.copy(source / "feature_stack.npy", target / "feature_stack.npy")
        report = validate_dataset_independence(
            manifest_path.parent,
            json.loads(manifest_path.read_text(encoding="utf-8")),
        )
        assert report.duplicate_feature_hashes or report.feature_path_overlap

    def test_spatial_overlap_reported(self, tmp_path: Path) -> None:
        from tests.scientific_helpers import write_spatial_dataset

        manifest_path, _ = write_spatial_dataset(tmp_path / "dataset", overlapping=True)
        report = validate_dataset_independence(
            manifest_path.parent,
            json.loads(manifest_path.read_text(encoding="utf-8")),
        )
        assert report.spatial_overlap_count >= 1
