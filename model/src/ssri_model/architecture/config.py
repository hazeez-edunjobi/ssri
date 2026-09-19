"""Configuration for the SSRI segmentation architecture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ssri_model.architecture.exceptions import InvalidModelConfigError
from ssri_model.ml.constants import CHANNEL_COUNT

NormalizationType = Literal["batch", "group", "identity"]
ActivationType = Literal["relu", "gelu"]


@dataclass(frozen=True)
class SSRIModelConfig:
    """Typed configuration for ``SSRIModel``."""

    in_channels: int = CHANNEL_COUNT
    num_classes: int = 3
    base_channels: int = 32
    num_encoder_stages: int = 3
    dropout: float = 0.0
    normalization: NormalizationType = "group"
    activation: ActivationType = "relu"

    def __post_init__(self) -> None:
        if self.in_channels <= 0:
            raise InvalidModelConfigError("in_channels must be greater than zero")
        if self.num_classes <= 0:
            raise InvalidModelConfigError("num_classes must be greater than zero")
        if self.base_channels <= 0:
            raise InvalidModelConfigError("base_channels must be greater than zero")
        if self.num_encoder_stages <= 0:
            raise InvalidModelConfigError("num_encoder_stages must be greater than zero")
        if not 0.0 <= self.dropout < 1.0:
            raise InvalidModelConfigError("dropout must satisfy 0 <= dropout < 1")
        if self.normalization not in ("batch", "group", "identity"):
            raise InvalidModelConfigError(
                f"Unsupported normalization: {self.normalization}"
            )
        if self.activation not in ("relu", "gelu"):
            raise InvalidModelConfigError(f"Unsupported activation: {self.activation}")

    def stage_channels(self) -> tuple[int, ...]:
        """Return encoder output channel widths after each stage."""
        if self.num_encoder_stages == 1:
            return (self.base_channels * 2,)

        channels = [
            self.base_channels * (2 ** (stage + 1))
            for stage in range(self.num_encoder_stages - 1)
        ]
        channels.append(self.base_channels * (2 ** (self.num_encoder_stages - 1)))
        return tuple(channels)

    @property
    def bottleneck_channels(self) -> int:
        """Return bottleneck feature width."""
        return int(self.base_channels * (2**self.num_encoder_stages))
