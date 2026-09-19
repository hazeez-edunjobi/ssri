"""Encoder stack for SSRI U-Net architecture."""

from __future__ import annotations

import torch
import torch.nn as nn

from ssri_model.architecture.blocks import ConvBlock, Downsample
from ssri_model.architecture.config import SSRIModelConfig


class EncoderStage(nn.Module):
    """Convolution followed by downsampling."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        *,
        config: SSRIModelConfig,
    ) -> None:
        super().__init__()
        self.conv = ConvBlock(in_channels, out_channels, config=config)
        self.downsample = Downsample()

    def forward(self, tensor: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.conv(tensor)
        return features, self.downsample(features)


class SSRIEncoder(nn.Module):
    """Progressive spatial encoder with skip-connection features."""

    def __init__(self, config: SSRIModelConfig) -> None:
        super().__init__()
        self.config = config
        stage_channels = config.stage_channels()

        self.stem = ConvBlock(config.in_channels, config.base_channels, config=config)

        encoder_blocks: list[EncoderStage] = []
        in_channels = config.base_channels
        for out_channels in stage_channels:
            encoder_blocks.append(
                EncoderStage(in_channels, out_channels, config=config)
            )
            in_channels = out_channels

        self.blocks = nn.ModuleList(encoder_blocks)
        self.bottleneck = ConvBlock(
            stage_channels[-1],
            config.bottleneck_channels,
            config=config,
        )

    def forward(self, tensor: torch.Tensor) -> tuple[torch.Tensor, list[torch.Tensor]]:
        current = self.stem(tensor)
        skips: list[torch.Tensor] = [current]

        for encoder_stage in self.blocks:
            _, current = encoder_stage(current)
            skips.append(current)

        bottleneck = self.bottleneck(current)
        decoder_skips = skips[: self.config.num_encoder_stages]
        return bottleneck, decoder_skips
