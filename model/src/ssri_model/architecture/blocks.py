"""Reusable convolution blocks for SSRI architecture."""

from __future__ import annotations

from typing import cast

import torch
import torch.nn as nn
import torch.nn.functional as F

from ssri_model.architecture.config import ActivationType, NormalizationType, SSRIModelConfig


def _num_groups(channels: int) -> int:
    """Select a valid GroupNorm group count for ``channels``."""
    for groups in (32, 16, 8, 4, 2, 1):
        if channels >= groups and channels % groups == 0:
            return groups
    return 1


def build_normalization(
    normalization: NormalizationType,
    channels: int,
) -> nn.Module:
    """Create a normalization layer for convolution blocks."""
    if normalization == "batch":
        return nn.BatchNorm2d(channels)
    if normalization == "group":
        return nn.GroupNorm(_num_groups(channels), channels)
    return nn.Identity()


def build_activation(activation: ActivationType) -> nn.Module:
    """Create an activation layer."""
    if activation == "gelu":
        return nn.GELU()
    return nn.ReLU(inplace=True)


class ConvBlock(nn.Module):
    """Two-layer convolution block with normalization and activation."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        *,
        config: SSRIModelConfig,
    ) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            build_normalization(config.normalization, out_channels),
            build_activation(config.activation),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            build_normalization(config.normalization, out_channels),
            build_activation(config.activation),
        )
        self.dropout = (
            nn.Dropout2d(p=config.dropout) if config.dropout > 0.0 else nn.Identity()
        )

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        return cast(torch.Tensor, self.dropout(self.block(tensor)))


class Downsample(nn.Module):
    """Spatial downsampling by factor two."""

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        return F.max_pool2d(tensor, kernel_size=2, stride=2)


class Upsample(nn.Module):
    """Spatial upsampling by factor two."""

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        return F.interpolate(
            tensor,
            scale_factor=2.0,
            mode="bilinear",
            align_corners=False,
        )


def align_spatial(
    tensor: torch.Tensor,
    target_size: tuple[int, int],
) -> torch.Tensor:
    """Resize ``tensor`` to ``target_size`` without cropping geospatial content."""
    if tensor.shape[-2:] == target_size:
        return tensor
    return F.interpolate(
        tensor,
        size=target_size,
        mode="bilinear",
        align_corners=False,
    )
