"""Uncertainty quantification for SSRI predictions.

Software metrics here are calibration parameters until scientifically validated.
Defaults are explicit and must not be presented as geological truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

import numpy as np
import torch
import torch.nn as nn

from ssri_model.ml.constants import CHANNEL_NAMES


class ConfidenceTier(str, Enum):
    HIGH = "High"
    MODERATE = "Moderate"
    LOW = "Low"
    EXTRAPOLATION_WARNING = "Extrapolation Warning"


@dataclass(frozen=True)
class UncertaintyConfig:
    """Configurable uncertainty estimation parameters (calibration knobs)."""

    mc_samples: int = 100
    dropout_p: float = 0.1
    interval_80: float = 0.80
    interval_95: float = 0.95
    high_similarity_min: float = 0.75
    moderate_similarity_min: float = 0.55
    low_similarity_min: float = 0.35
    high_interval_width_max: float = 0.20
    moderate_interval_width_max: float = 0.40
    seed: int | None = 42

    def __post_init__(self) -> None:
        if self.mc_samples < 2:
            raise ValueError("mc_samples must be at least 2")
        if not 0.0 < self.dropout_p < 1.0:
            raise ValueError("dropout_p must be in (0, 1)")
        if not 0.0 < self.interval_80 < 1.0:
            raise ValueError("interval_80 must be in (0, 1)")
        if not 0.0 < self.interval_95 < 1.0:
            raise ValueError("interval_95 must be in (0, 1)")


@dataclass(frozen=True)
class CredibleInterval:
    lower: float
    upper: float
    level: float

    def width(self) -> float:
        return float(self.upper - self.lower)

    def to_list(self) -> list[float]:
        return [self.lower, self.upper]


@dataclass(frozen=True)
class HazardUncertainty:
    hazard_type: str
    point_estimate: float
    credible_interval_80: CredibleInterval
    credible_interval_95: CredibleInterval
    domain_similarity_score: float | None
    confidence_tier: ConfidenceTier
    primary_drivers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "hazard_type": self.hazard_type,
            "point_estimate": self.point_estimate,
            "susceptibility_score": self.point_estimate,
            "credible_interval_80": self.credible_interval_80.to_list(),
            "credible_interval_95": self.credible_interval_95.to_list(),
            "domain_similarity_score": self.domain_similarity_score,
            "confidence_tier": self.confidence_tier.value,
            "primary_drivers": list(self.primary_drivers),
        }


@dataclass(frozen=True)
class AssessmentResult:
    """Stable uncertainty-aware assessment payload."""

    assessment_id: str
    hazard_profiles: tuple[HazardUncertainty, ...]
    explanation: str = ""
    model_version: str = "unknown"
    spatial_output_url: str | None = None
    notes: tuple[str, ...] = (
        "Confidence tiers use configurable calibration parameters, "
        "not scientifically validated thresholds.",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "hazard_profiles": [profile.to_dict() for profile in self.hazard_profiles],
            "explanation": self.explanation,
            "model_version": self.model_version,
            "spatial_output_url": self.spatial_output_url,
            "notes": list(self.notes),
        }


@dataclass
class DomainCentroid:
    """Cached source-domain embedding centroid for similarity scoring."""

    vector: np.ndarray
    count: int = 0

    def update(self, embedding: np.ndarray) -> None:
        if self.count == 0:
            self.vector = embedding.astype(np.float64)
            self.count = 1
            return
        self.count += 1
        self.vector = self.vector + (embedding.astype(np.float64) - self.vector) / self.count


def enable_mc_dropout(module: nn.Module, *, dropout_p: float | None = None) -> None:
    """Force dropout layers into train mode for MC sampling."""
    for submodule in module.modules():
        if isinstance(submodule, (nn.Dropout, nn.Dropout2d, nn.Dropout3d)):
            submodule.train()
            if dropout_p is not None and hasattr(submodule, "p"):
                submodule.p = float(dropout_p)


def empirical_credible_interval(
    samples: np.ndarray,
    *,
    level: float,
) -> CredibleInterval:
    """Compute an empirical equal-tailed credible interval (no normality assumption)."""
    if samples.size == 0:
        raise ValueError("samples must be non-empty")
    alpha = (1.0 - level) / 2.0
    lower = float(np.quantile(samples, alpha))
    upper = float(np.quantile(samples, 1.0 - alpha))
    return CredibleInterval(lower=lower, upper=upper, level=level)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def normalize_similarity(raw_cosine: float) -> float:
    """Map cosine similarity from [-1, 1] to [0, 1]."""
    return float(np.clip((raw_cosine + 1.0) / 2.0, 0.0, 1.0))


def assign_confidence_tier(
    *,
    interval_width: float,
    domain_similarity: float,
    config: UncertaintyConfig,
) -> ConfidenceTier:
    if domain_similarity < config.low_similarity_min:
        return ConfidenceTier.EXTRAPOLATION_WARNING
    if (
        domain_similarity >= config.high_similarity_min
        and interval_width <= config.high_interval_width_max
    ):
        return ConfidenceTier.HIGH
    if (
        domain_similarity >= config.moderate_similarity_min
        and interval_width <= config.moderate_interval_width_max
    ):
        return ConfidenceTier.MODERATE
    return ConfidenceTier.LOW


def gradient_feature_attribution(
    model: nn.Module,
    features: torch.Tensor,
    *,
    class_index: int,
) -> list[tuple[str, float]]:
    """Gradient-based channel importance (mean |grad| per input channel)."""
    model.eval()
    features = features.detach().clone().requires_grad_(True)
    logits = model(features)
    # Mean spatial probability for the selected class.
    probs = torch.sigmoid(logits[:, class_index : class_index + 1])
    score = probs.mean()
    score.backward()
    assert features.grad is not None
    channel_importance = features.grad.abs().mean(dim=(0, 2, 3)).detach().cpu().numpy()
    ranked = sorted(
        (
            (CHANNEL_NAMES[i] if i < len(CHANNEL_NAMES) else f"channel_{i}", float(v))
            for i, v in enumerate(channel_importance)
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    return ranked


@torch.inference_mode(False)
def run_mc_dropout(
    model: nn.Module,
    features: torch.Tensor,
    *,
    config: UncertaintyConfig | None = None,
) -> np.ndarray:
    """Return MC samples of per-class mean probabilities shaped (N, C)."""
    cfg = config or UncertaintyConfig()
    if cfg.seed is not None:
        torch.manual_seed(cfg.seed)
        np.random.seed(cfg.seed)
    model.eval()
    enable_mc_dropout(model, dropout_p=cfg.dropout_p)
    samples: list[np.ndarray] = []
    with torch.no_grad():
        for _ in range(cfg.mc_samples):
            logits = model(features)
            probs = torch.sigmoid(logits)
            # Spatial mean per class for compact assessment scores.
            sample = probs.mean(dim=(0, 2, 3)).detach().cpu().numpy()
            samples.append(sample)
    model.eval()
    return np.stack(samples, axis=0)


def embedding_from_features(features: torch.Tensor) -> np.ndarray:
    """Simple domain embedding: channel-wise spatial means (C,)."""
    if features.ndim != 4:
        raise ValueError("features must be BCHW")
    return features.mean(dim=(0, 2, 3)).detach().cpu().numpy().astype(np.float64)


def assess_from_mc_samples(
    samples: np.ndarray,
    *,
    hazard_names: Sequence[str],
    domain_similarity: float | None,
    config: UncertaintyConfig | None = None,
    primary_drivers_by_class: Mapping[int, Sequence[str]] | None = None,
    assessment_id: str = "assessment",
    model_version: str = "unknown",
    explanation: str = "",
    domain_similarity_calibrated: bool = True,
) -> AssessmentResult:
    cfg = config or UncertaintyConfig()
    if samples.ndim != 2:
        raise ValueError("samples must be shaped (N, C)")
    profiles: list[HazardUncertainty] = []
    for class_index, hazard_name in enumerate(hazard_names):
        class_samples = samples[:, class_index]
        median = float(np.median(class_samples))
        ci80 = empirical_credible_interval(class_samples, level=cfg.interval_80)
        ci95 = empirical_credible_interval(class_samples, level=cfg.interval_95)
        # Uncalibrated domain similarity must not drive tiers via a fake 0.5 score.
        # Conservative: report Low until a real reference centroid is configured.
        if not domain_similarity_calibrated or domain_similarity is None:
            tier = ConfidenceTier.LOW
            similarity_score: float | None = None
        else:
            tier = assign_confidence_tier(
                interval_width=ci80.width(),
                domain_similarity=float(domain_similarity),
                config=cfg,
            )
            similarity_score = float(domain_similarity)
        drivers = tuple(primary_drivers_by_class.get(class_index, ())[:5]) if primary_drivers_by_class else ()
        profiles.append(
            HazardUncertainty(
                hazard_type=hazard_name,
                point_estimate=median,
                credible_interval_80=ci80,
                credible_interval_95=ci95,
                domain_similarity_score=similarity_score,
                confidence_tier=tier,
                primary_drivers=drivers,
            )
        )
    return AssessmentResult(
        assessment_id=assessment_id,
        hazard_profiles=tuple(profiles),
        explanation=explanation,
        model_version=model_version,
    )


def build_template_explanation(profiles: Sequence[HazardUncertainty]) -> str:
    """Traceable template explanation from drivers/tiers (not geological advice)."""
    parts: list[str] = []
    for profile in profiles:
        drivers = ", ".join(profile.primary_drivers) if profile.primary_drivers else "model channels"
        parts.append(
            f"{profile.hazard_type}: median susceptibility {profile.point_estimate:.3f} "
            f"({profile.confidence_tier.value.lower()}); primary contributing features: {drivers}."
        )
    parts.append(
        "This explanation is derived from model attribution and uncertainty outputs; "
        "it is not a field geological validation."
    )
    return " ".join(parts)
