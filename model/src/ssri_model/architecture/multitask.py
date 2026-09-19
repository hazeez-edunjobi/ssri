"""Multi-task PRD hazard heads (landslide / subsidence / liquefaction).

Separate from legacy single ``SegmentationHead`` (subsidence/landslide/sinkhole)
so existing checkpoints remain loadable.
"""

from __future__ import annotations

from typing import cast

import torch
import torch.nn as nn
import torch.nn.functional as F

from ssri_model.architecture.config import SSRIModelConfig
from ssri_model.architecture.decoder import SSRIDecoder
from ssri_model.architecture.encoder import SSRIEncoder
from ssri_model.architecture.exceptions import InvalidInputTensorError
from ssri_model.dann import DomainDiscriminator, GradientReversalLayer, global_average_pool
from ssri_model.ingestion.schema import PRD_HAZARD_ORDER, PrdHazard
from ssri_model.ml.constants import CHANNEL_COUNT


class MultiTaskHazardHeads(nn.Module):
    """One 1×1 head per PRD hazard → per-pixel logits."""

    def __init__(self, in_channels: int) -> None:
        super().__init__()
        self.task_names = tuple(h.value for h in PRD_HAZARD_ORDER)
        self.heads = nn.ModuleDict(
            {name: nn.Conv2d(in_channels, 1, kernel_size=1) for name in self.task_names}
        )

    def forward(self, decoded: torch.Tensor) -> dict[str, torch.Tensor]:
        return {
            name: cast(torch.Tensor, head(decoded).squeeze(1))
            for name, head in self.heads.items()
        }


class SSRIMultiTaskModel(nn.Module):
    """Shared U-Net backbone + PRD multi-task heads (+ optional DANN discriminator)."""

    def __init__(
        self,
        config: SSRIModelConfig | None = None,
        *,
        dann: bool = False,
        grl_lambda: float = 1.0,
    ) -> None:
        super().__init__()
        self.config = config or SSRIModelConfig()
        self.dann_enabled = bool(dann)
        self.encoder = SSRIEncoder(self.config)
        self.decoder = SSRIDecoder(self.config)
        self.heads = MultiTaskHazardHeads(self.config.base_channels)
        self.grl = GradientReversalLayer(lambda_=grl_lambda)
        self.domain_discriminator = DomainDiscriminator(
            in_features=self.config.bottleneck_channels,
            hidden=128,
        )

    def encode_embedding(self, features: torch.Tensor) -> torch.Tensor:
        """Return bottleneck embedding ``(B, C)`` after GAP (for domain similarity)."""
        self._validate_input(features)
        bottleneck, _skips = self.encoder(features)
        return global_average_pool(bottleneck)

    def forward(
        self,
        features: torch.Tensor,
        *,
        return_domain_logit: bool = False,
    ) -> dict[str, torch.Tensor] | tuple[dict[str, torch.Tensor], torch.Tensor]:
        self._validate_input(features)
        bottleneck, skips = self.encoder(features)
        decoded = self.decoder(bottleneck, skips)
        task_logits = self.heads(decoded)
        if not return_domain_logit:
            return task_logits
        reversed_emb = self.grl(global_average_pool(bottleneck))
        domain_logit = self.domain_discriminator(reversed_emb)
        return task_logits, domain_logit

    def _validate_input(self, features: torch.Tensor) -> None:
        if features.ndim != 4:
            raise InvalidInputTensorError(
                f"Expected 4D input tensor (B, C, H, W), received ndim={features.ndim}"
            )
        if features.shape[1] != CHANNEL_COUNT:
            raise InvalidInputTensorError(
                f"Expected {CHANNEL_COUNT} input channels, received {features.shape[1]}"
            )


def masked_multitask_bce_with_logits(
    logits: dict[str, torch.Tensor],
    targets: dict[str, torch.Tensor],
    masks: dict[str, torch.Tensor],
) -> torch.Tensor:
    """Mean BCE over tasks/pixels where mask==1; skips fully-missing tasks.

    ``targets`` / ``masks`` are ``(B, H, W)``. Mask 0 = missing label (not negative).
    """
    losses: list[torch.Tensor] = []
    for name in (h.value for h in PrdHazard):
        if name not in logits:
            continue
        mask = masks[name].bool()
        if not bool(mask.any()):
            continue
        pred = logits[name][mask]
        tgt = targets[name][mask].float()
        losses.append(F.binary_cross_entropy_with_logits(pred, tgt))
    if not losses:
        # Retain graph connectivity when a batch has no labelled pixels.
        any_logit = next(iter(logits.values()))
        return any_logit.sum() * 0.0
    return torch.stack(losses).mean()
