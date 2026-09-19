"""Stage 2.5 training configuration and orchestration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ssri_model.architecture import SSRIModelConfig, create_ssri_model
from ssri_model.training import (
    Trainer,
    TrainingConfig,
    create_experiment_directory,
    set_seed,
)
from ssri_model.training.exceptions import (
    ExperimentExistsError,
    InvalidTrainingConfigError,
    SplitLeakageError,
)
from ssri_model.training.safety import check_split_leakage
from tests.training_helpers import SyntheticSegmentationDataset, make_dataloader


class TestTrainingConfig:
    def test_valid_config(self) -> None:
        config = TrainingConfig(
            output_dir="./outputs",
            dataset_manifest="manifest.json",
            batch_size=4,
            epochs=10,
        )
        assert config.batch_size == 4

    def test_invalid_learning_rate(self) -> None:
        with pytest.raises(InvalidTrainingConfigError):
            TrainingConfig(learning_rate=0.0)

    def test_invalid_batch_size(self) -> None:
        with pytest.raises(InvalidTrainingConfigError):
            TrainingConfig(batch_size=0)

    def test_invalid_optimizer(self) -> None:
        with pytest.raises(InvalidTrainingConfigError):
            TrainingConfig(optimizer="rmsprop")  # type: ignore[arg-type]

    def test_invalid_scheduler(self) -> None:
        with pytest.raises(InvalidTrainingConfigError):
            TrainingConfig(scheduler="step")  # type: ignore[arg-type]

    def test_early_stopping_disabled_by_default(self) -> None:
        config = TrainingConfig()
        assert config.early_stopping_enabled is False


class TestExperimentDirectory:
    def test_create_experiment_directory(self, tmp_path: Path) -> None:
        experiment_dir = create_experiment_directory(tmp_path / "outputs", experiment_id="run-a")
        assert experiment_dir.exists()
        assert (experiment_dir / "logs").exists()

    def test_existing_experiment_rejected(self, tmp_path: Path) -> None:
        root = tmp_path / "outputs"
        create_experiment_directory(root, experiment_id="run-a")
        with pytest.raises(ExperimentExistsError):
            create_experiment_directory(root, experiment_id="run-a")


class TestSplitLeakage:
    def test_overlapping_split_ids_rejected(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            """
            {
              "dataset_name": "demo",
              "version": "0.1.0",
              "created_at": "2026-08-08T00:00:00+00:00",
              "channels": ["elevation"],
              "label_classes": ["subsidence"],
              "resolution": 30.0,
              "crs": "EPSG:32613",
              "normalization": {},
              "train_count": 1,
              "validation_count": 1,
              "test_count": 0,
              "splits": {
                "train": ["sample-a"],
                "validation": ["sample-a"],
                "test": []
              }
            }
            """.strip(),
            encoding="utf-8",
        )
        with pytest.raises(SplitLeakageError):
            check_split_leakage(manifest)


class TestTrainerStage25:
    def test_one_epoch_cpu_training(self, tmp_path: Path) -> None:
        train_dataset = SyntheticSegmentationDataset(num_samples=4, height=32, width=32, seed=1)
        val_dataset = SyntheticSegmentationDataset(num_samples=4, height=32, width=32, seed=2)
        model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
        config = TrainingConfig(
            epochs=1,
            batch_size=2,
            device="cpu",
            checkpoint_dir=str(tmp_path / "experiment"),
        )
        trainer = Trainer(
            model=model,
            config=config,
            train_loader=make_dataloader(train_dataset, batch_size=2),
            validation_loader=make_dataloader(val_dataset, batch_size=2),
        )
        result = trainer.fit()
        assert result.final_epoch == 1
        assert len(result.history.epochs) == 1

    def test_constructor_fit_api(self, tmp_path: Path) -> None:
        train_dataset = SyntheticSegmentationDataset(num_samples=4, height=16, width=16, seed=3)
        val_dataset = SyntheticSegmentationDataset(num_samples=4, height=16, width=16, seed=4)
        model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
        config = TrainingConfig(
            epochs=1,
            device="cpu",
            checkpoint_dir=str(tmp_path / "experiment"),
        )
        trainer = Trainer(
            model=model,
            train_loader=make_dataloader(train_dataset),
            validation_loader=make_dataloader(val_dataset),
            config=config,
        )
        result = trainer.fit()
        assert result.experiment_dir


class TestReproducibility:
    def test_same_seed_same_initial_loss(self) -> None:
        import torch

        from ssri_model.training import masked_cross_entropy

        set_seed(123)
        logits = torch.randn(1, 3, 4, 4)
        targets = torch.zeros(1, 4, 4, dtype=torch.long)
        mask = torch.ones(1, 4, 4, dtype=torch.bool)
        loss_a = float(masked_cross_entropy(logits, targets, mask).item())
        set_seed(123)
        logits_b = torch.randn(1, 3, 4, 4)
        loss_b = float(masked_cross_entropy(logits_b, targets, mask).item())
        assert loss_a == loss_b
