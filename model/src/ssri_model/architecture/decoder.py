"""Decoder stack with skip connections for SSRI U-Net architecture."""

from __future__ import annotations

from typing import cast

import torch
import torch.nn as nn

from ssri_model.architecture.blocks import ConvBlock, Upsample, align_spatial
from ssri_model.architecture.config import SSRIModelConfig


class DecoderStage(nn.Module):
    """One decoder stage with upsampling, skip fusion, and convolution."""

    def __init__(
        self,
        in_channels: int,
        skip_channels: int,
        out_channels: int,
        *,
        config: SSRIModelConfig,
    ) -> None:
        super().__init__()
        self.upsample = Upsample()
        self.conv = ConvBlock(
            in_channels + skip_channels,
            out_channels,
            config=config,
        )

    def forward(
        self,
        tensor: torch.Tensor,
        skip: torch.Tensor,
    ) -> torch.Tensor:
        upsampled = self.upsample(tensor)
        upsampled = align_spatial(
            upsampled,
            (int(skip.shape[-2]), int(skip.shape[-1])),
        )
        merged = torch.cat([upsampled, skip], dim=1)
        return cast(torch.Tensor, self.conv(merged))


class SSRIDecoder(nn.Module):
    """Upsampling decoder that restores the input spatial resolution."""

    def __init__(self, config: SSRIModelConfig) -> None:
        super().__init__()
        self.config = config
        stage_channels = config.stage_channels()
        skip_channels = list(reversed([config.base_channels, *stage_channels[:-1]]))
        decoder_outputs = skip_channels

        decoder_stages: list[DecoderStage] = []
        in_channels = config.bottleneck_channels
        for index, out_channels in enumerate(decoder_outputs):
            decoder_stages.append(
                DecoderStage(
                    in_channels,
                    skip_channels[index],
                    out_channels,
                    config=config,
                )
            )
            in_channels = out_channels

        self.stages = nn.ModuleList(decoder_stages)

    def forward(
        self,
        tensor: torch.Tensor,
        skips: list[torch.Tensor],
    ) -> torch.Tensor:
        current = tensor
        reversed_skips = list(reversed(skips))
        for stage, skip in zip(self.stages, reversed_skips, strict=True):
            current = stage(current, skip)

        return current
