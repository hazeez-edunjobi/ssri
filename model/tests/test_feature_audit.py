"""Tests for SSRI feature scientific validation."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ssri_model.ml.constants import CHANNEL_COUNT, FEATURE_NODATA
from ssri_model.scientific.feature_audit import audit_sample_features
from ssri_model.scientific.validation import audit_features_only
from tests.scientific_helpers import write_evaluation_dataset_with_manifest


class TestFeatureAudit:
    def test_valid_channels(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        result = audit_features_only(manifest_path=manifest_path)
        assert result.status in ("PASS", "WARNING")
        assert len(result.channels) == CHANNEL_COUNT

    def test_nan_detection(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        sample_dir = tmp_path / "dataset" / "train" / "train-a"
        tensor = np.load(sample_dir / "feature_stack.npy")
        tensor[0, 0, 0] = np.nan
        np.save(sample_dir / "feature_stack.npy", tensor)
        audits = audit_sample_features(sample_dir)
        assert any("NaN" in warning for audit in audits for warning in audit.warnings)

    def test_inf_detection(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        sample_dir = tmp_path / "dataset" / "train" / "train-a"
        tensor = np.load(sample_dir / "feature_stack.npy")
        tensor[1, 0, 0] = np.inf
        np.save(sample_dir / "feature_stack.npy", tensor)
        audits = audit_sample_features(sample_dir)
        assert any("Inf" in warning for audit in audits for warning in audit.warnings)

    def test_all_nodata_channel(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        sample_dir = tmp_path / "dataset" / "train" / "train-a"
        tensor = np.load(sample_dir / "feature_stack.npy")
        tensor[2, :, :] = FEATURE_NODATA
        np.save(sample_dir / "feature_stack.npy", tensor)
        audits = audit_sample_features(sample_dir)
        assert any(audit.status == "FAIL" for audit in audits if audit.channel_name == "plan_curvature")

    def test_constant_channel(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        sample_dir = tmp_path / "dataset" / "train" / "train-a"
        tensor = np.load(sample_dir / "feature_stack.npy")
        tensor[3, :, :] = 5.0
        np.save(sample_dir / "feature_stack.npy", tensor)
        audits = audit_sample_features(sample_dir)
        assert any(audit.constant_value for audit in audits if audit.channel_name == "profile_curvature")

    def test_nodata_fraction(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        sample_dir = tmp_path / "dataset" / "train" / "train-a"
        tensor = np.load(sample_dir / "feature_stack.npy")
        tensor[:, 0, :] = FEATURE_NODATA
        np.save(sample_dir / "feature_stack.npy", tensor)
        audits = audit_sample_features(sample_dir)
        assert any(audit.nodata_fraction > 0 for audit in audits)
