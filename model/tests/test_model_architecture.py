"""Tests for Stage 2.3 SSRI neural network architecture."""

from __future__ import annotations

import torch
import pytest

from ssri_model.architecture import (
    InvalidInputTensorError,
    InvalidModelConfigError,
    SSRIModel,
    SSRIModelConfig,
    count_parameters,
    create_ssri_model,
    format_parameter_summary,
)
from ssri_model.ml.constants import CHANNEL_COUNT


@pytest.fixture
def model() -> SSRIModel:
    return create_ssri_model()


class TestSSRIModelConfig:
    def test_default_configuration(self) -> None:
        config = SSRIModelConfig()
        assert config.in_channels == 13
        assert config.num_classes == 3
        assert config.base_channels == 32
        assert config.dropout == 0.0
        assert config.normalization == "group"

    def test_invalid_in_channels(self) -> None:
        with pytest.raises(InvalidModelConfigError):
            SSRIModelConfig(in_channels=0)

    def test_invalid_dropout(self) -> None:
        with pytest.raises(InvalidModelConfigError):
            SSRIModelConfig(dropout=1.0)


class TestSSRIModel:
    def test_model_creation(self, model: SSRIModel) -> None:
        assert model.in_channels == 13
        assert model.num_classes == 3

    def test_parameter_count(self, model: SSRIModel) -> None:
        summary = count_parameters(model)
        assert summary.total_parameters > 0
        assert summary.trainable_parameters > 0
        assert "total_parameters=" in format_parameter_summary(model)

    def test_forward_pass_batch(self, model: SSRIModel) -> None:
        features = torch.randn(2, 13, 64, 64, dtype=torch.float32)
        logits = model(features)
        assert logits.shape == (2, 3, 64, 64)

    def test_forward_pass_single_sample(self, model: SSRIModel) -> None:
        features = torch.randn(1, 13, 64, 64, dtype=torch.float32)
        logits = model(features)
        assert logits.shape == (1, 3, 64, 64)

    def test_non_square_input(self, model: SSRIModel) -> None:
        features = torch.randn(2, 13, 80, 96, dtype=torch.float32)
        logits = model(features)
        assert logits.shape == (2, 3, 80, 96)

    def test_odd_dimensions(self, model: SSRIModel) -> None:
        features = torch.randn(1, 13, 101, 137, dtype=torch.float32)
        logits = model(features)
        assert logits.shape == (1, 3, 101, 137)

    def test_wrong_channel_count_low(self, model: SSRIModel) -> None:
        with pytest.raises(InvalidInputTensorError):
            model(torch.randn(2, 12, 64, 64))

    def test_wrong_channel_count_high(self, model: SSRIModel) -> None:
        with pytest.raises(InvalidInputTensorError):
            model(torch.randn(2, 14, 64, 64))

    def test_non_4d_input(self, model: SSRIModel) -> None:
        with pytest.raises(InvalidInputTensorError):
            model(torch.randn(2, 13, 64))

    def test_output_dtype(self, model: SSRIModel) -> None:
        features = torch.randn(1, 13, 32, 32, dtype=torch.float32)
        logits = model(features)
        assert logits.dtype == torch.float32

    def test_logit_output_is_unbounded(self, model: SSRIModel) -> None:
        features = torch.randn(2, 13, 64, 64, dtype=torch.float32)
        logits = model(features)
        assert logits.numel() > 0

    def test_cpu_forward_pass(self, model: SSRIModel) -> None:
        features = torch.randn(1, 13, 64, 64)
        logits = model(features)
        assert logits.device.type == "cpu"

    def test_eval_deterministic(self, model: SSRIModel) -> None:
        model.eval()
        features = torch.randn(1, 13, 64, 64)
        first = model(features)
        second = model(features)
        assert torch.equal(first, second)

    def test_gradient_flow(self, model: SSRIModel) -> None:
        features = torch.randn(1, 13, 64, 64, requires_grad=False)
        logits = model(features)
        loss = logits.mean()
        loss.backward()
        assert any(
            parameter.grad is not None
            for parameter in model.parameters()
            if parameter.requires_grad
        )

    def test_model_factory(self) -> None:
        created = create_ssri_model()
        assert isinstance(created, SSRIModel)

    def test_configurable_base_channels(self) -> None:
        config = SSRIModelConfig(base_channels=16)
        created = create_ssri_model(config)
        features = torch.randn(1, 13, 64, 64)
        assert created(features).shape == (1, 3, 64, 64)

    def test_configurable_dropout(self) -> None:
        config = SSRIModelConfig(dropout=0.1)
        created = create_ssri_model(config)
        created.train()
        features = torch.randn(2, 13, 64, 64)
        assert created(features).shape == (2, 3, 64, 64)

    @pytest.mark.parametrize("normalization", ["batch", "group", "identity"])
    def test_configurable_normalization(self, normalization: str) -> None:
        config = SSRIModelConfig(normalization=normalization)  # type: ignore[arg-type]
        created = create_ssri_model(config)
        logits = created(torch.randn(1, 13, 64, 64))
        assert logits.shape == (1, 3, 64, 64)

    def test_spatial_dimensions_preserved(self, model: SSRIModel) -> None:
        for height, width in ((32, 48), (65, 73), (101, 137)):
            features = torch.randn(1, CHANNEL_COUNT, height, width)
            logits = model(features)
            assert logits.shape == (1, 3, height, width)


class TestStage22Integration:
    def test_features_batch_through_model(self) -> None:
        batch = {
            "features": torch.randn(2, 13, 64, 64, dtype=torch.float32),
            "label": torch.zeros(2, 64, 64, dtype=torch.int64),
            "mask": torch.ones(2, 64, 64, dtype=torch.bool),
            "sample_id": ["sample-a", "sample-b"],
        }
        model = create_ssri_model()
        logits = model(batch["features"])

        assert batch["features"].dtype == torch.float32
        assert logits.shape == (2, 3, 64, 64)
