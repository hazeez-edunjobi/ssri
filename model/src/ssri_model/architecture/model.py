"""SSRI U-Net segmentation model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import torch
import torch.nn as nn

from ssri_model.architecture.config import SSRIModelConfig
from ssri_model.architecture.decoder import SSRIDecoder
from ssri_model.architecture.encoder import SSRIEncoder
from ssri_model.architecture.exceptions import InvalidInputTensorError
from ssri_model.architecture.heads import SegmentationHead
from ssri_model.ml.constants import CHANNEL_COUNT


@dataclass(frozen=True)
class ParameterSummary:
    """Summary of model parameter counts."""

    total_parameters: int
    trainable_parameters: int


class SSRIModel(nn.Module):
    """Lightweight U-Net for dense geohazard susceptibility prediction."""

    def __init__(self, config: SSRIModelConfig | None = None) -> None:
        super().__init__()
        self.config = config or SSRIModelConfig()
        self.in_channels = self.config.in_channels
        self.num_classes = self.config.num_classes

        self.encoder = SSRIEncoder(self.config)
        self.decoder = SSRIDecoder(self.config)
        self.head = SegmentationHead(
            self.config.base_channels,
            self.config.num_classes,
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """Return raw hazard logits for each input pixel."""
        self._validate_input(features)
        input_size = features.shape[-2:]

        bottleneck, skips = self.encoder(features)
        decoded = self.decoder(bottleneck, skips)
        logits = self.head(decoded)

        if logits.shape[-2:] != input_size:
            raise InvalidInputTensorError(
                "Decoder failed to restore spatial dimensions; "
                f"expected {input_size}, received {tuple(logits.shape[-2:])}"
            )
        return cast(torch.Tensor, logits)

    def _validate_input(self, features: torch.Tensor) -> None:
        if features.ndim != 4:
            raise InvalidInputTensorError(
                f"Expected 4D input tensor (B, C, H, W), received ndim={features.ndim}"
            )
        if features.shape[1] != CHANNEL_COUNT:
            raise InvalidInputTensorError(
                f"Expected {CHANNEL_COUNT} input channels, received {features.shape[1]}"
            )


def create_ssri_model(config: SSRIModelConfig | None = None) -> SSRIModel:
    """Create an SSRI segmentation model with canonical defaults."""
    return SSRIModel(config=config)


def count_parameters(model: nn.Module) -> ParameterSummary:
    """Count total and trainable parameters in a model."""
    total = sum(parameter.numel() for parameter in model.parameters())
    trainable = sum(
        parameter.numel()
        for parameter in model.parameters()
        if parameter.requires_grad
    )
    return ParameterSummary(
        total_parameters=total,
        trainable_parameters=trainable,
    )


def format_parameter_summary(model: nn.Module) -> str:
    """Return a readable parameter count summary."""
    summary = count_parameters(model)
    return (
        f"total_parameters={summary.total_parameters:,} "
        f"trainable_parameters={summary.trainable_parameters:,}"
    )
