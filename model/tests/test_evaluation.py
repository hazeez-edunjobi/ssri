"""Tests for SSRI evaluation configuration and evaluator."""

from __future__ import annotations

from pathlib import Path

import pytest
import torch

from ssri_model.evaluation import (
    EVALUATION_JSON_NAME,
    EvaluationConfig,
    Evaluator,
    evaluate_checkpoint,
)
from ssri_model.evaluation.exceptions import InvalidEvaluationConfigError
from tests.evaluation_helpers import (
    train_and_save_checkpoint,
    write_evaluation_dataset,
)


class TestEvaluationConfig:
    def test_valid_configuration(self, tmp_path: Path) -> None:
        checkpoint = tmp_path / "model.pt"
        checkpoint.write_text("placeholder", encoding="utf-8")
        manifest = tmp_path / "manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        config = EvaluationConfig(
            checkpoint_path=str(checkpoint),
            dataset_manifest=str(manifest),
            output_dir=str(tmp_path / "out"),
        )
        assert config.batch_size == 4

    def test_invalid_batch_size(self) -> None:
        with pytest.raises(InvalidEvaluationConfigError):
            EvaluationConfig(
                checkpoint_path="a.pt",
                dataset_manifest="manifest.json",
                output_dir="out",
                batch_size=0,
            )

    def test_invalid_device(self) -> None:
        with pytest.raises(InvalidEvaluationConfigError):
            EvaluationConfig(
                checkpoint_path="a.pt",
                dataset_manifest="manifest.json",
                output_dir="out",
                device="tpu",  # type: ignore[arg-type]
            )


class TestEvaluator:
    @pytest.fixture
    def evaluation_assets(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        dataset_root, manifest_path = write_evaluation_dataset(tmp_path / "dataset")
        checkpoint_dir = tmp_path / "checkpoint"
        checkpoint_path = train_and_save_checkpoint(
            dataset_root,
            manifest_path,
            checkpoint_dir,
        )
        return dataset_root, manifest_path, checkpoint_path

    def test_evaluate_checkpoint(self, evaluation_assets: tuple, tmp_path: Path) -> None:
        _, manifest_path, checkpoint_path = evaluation_assets
        config = EvaluationConfig(
            checkpoint_path=str(checkpoint_path),
            dataset_manifest=str(manifest_path),
            output_dir=str(tmp_path / "evaluation"),
            device="cpu",
            batch_size=2,
            save_predictions=True,
            save_probabilities=True,
            save_confidence=True,
        )
        result = evaluate_checkpoint(config)
        assert result.test_sample_count == 2
        assert result.evaluated_sample_count == 2
        assert result.scientific_validation_status == "NOT_VALIDATED"
        assert (tmp_path / "evaluation" / EVALUATION_JSON_NAME).exists()

    def test_model_parameters_unchanged(self, evaluation_assets: tuple, tmp_path: Path) -> None:
        _, manifest_path, checkpoint_path = evaluation_assets
        config = EvaluationConfig(
            checkpoint_path=str(checkpoint_path),
            dataset_manifest=str(manifest_path),
            output_dir=str(tmp_path / "evaluation"),
            device="cpu",
            save_predictions=False,
        )
        evaluator = Evaluator(config)
        from ssri_model.evaluation.evaluator import load_evaluation_model

        model, _ = load_evaluation_model(checkpoint_path, device=torch.device("cpu"))
        before = [parameter.detach().clone() for parameter in model.parameters()]
        evaluator.evaluate()
        after = list(model.parameters())
        for previous, current in zip(before, after, strict=True):
            assert torch.equal(previous, current)

    def test_uses_test_split_only(self, evaluation_assets: tuple, tmp_path: Path) -> None:
        dataset_root, manifest_path, checkpoint_path = evaluation_assets
        config = EvaluationConfig(
            checkpoint_path=str(checkpoint_path),
            dataset_manifest=str(manifest_path),
            output_dir=str(tmp_path / "evaluation"),
            device="cpu",
        )
        result = Evaluator(config).evaluate()
        assert result.test_sample_count == 2
        assert all(sample.sample_id.startswith("test-") for sample in result.sample_results)
