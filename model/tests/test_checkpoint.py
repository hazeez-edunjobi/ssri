"""Tests for SSRI training checkpoints."""

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
from ssri_model.training.exceptions import CheckpointCompatibilityError, CheckpointError
from ssri_model.training.checkpoint import save_checkpoint
from tests.training_helpers import SyntheticSegmentationDataset, make_dataloader


@pytest.fixture
def trained_checkpoint(tmp_path: Path) -> Path:
    train_dataset = SyntheticSegmentationDataset(num_samples=4, height=16, width=16, seed=5)
    val_dataset = SyntheticSegmentationDataset(num_samples=4, height=16, width=16, seed=6)
    train_loader = make_dataloader(train_dataset, batch_size=2)
    val_loader = make_dataloader(val_dataset, batch_size=2)
    model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
    config = TrainingConfig(
        epochs=2,
        batch_size=2,
        device="cpu",
        checkpoint_dir=str(tmp_path / "checkpoints"),
        early_stopping_patience=5,
    )
    trainer = Trainer(model=model, config=config)
    trainer.fit(train_loader, val_loader)
    return tmp_path / "checkpoints" / BEST_CHECKPOINT_NAME


class TestCheckpoint:
    def test_latest_and_best_exist(self, trained_checkpoint: Path) -> None:
        checkpoint_dir = trained_checkpoint.parent
        assert (checkpoint_dir / LATEST_CHECKPOINT_NAME).exists()
        assert (checkpoint_dir / BEST_CHECKPOINT_NAME).exists()

    def test_checkpoint_can_be_loaded(self, trained_checkpoint: Path) -> None:
        model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
        config = TrainingConfig(device="cpu")
        optimizer = create_optimizer(model, config)
        scheduler = create_scheduler(optimizer, config)
        payload = load_checkpoint(
            trained_checkpoint,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
        )
        assert "epoch" in payload
        assert "training_history" in payload

    def test_model_parameters_restore(self, trained_checkpoint: Path) -> None:
        source_model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
        load_checkpoint(trained_checkpoint, model=source_model)
        source_params = [parameter.detach().clone() for parameter in source_model.parameters()]

        target_model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
        load_checkpoint(trained_checkpoint, model=target_model)
        target_params = list(target_model.parameters())

        for source, target in zip(source_params, target_params, strict=True):
            assert torch.allclose(source, target)

    def test_optimizer_and_scheduler_restore(self, trained_checkpoint: Path) -> None:
        model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
        config = TrainingConfig(device="cpu", scheduler="cosine", epochs=2)
        optimizer = create_optimizer(model, config)
        scheduler = create_scheduler(optimizer, config)
        payload = load_checkpoint(
            trained_checkpoint,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
        )
        assert payload["optimizer_state_dict"] is not None
        assert payload["scheduler_state_dict"] is not None

    def test_epoch_and_history_restore(self, trained_checkpoint: Path) -> None:
        payload = torch.load(trained_checkpoint, map_location="cpu")
        history = TrainingHistory.from_dict(payload["training_history"])
        assert len(history.epochs) >= 1
        assert payload["epoch"] >= 1

    def test_incompatible_architecture_rejected(self, trained_checkpoint: Path) -> None:
        incompatible_model = create_ssri_model(
            SSRIModelConfig(base_channels=8, num_encoder_stages=2, num_classes=4)
        )
        with pytest.raises(CheckpointCompatibilityError):
            load_checkpoint(trained_checkpoint, model=incompatible_model)

    def test_missing_checkpoint_raises(self, tmp_path: Path) -> None:
        model = create_ssri_model()
        with pytest.raises(CheckpointError):
            load_checkpoint(tmp_path / "missing.pt", model=model)

    def test_manual_save_contains_required_fields(self, tmp_path: Path) -> None:
        model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
        config = TrainingConfig(device="cpu", checkpoint_dir=str(tmp_path))
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
            best_metric=0.5,
            best_metric_name="macro_f1",
            best_validation_loss=0.5,
            training_config=config,
            model_config=model.config,
            history=history,
            seed=42,
        )
        payload = torch.load(path, map_location="cpu")
        for key in (
            "model_state_dict",
            "optimizer_state_dict",
            "scheduler_state_dict",
            "epoch",
            "best_validation_loss",
            "training_config",
            "model_config",
            "training_history",
            "seed",
        ):
            assert key in payload
