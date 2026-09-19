"""Tests for SSRI evaluation safety checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ssri_model.architecture import create_ssri_model
from ssri_model.evaluation import (
    EvaluationConfig,
    EvaluationDataLeakageError,
    InvalidEvaluationConfigError,
    check_test_split_leakage,
    validate_evaluation_setup,
)
from tests.evaluation_helpers import save_manual_checkpoint, write_evaluation_dataset


class TestEvaluationSafety:
    def test_missing_test_split(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "dataset_name": "demo",
                    "version": "0.1.0",
                    "created_at": "2026-08-08T00:00:00+00:00",
                    "channels": ["elevation"] * 13,
                    "label_classes": ["subsidence", "landslide", "sinkhole"],
                    "resolution": 30.0,
                    "crs": "EPSG:32613",
                    "normalization": {},
                    "train_count": 1,
                    "validation_count": 0,
                    "test_count": 0,
                    "splits": {"train": ["a"], "validation": [], "test": []},
                }
            ),
            encoding="utf-8",
        )
        config = EvaluationConfig(
            checkpoint_path=str(tmp_path / "model.pt"),
            dataset_manifest=str(manifest),
            output_dir=str(tmp_path / "out"),
        )
        config.checkpoint.write_text("x", encoding="utf-8")
        with pytest.raises(InvalidEvaluationConfigError):
            validate_evaluation_setup(config)

    def test_overlapping_train_test_ids(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "dataset_name": "demo",
                    "version": "0.1.0",
                    "created_at": "2026-08-08T00:00:00+00:00",
                    "channels": ["elevation"] * 13,
                    "label_classes": ["subsidence", "landslide", "sinkhole"],
                    "resolution": 30.0,
                    "crs": "EPSG:32613",
                    "normalization": {},
                    "train_count": 1,
                    "validation_count": 0,
                    "test_count": 1,
                    "splits": {
                        "train": ["shared"],
                        "validation": [],
                        "test": ["shared"],
                    },
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(EvaluationDataLeakageError):
            check_test_split_leakage(manifest)

    def test_incompatible_dataset_identity(self, tmp_path: Path) -> None:
        dataset_root, manifest_path = write_evaluation_dataset(tmp_path / "dataset")
        _ = dataset_root
        checkpoint_path = save_manual_checkpoint(
            tmp_path / "checkpoint.pt",
            dataset_identity={"dataset_name": "other", "version": "9.9.9"},
        )
        from ssri_model.evaluation.evaluator import load_evaluation_model

        with pytest.raises(Exception):
            load_evaluation_model(
                checkpoint_path,
                device=__import__("torch").device("cpu"),
                expected_dataset_identity={
                    "dataset_name": "synthetic-eval",
                    "version": "0.1.0",
                },
            )

    def test_incompatible_model_channels(self) -> None:
        from ssri_model.architecture import SSRIModelConfig, create_ssri_model

        model = create_ssri_model(SSRIModelConfig(in_channels=12, num_classes=3))
        with pytest.raises(InvalidEvaluationConfigError):
            validate_evaluation_setup(
                EvaluationConfig(
                    checkpoint_path="x.pt",
                    dataset_manifest="m.json",
                    output_dir="out",
                ),
                model=model,
            )

    def test_validate_setup_accepts_valid_dataset(self, tmp_path: Path) -> None:
        _, manifest_path = write_evaluation_dataset(tmp_path / "dataset")
        checkpoint_path = save_manual_checkpoint(
            tmp_path / "checkpoint.pt",
            dataset_identity={"dataset_name": "synthetic-eval", "version": "0.1.0"},
        )
        config = EvaluationConfig(
            checkpoint_path=str(checkpoint_path),
            dataset_manifest=str(manifest_path),
            output_dir=str(tmp_path / "out"),
        )
        manifest = validate_evaluation_setup(config, model=create_ssri_model())
        assert manifest.dataset_name == "synthetic-eval"
