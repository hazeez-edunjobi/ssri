"""Output heads for SSRI hazard segmentation."""

from __future__ import annotations

from typing import cast

import torch
import torch.nn as nn


class SegmentationHead(nn.Module):
    """1×1 convolution producing per-pixel hazard logits."""

    def __init__(self, in_channels: int, num_classes: int) -> None:
        super().__init__()
        self.classifier = nn.Conv2d(in_channels, num_classes, kernel_size=1)

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        return cast(torch.Tensor, self.classifier(tensor))
