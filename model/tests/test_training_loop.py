"""Tests for SSRI training loop."""

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
)
from tests.training_helpers import SyntheticSegmentationDataset, make_dataloader


@pytest.fixture
def tiny_training_setup(tmp_path: Path) -> tuple:
    train_dataset = SyntheticSegmentationDataset(num_samples=4, height=32, width=32, seed=1)
    val_dataset = SyntheticSegmentationDataset(num_samples=4, height=32, width=32, seed=2)
    train_loader = make_dataloader(train_dataset, batch_size=2)
    val_loader = make_dataloader(val_dataset, batch_size=2)

    model = create_ssri_model(
        SSRIModelConfig(base_channels=8, num_encoder_stages=2)
    )
    config = TrainingConfig(
        epochs=3,
        batch_size=2,
        learning_rate=1e-2,
        device="cpu",
        seed=42,
        checkpoint_dir=str(tmp_path / "checkpoints"),
        early_stopping_patience=10,
        scheduler="cosine",
    )
    trainer = Trainer(model=model, config=config)
    return trainer, train_loader, val_loader, model, tmp_path


class TestTrainingLoop:
    def test_fit_runs_on_cpu(self, tiny_training_setup: tuple) -> None:
        trainer, train_loader, val_loader, _, _ = tiny_training_setup
        result = trainer.fit(train_loader, val_loader)
        assert result.final_epoch >= 1
        assert result.best_validation_loss < float("inf")
        assert len(result.history.epochs) == result.final_epoch

    def test_loss_is_finite(self, tiny_training_setup: tuple) -> None:
        trainer, train_loader, val_loader, _, _ = tiny_training_setup
        result = trainer.fit(train_loader, val_loader)
        for record in result.history.epochs:
            assert record.train_loss == record.train_loss
            assert record.validation_loss == record.validation_loss

    def test_model_parameters_change(self, tiny_training_setup: tuple) -> None:
        trainer, train_loader, val_loader, model, _ = tiny_training_setup
        before = [parameter.detach().clone() for parameter in model.parameters()]
        trainer.fit(train_loader, val_loader)
        after = list(model.parameters())
        assert any(
            not torch.allclose(previous, current)
            for previous, current in zip(before, after, strict=True)
        )

    def test_history_recorded(self, tiny_training_setup: tuple) -> None:
        trainer, train_loader, val_loader, _, _ = tiny_training_setup
        result = trainer.fit(train_loader, val_loader)
        assert result.history.epochs[0].epoch == 1
        assert result.history.epochs[-1].learning_rate >= 0.0

    def test_checkpoints_created(self, tiny_training_setup: tuple) -> None:
        trainer, train_loader, val_loader, _, tmp_path = tiny_training_setup
        result = trainer.fit(train_loader, val_loader)
        checkpoint_dir = tmp_path / "checkpoints"
        assert (checkpoint_dir / LATEST_CHECKPOINT_NAME).exists()
        assert (checkpoint_dir / BEST_CHECKPOINT_NAME).exists()
        assert Path(result.checkpoint_paths["best"]).exists()

    def test_eval_mode_is_deterministic(self, tiny_training_setup: tuple) -> None:
        trainer, train_loader, val_loader, model, _ = tiny_training_setup
        trainer.fit(train_loader, val_loader)
        batch = next(iter(val_loader))
        model.eval()
        with torch.no_grad():
            first = model(batch["features"])
            second = model(batch["features"])
        assert torch.equal(first, second)

    def test_gradient_flow(self, tiny_training_setup: tuple) -> None:
        _, train_loader, _, model, _ = tiny_training_setup
        batch = next(iter(train_loader))
        model.train()
        model.zero_grad()
        logits = model(batch["features"])
        loss = logits.mean()
        loss.backward()
        assert any(
            parameter.grad is not None for parameter in model.parameters() if parameter.requires_grad
        )

    def test_early_stopping(self, tmp_path: Path) -> None:
        train_dataset = SyntheticSegmentationDataset(num_samples=4, height=16, width=16, seed=3)
        val_dataset = SyntheticSegmentationDataset(num_samples=4, height=16, width=16, seed=4)
        train_loader = make_dataloader(train_dataset, batch_size=2)
        val_loader = make_dataloader(val_dataset, batch_size=2)
        model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
        config = TrainingConfig(
            epochs=20,
            batch_size=2,
            device="cpu",
            checkpoint_dir=str(tmp_path / "checkpoints"),
            early_stopping_patience=1,
            min_delta=1e9,
        )
        trainer = Trainer(model=model, config=config)
        result = trainer.fit(train_loader, val_loader)
        assert result.stopped_early is True
        assert result.final_epoch < config.epochs
