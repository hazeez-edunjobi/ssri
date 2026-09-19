"""Stage 2.5 checkpoint tests."""

from __future__ import annotations

from pathlib import Path

import torch
import pytest

from ssri_model.architecture import SSRIModelConfig, create_ssri_model
from ssri_model.training import (
    BEST_CHECKPOINT_NAME,
    LATEST_CHECKPOINT_NAME,
    Trainer,
    TrainingConfig,
    TrainingHistory,
    create_optimizer,
    create_scheduler,
    load_checkpoint,
)
from ssri_model.training.checkpoint import save_checkpoint
from ssri_model.training.exceptions import CheckpointCompatibilityError, CheckpointError
from tests.training_helpers import SyntheticSegmentationDataset, make_dataloader


@pytest.fixture
def trained_experiment(tmp_path: Path) -> Path:
    train_dataset = SyntheticSegmentationDataset(num_samples=4, height=16, width=16, seed=7)
    val_dataset = SyntheticSegmentationDataset(num_samples=4, height=16, width=16, seed=8)
    model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
    config = TrainingConfig(
        epochs=2,
        batch_size=2,
        device="cpu",
        checkpoint_dir=str(tmp_path / "experiment"),
        early_stopping_patience=10,
    )
    trainer = Trainer(
        model=model,
        config=config,
        train_loader=make_dataloader(train_dataset, batch_size=2),
        validation_loader=make_dataloader(val_dataset, batch_size=2),
    )
    trainer.fit()
    return tmp_path / "experiment"


class TestCheckpointsStage25:
    def test_latest_and_best_created(self, trained_experiment: Path) -> None:
        assert (trained_experiment / LATEST_CHECKPOINT_NAME).exists()
        assert (trained_experiment / BEST_CHECKPOINT_NAME).exists()

    def test_save_load_round_trip(self, trained_experiment: Path) -> None:
        model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
        config = TrainingConfig(device="cpu")
        optimizer = create_optimizer(model, config)
        scheduler = create_scheduler(optimizer, config)
        payload = load_checkpoint(
            trained_experiment / BEST_CHECKPOINT_NAME,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
        )
        assert "training_history" in payload
        assert "dataset_manifest" in payload or payload.get("dataset_manifest") is None

    def test_resume_training(self, trained_experiment: Path) -> None:
        train_dataset = SyntheticSegmentationDataset(num_samples=4, height=16, width=16, seed=9)
        val_dataset = SyntheticSegmentationDataset(num_samples=4, height=16, width=16, seed=10)
        model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
        config = TrainingConfig(
            epochs=3,
            device="cpu",
            checkpoint_dir=str(trained_experiment),
        )
        trainer = Trainer(
            model=model,
            config=config,
            train_loader=make_dataloader(train_dataset, batch_size=2),
            validation_loader=make_dataloader(val_dataset, batch_size=2),
        )
        trainer.resume_from_checkpoint(trained_experiment / LATEST_CHECKPOINT_NAME)
        result = trainer.fit()
        assert result.final_epoch >= 2

    def test_incompatible_checkpoint_rejected(self, trained_experiment: Path) -> None:
        incompatible = create_ssri_model(
            SSRIModelConfig(base_channels=8, num_encoder_stages=2, num_classes=4)
        )
        with pytest.raises(CheckpointCompatibilityError):
            load_checkpoint(trained_experiment / BEST_CHECKPOINT_NAME, model=incompatible)

    def test_missing_checkpoint_raises(self, tmp_path: Path) -> None:
        model = create_ssri_model()
        with pytest.raises(CheckpointError):
            load_checkpoint(tmp_path / "missing.pt", model=model)

    def test_checkpoint_contains_full_state(self, tmp_path: Path) -> None:
        model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
        config = TrainingConfig(device="cpu")
        optimizer = create_optimizer(model, config)
        scheduler = create_scheduler(optimizer, config)
        history = TrainingHistory()
        path = tmp_path / "manual.pt"
        save_checkpoint(
            path=path,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
            epoch=1,
            best_metric=0.4,
            best_metric_name="macro_f1",
            best_validation_loss=0.5,
            training_config=config,
            model_config=model.config,
            history=history,
            seed=42,
            dataset_manifest={"dataset_name": "demo", "version": "0.1.0"},
        )
        payload = torch.load(path, map_location="cpu")
        for key in (
            "model_state_dict",
            "optimizer_state_dict",
            "scheduler_state_dict",
            "training_config",
            "model_config",
            "training_history",
            "seed",
            "best_metric",
            "dataset_manifest",
        ):
            assert key in payload
