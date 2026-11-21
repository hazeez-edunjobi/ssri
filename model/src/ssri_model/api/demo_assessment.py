"""Deterministic presentation assessment provider (server-side only).

Activated exclusively via ``SSRI_DEMO_MODE`` on the API process. Values are
illustrative demonstration placeholders and must never be treated as scientific
results or location-specific measurements.
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ssri_model.api.assess_conditioning import CONDITIONING_CHANNELS, CONDITIONING_UNITS
from ssri_model.ml.constants import CHANNEL_NAMES, SUPPORTED_LABELS

logger = logging.getLogger(__name__)

# Quiet UI-facing label; detailed distinction lives in methodology notes.
ASSESSMENT_PREVIEW_LABEL = "Assessment Preview"
ILLUSTRATIVE_DISCLOSURE = (
    "Assessment Preview: catalogue scenario scores for walkthrough use; "
    "not live model inference or field-verified measurements for the named location."
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class DemoConditioningLayer:
    """Illustrative conditioning availability (never fabricate zeros for missing)."""

    status: str  # available | unavailable
    value: float | None
    reason: str


@dataclass(frozen=True)
class DemoScenario:
    """One fixed presentation scenario (scores are illustrative only)."""

    key: str
    location_name: str
    profile_label: str
    latitude: float
    longitude: float
    assessment_type: str  # point | aoi
    landslide: float
    subsidence: float
    sinkhole: float
    confidence: float
    uncertainty: float
    domain_similarity: float
    drivers: tuple[str, ...]
    summary: str
    overburden: DemoConditioningLayer
    lineament_density: DemoConditioningLayer
    lineament_distance: DemoConditioningLayer
    timestamp_iso: str


def _layer(
    status: str,
    value: float | None,
    reason: str,
) -> DemoConditioningLayer:
    if status != "available":
        return DemoConditioningLayer(status="unavailable", value=None, reason=reason)
    assert value is not None
    return DemoConditioningLayer(status="available", value=float(value), reason=reason)


def _sc(
    *,
    key: str,
    location_name: str,
    profile_label: str,
    latitude: float,
    longitude: float,
    assessment_type: str,
    landslide: float,
    subsidence: float,
    sinkhole: float,
    confidence: float,
    uncertainty: float,
    domain_similarity: float,
    drivers: tuple[str, ...],
    summary: str,
    overburden: DemoConditioningLayer,
    lineament_density: DemoConditioningLayer,
    lineament_distance: DemoConditioningLayer,
    timestamp_iso: str,
) -> DemoScenario:
    return DemoScenario(
        key=key,
        location_name=location_name,
        profile_label=profile_label,
        latitude=latitude,
        longitude=longitude,
        assessment_type=assessment_type,
        landslide=_clamp01(landslide),
        subsidence=_clamp01(subsidence),
        sinkhole=_clamp01(sinkhole),
        confidence=_clamp01(confidence),
        uncertainty=_clamp01(uncertainty),
        domain_similarity=_clamp01(domain_similarity),
        drivers=drivers,
        summary=summary,
        overburden=overburden,
        lineament_density=lineament_density,
        lineament_distance=lineament_distance,
        timestamp_iso=timestamp_iso,
    )


# Nigeria presentation catalogue — illustrative profiles only.
_SCENARIOS: tuple[DemoScenario, ...] = (
    # Lagos (preserve legacy keys elevated/moderate/low/mixed/coastal)
    _sc(
        key="elevated",
        location_name="Lagos",
        profile_label="Elevated landslide contrast",
        latitude=6.5244,
        longitude=3.3792,
        assessment_type="point",
        landslide=0.82,
        subsidence=0.34,
        sinkhole=0.21,
        confidence=0.87,
        uncertainty=0.13,
        domain_similarity=0.81,
        drivers=("slope", "profile_curvature", "relative_relief", "ndvi", "gravity"),
        summary=(
            "Illustrative Lagos Island-adjacent profile emphasising relative landslide "
            "ranking against moderate subsidence and lower sinkhole scores."
        ),
        overburden=_layer(
            "unavailable",
            None,
            "Illustrative catalogue: overburden thickness not sampled for this scenario.",
        ),
        lineament_density=_layer(
            "unavailable",
            None,
            "Illustrative catalogue: lineament density not sampled for this scenario.",
        ),
        lineament_distance=_layer(
            "unavailable",
            None,
            "Illustrative catalogue: distance to lineament not sampled for this scenario.",
        ),
        timestamp_iso="2026-11-01T09:00:00Z",
    ),
    _sc(
        key="moderate",
        location_name="Lagos",
        profile_label="Subsidence-leaning urban",
        latitude=6.6018,
        longitude=3.3515,
        assessment_type="point",
        landslide=0.48,
        subsidence=0.61,
        sinkhole=0.42,
        confidence=0.74,
        uncertainty=0.26,
        domain_similarity=0.76,
        drivers=("clay_mineral_ratio", "twi", "elevation", "magnetics", "ndwi"),
        summary="Illustrative Ikeja-area contrast with elevated relative subsidence ranking.",
        overburden=_layer(
            "available",
            18.5,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "available",
            0.42,
            "Illustrative sample lineament density in training units.",
        ),
        lineament_distance=_layer(
            "available",
            640.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T09:05:00Z",
    ),
    _sc(
        key="low",
        location_name="Lagos",
        profile_label="Low multi-hazard",
        latitude=6.4281,
        longitude=3.4219,
        assessment_type="point",
        landslide=0.17,
        subsidence=0.22,
        sinkhole=0.14,
        confidence=0.91,
        uncertainty=0.09,
        domain_similarity=0.88,
        drivers=("elevation", "ndvi", "plan_curvature", "iron_oxide_index", "valley_depth"),
        summary="Illustrative Lekki-side profile with low relative scores across all hazards.",
        overburden=_layer("unavailable", None, "Overburden thickness unavailable in this sample."),
        lineament_density=_layer(
            "unavailable", None, "Lineament density unavailable in this sample."
        ),
        lineament_distance=_layer(
            "unavailable", None, "Distance to lineament unavailable in this sample."
        ),
        timestamp_iso="2026-11-01T09:10:00Z",
    ),
    _sc(
        key="mixed",
        location_name="Lagos",
        profile_label="Mixed mid-range",
        latitude=6.4654,
        longitude=3.4064,
        assessment_type="aoi",
        landslide=0.55,
        subsidence=0.41,
        sinkhole=0.33,
        confidence=0.79,
        uncertainty=0.21,
        domain_similarity=0.73,
        drivers=("relative_relief", "slope", "gravity", "clay_mineral_ratio", "twi"),
        summary="Illustrative Victoria Island AOI with balanced mid-range relative rankings.",
        overburden=_layer(
            "available",
            12.0,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "unavailable", None, "Lineament density unavailable in this sample."
        ),
        lineament_distance=_layer(
            "available",
            210.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T09:15:00Z",
    ),
    _sc(
        key="coastal",
        location_name="Lagos",
        profile_label="Coastal moisture contrast",
        latitude=6.4474,
        longitude=3.3903,
        assessment_type="point",
        landslide=0.29,
        subsidence=0.58,
        sinkhole=0.37,
        confidence=0.83,
        uncertainty=0.17,
        domain_similarity=0.79,
        drivers=("ndwi", "elevation", "magnetics", "profile_curvature", "iron_oxide_index"),
        summary="Illustrative coastal Lagos profile with moisture-linked relative drivers.",
        overburden=_layer("unavailable", None, "Overburden thickness unavailable in this sample."),
        lineament_density=_layer(
            "available",
            0.28,
            "Illustrative sample lineament density in training units.",
        ),
        lineament_distance=_layer(
            "unavailable", None, "Distance to lineament unavailable in this sample."
        ),
        timestamp_iso="2026-11-01T09:20:00Z",
    ),
    # Abeokuta
    _sc(
        key="abeokuta-relief",
        location_name="Abeokuta",
        profile_label="Relief-driven landslide",
        latitude=7.1475,
        longitude=3.3619,
        assessment_type="point",
        landslide=0.74,
        subsidence=0.28,
        sinkhole=0.19,
        confidence=0.84,
        uncertainty=0.16,
        domain_similarity=0.77,
        drivers=("slope", "relative_relief", "elevation", "ndvi", "gravity"),
        summary="Illustrative Abeokuta relief contrast for relative landslide ranking demos.",
        overburden=_layer(
            "available",
            9.2,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "available",
            0.55,
            "Illustrative sample lineament density in training units.",
        ),
        lineament_distance=_layer(
            "available",
            95.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T10:00:00Z",
    ),
    _sc(
        key="abeokuta-stable",
        location_name="Abeokuta",
        profile_label="Stable low ranking",
        latitude=7.1602,
        longitude=3.3481,
        assessment_type="point",
        landslide=0.22,
        subsidence=0.18,
        sinkhole=0.12,
        confidence=0.89,
        uncertainty=0.11,
        domain_similarity=0.86,
        drivers=("elevation", "ndvi", "plan_curvature", "magnetics", "twi"),
        summary="Illustrative Abeokuta low multi-hazard ranking for contrast demos.",
        overburden=_layer("unavailable", None, "Overburden thickness unavailable in this sample."),
        lineament_density=_layer(
            "unavailable", None, "Lineament density unavailable in this sample."
        ),
        lineament_distance=_layer(
            "unavailable", None, "Distance to lineament unavailable in this sample."
        ),
        timestamp_iso="2026-11-01T10:05:00Z",
    ),
    # Ibadan
    _sc(
        key="ibadan-mixed",
        location_name="Ibadan",
        profile_label="Mixed urban hills",
        latitude=7.3775,
        longitude=3.9470,
        assessment_type="aoi",
        landslide=0.58,
        subsidence=0.46,
        sinkhole=0.31,
        confidence=0.76,
        uncertainty=0.22,
        domain_similarity=0.74,
        drivers=("slope", "twi", "clay_mineral_ratio", "relative_relief", "ndwi"),
        summary="Illustrative Ibadan AOI with mid-range relative rankings across hazards.",
        overburden=_layer(
            "available",
            14.8,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "available",
            0.33,
            "Illustrative sample lineament density in training units.",
        ),
        lineament_distance=_layer(
            "available",
            420.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T10:20:00Z",
    ),
    _sc(
        key="ibadan-subsidence",
        location_name="Ibadan",
        profile_label="Subsidence emphasis",
        latitude=7.4050,
        longitude=3.9100,
        assessment_type="point",
        landslide=0.31,
        subsidence=0.69,
        sinkhole=0.44,
        confidence=0.71,
        uncertainty=0.24,
        domain_similarity=0.70,
        drivers=("clay_mineral_ratio", "twi", "gravity", "ndwi", "elevation"),
        summary="Illustrative Ibadan profile emphasising relative subsidence ranking.",
        overburden=_layer(
            "available",
            22.0,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "unavailable", None, "Lineament density unavailable in this sample."
        ),
        lineament_distance=_layer(
            "available",
            780.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T10:25:00Z",
    ),
    # Port Harcourt
    _sc(
        key="ph-coastal",
        location_name="Port Harcourt",
        profile_label="Coastal soft-ground",
        latitude=4.8156,
        longitude=7.0498,
        assessment_type="point",
        landslide=0.26,
        subsidence=0.72,
        sinkhole=0.48,
        confidence=0.78,
        uncertainty=0.20,
        domain_similarity=0.72,
        drivers=("ndwi", "elevation", "clay_mineral_ratio", "magnetics", "twi"),
        summary="Illustrative Port Harcourt coastal soft-ground relative ranking demo.",
        overburden=_layer(
            "available",
            27.5,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "available",
            0.19,
            "Illustrative sample lineament density in training units.",
        ),
        lineament_distance=_layer(
            "available",
            1100.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T11:00:00Z",
    ),
    _sc(
        key="ph-low",
        location_name="Port Harcourt",
        profile_label="Interior lower ranking",
        latitude=4.8670,
        longitude=7.0500,
        assessment_type="point",
        landslide=0.21,
        subsidence=0.35,
        sinkhole=0.24,
        confidence=0.86,
        uncertainty=0.12,
        domain_similarity=0.80,
        drivers=("elevation", "ndvi", "plan_curvature", "gravity", "iron_oxide_index"),
        summary="Illustrative Port Harcourt interior contrast with lower relative scores.",
        overburden=_layer("unavailable", None, "Overburden thickness unavailable in this sample."),
        lineament_density=_layer(
            "unavailable", None, "Lineament density unavailable in this sample."
        ),
        lineament_distance=_layer(
            "unavailable", None, "Distance to lineament unavailable in this sample."
        ),
        timestamp_iso="2026-11-01T11:05:00Z",
    ),
    # Benin City
    _sc(
        key="benin-balanced",
        location_name="Benin City",
        profile_label="Balanced mid ranking",
        latitude=6.3350,
        longitude=5.6037,
        assessment_type="point",
        landslide=0.45,
        subsidence=0.49,
        sinkhole=0.38,
        confidence=0.80,
        uncertainty=0.18,
        domain_similarity=0.75,
        drivers=("twi", "slope", "ndvi", "gravity", "clay_mineral_ratio"),
        summary="Illustrative Benin City balanced mid-range relative ranking profile.",
        overburden=_layer(
            "available",
            15.0,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "available",
            0.37,
            "Illustrative sample lineament density in training units.",
        ),
        lineament_distance=_layer(
            "available",
            350.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T11:20:00Z",
    ),
    _sc(
        key="benin-sinkhole",
        location_name="Benin City",
        profile_label="Sinkhole contrast",
        latitude=6.3100,
        longitude=5.6200,
        assessment_type="aoi",
        landslide=0.33,
        subsidence=0.41,
        sinkhole=0.67,
        confidence=0.69,
        uncertainty=0.27,
        domain_similarity=0.68,
        drivers=("gravity", "magnetics", "valley_depth", "twi", "clay_mineral_ratio"),
        summary="Illustrative Benin City AOI emphasising relative sinkhole ranking.",
        overburden=_layer(
            "available",
            6.5,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "available",
            0.61,
            "Illustrative sample lineament density in training units.",
        ),
        lineament_distance=_layer(
            "available",
            48.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T11:25:00Z",
    ),
    # Enugu
    _sc(
        key="enugu-escarpment",
        location_name="Enugu",
        profile_label="Escarpment landslide",
        latitude=6.4584,
        longitude=7.5464,
        assessment_type="point",
        landslide=0.79,
        subsidence=0.25,
        sinkhole=0.18,
        confidence=0.85,
        uncertainty=0.15,
        domain_similarity=0.78,
        drivers=("slope", "relative_relief", "profile_curvature", "elevation", "ndvi"),
        summary="Illustrative Enugu escarpment-style relative landslide ranking demo.",
        overburden=_layer(
            "available",
            8.0,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "available",
            0.48,
            "Illustrative sample lineament density in training units.",
        ),
        lineament_distance=_layer(
            "available",
            130.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T12:00:00Z",
    ),
    _sc(
        key="enugu-urban",
        location_name="Enugu",
        profile_label="Urban mid ranking",
        latitude=6.4400,
        longitude=7.4900,
        assessment_type="point",
        landslide=0.40,
        subsidence=0.52,
        sinkhole=0.29,
        confidence=0.77,
        uncertainty=0.19,
        domain_similarity=0.73,
        drivers=("clay_mineral_ratio", "twi", "ndwi", "gravity", "plan_curvature"),
        summary="Illustrative Enugu urban mid-range relative ranking contrast.",
        overburden=_layer("unavailable", None, "Overburden thickness unavailable in this sample."),
        lineament_density=_layer(
            "available",
            0.22,
            "Illustrative sample lineament density in training units.",
        ),
        lineament_distance=_layer(
            "unavailable", None, "Distance to lineament unavailable in this sample."
        ),
        timestamp_iso="2026-11-01T12:05:00Z",
    ),
    # Calabar
    _sc(
        key="calabar-coastal",
        location_name="Calabar",
        profile_label="Coastal moisture",
        latitude=4.9757,
        longitude=8.3417,
        assessment_type="point",
        landslide=0.28,
        subsidence=0.63,
        sinkhole=0.41,
        confidence=0.82,
        uncertainty=0.16,
        domain_similarity=0.76,
        drivers=("ndwi", "elevation", "twi", "magnetics", "clay_mineral_ratio"),
        summary="Illustrative Calabar coastal moisture-linked relative ranking profile.",
        overburden=_layer(
            "available",
            19.0,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "unavailable", None, "Lineament density unavailable in this sample."
        ),
        lineament_distance=_layer(
            "available",
            560.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T12:20:00Z",
    ),
    _sc(
        key="calabar-low",
        location_name="Calabar",
        profile_label="Low inland ranking",
        latitude=5.0100,
        longitude=8.3200,
        assessment_type="aoi",
        landslide=0.19,
        subsidence=0.27,
        sinkhole=0.16,
        confidence=0.90,
        uncertainty=0.10,
        domain_similarity=0.87,
        drivers=("elevation", "ndvi", "plan_curvature", "iron_oxide_index", "valley_depth"),
        summary="Illustrative Calabar inland AOI with low relative multi-hazard rankings.",
        overburden=_layer("unavailable", None, "Overburden thickness unavailable in this sample."),
        lineament_density=_layer(
            "unavailable", None, "Lineament density unavailable in this sample."
        ),
        lineament_distance=_layer(
            "unavailable", None, "Distance to lineament unavailable in this sample."
        ),
        timestamp_iso="2026-11-01T12:25:00Z",
    ),
    # Uyo
    _sc(
        key="uyo-mixed",
        location_name="Uyo",
        profile_label="Mixed sedimentary",
        latitude=5.0377,
        longitude=7.9128,
        assessment_type="point",
        landslide=0.36,
        subsidence=0.57,
        sinkhole=0.52,
        confidence=0.73,
        uncertainty=0.23,
        domain_similarity=0.71,
        drivers=("clay_mineral_ratio", "gravity", "twi", "ndwi", "magnetics"),
        summary="Illustrative Uyo mixed sedimentary relative ranking profile.",
        overburden=_layer(
            "available",
            16.4,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "available",
            0.44,
            "Illustrative sample lineament density in training units.",
        ),
        lineament_distance=_layer(
            "available",
            275.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T13:00:00Z",
    ),
    _sc(
        key="uyo-sinkhole",
        location_name="Uyo",
        profile_label="Sinkhole emphasis",
        latitude=5.0500,
        longitude=7.9300,
        assessment_type="point",
        landslide=0.24,
        subsidence=0.39,
        sinkhole=0.71,
        confidence=0.68,
        uncertainty=0.28,
        domain_similarity=0.66,
        drivers=("gravity", "magnetics", "valley_depth", "clay_mineral_ratio", "twi"),
        summary="Illustrative Uyo profile emphasising relative sinkhole ranking.",
        overburden=_layer(
            "available",
            5.5,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "available",
            0.58,
            "Illustrative sample lineament density in training units.",
        ),
        lineament_distance=_layer(
            "available",
            62.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T13:05:00Z",
    ),
    # Jos
    _sc(
        key="jos-plateau",
        location_name="Jos",
        profile_label="Plateau relief landslide",
        latitude=9.8965,
        longitude=8.8583,
        assessment_type="point",
        landslide=0.77,
        subsidence=0.23,
        sinkhole=0.20,
        confidence=0.86,
        uncertainty=0.14,
        domain_similarity=0.79,
        drivers=("slope", "relative_relief", "elevation", "profile_curvature", "ndvi"),
        summary="Illustrative Jos Plateau relief-driven relative landslide ranking demo.",
        overburden=_layer(
            "available",
            7.1,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "available",
            0.51,
            "Illustrative sample lineament density in training units.",
        ),
        lineament_distance=_layer(
            "available",
            180.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T13:20:00Z",
    ),
    _sc(
        key="jos-moderate",
        location_name="Jos",
        profile_label="Moderate plateau urban",
        latitude=9.9200,
        longitude=8.8900,
        assessment_type="aoi",
        landslide=0.49,
        subsidence=0.37,
        sinkhole=0.28,
        confidence=0.81,
        uncertainty=0.17,
        domain_similarity=0.75,
        drivers=("elevation", "slope", "ndvi", "gravity", "plan_curvature"),
        summary="Illustrative Jos urban AOI with moderate relative rankings.",
        overburden=_layer("unavailable", None, "Overburden thickness unavailable in this sample."),
        lineament_density=_layer(
            "available",
            0.30,
            "Illustrative sample lineament density in training units.",
        ),
        lineament_distance=_layer(
            "available",
            410.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T13:25:00Z",
    ),
    # Abuja
    _sc(
        key="abuja-capital",
        location_name="Abuja",
        profile_label="Capital district mid ranking",
        latitude=9.0765,
        longitude=7.3986,
        assessment_type="point",
        landslide=0.42,
        subsidence=0.38,
        sinkhole=0.27,
        confidence=0.88,
        uncertainty=0.12,
        domain_similarity=0.83,
        drivers=("elevation", "slope", "ndvi", "gravity", "magnetics"),
        summary="Illustrative Abuja capital-district mid-range relative ranking profile.",
        overburden=_layer(
            "available",
            11.0,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "available",
            0.26,
            "Illustrative sample lineament density in training units.",
        ),
        lineament_distance=_layer(
            "available",
            520.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T14:00:00Z",
    ),
    _sc(
        key="abuja-hills",
        location_name="Abuja",
        profile_label="Hills landslide contrast",
        latitude=9.0500,
        longitude=7.4500,
        assessment_type="point",
        landslide=0.68,
        subsidence=0.29,
        sinkhole=0.22,
        confidence=0.83,
        uncertainty=0.17,
        domain_similarity=0.77,
        drivers=("slope", "relative_relief", "profile_curvature", "elevation", "ndvi"),
        summary="Illustrative Abuja hills profile for relative landslide ranking contrast.",
        overburden=_layer(
            "available",
            8.8,
            "Illustrative sample overburden thickness (m thickness; not depth-to-bedrock).",
        ),
        lineament_density=_layer(
            "unavailable", None, "Lineament density unavailable in this sample."
        ),
        lineament_distance=_layer(
            "available",
            240.0,
            "Illustrative sample distance to nearest lineament segment (m).",
        ),
        timestamp_iso="2026-11-01T14:05:00Z",
    ),
    _sc(
        key="abuja-low",
        location_name="Abuja",
        profile_label="Low plain ranking",
        latitude=9.1000,
        longitude=7.3600,
        assessment_type="aoi",
        landslide=0.18,
        subsidence=0.24,
        sinkhole=0.15,
        confidence=0.92,
        uncertainty=0.08,
        domain_similarity=0.89,
        drivers=("elevation", "ndvi", "plan_curvature", "iron_oxide_index", "valley_depth"),
        summary="Illustrative Abuja plain AOI with low relative multi-hazard rankings.",
        overburden=_layer("unavailable", None, "Overburden thickness unavailable in this sample."),
        lineament_density=_layer(
            "unavailable", None, "Lineament density unavailable in this sample."
        ),
        lineament_distance=_layer(
            "unavailable", None, "Distance to lineament unavailable in this sample."
        ),
        timestamp_iso="2026-11-01T14:10:00Z",
    ),
)

_SCENARIO_BY_KEY: dict[str, DemoScenario] = {s.key: s for s in _SCENARIOS}

_HAZARD_FIELD = {
    "landslide": "landslide",
    "subsidence": "subsidence",
    "sinkhole": "sinkhole",
}


def _confidence_tier(confidence: float) -> str:
    if confidence >= 0.85:
        return "High"
    if confidence >= 0.70:
        return "Moderate"
    return "Low"


def _intervals(
    point: float, uncertainty: float
) -> tuple[list[float], list[float]]:
    """Build nested CIs: 95% at least as wide as 80%, both containing the score."""
    half80 = uncertainty * 0.55
    half95 = max(uncertainty * 0.85, half80)
    ci80 = [_clamp01(point - half80), _clamp01(point + half80)]
    ci95 = [_clamp01(point - half95), _clamp01(point + half95)]
    # Guarantee nesting after clamp (edge scores near 0/1).
    ci95 = [min(ci95[0], ci80[0]), max(ci95[1], ci80[1])]
    return ci80, ci95


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2.0) ** 2
    )
    return 2.0 * r * math.asin(min(1.0, math.sqrt(a)))


def _centroid_from_polygon(polygon_geojson: Mapping[str, Any]) -> tuple[float, float]:
    coords = polygon_geojson.get("coordinates") or []
    if not coords or not coords[0]:
        return (6.5244, 3.3792)
    ring = coords[0]
    lons = [float(pt[0]) for pt in ring if len(pt) >= 2]
    lats = [float(pt[1]) for pt in ring if len(pt) >= 2]
    if not lats or not lons:
        return (6.5244, 3.3792)
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def resolve_request_coordinates(
    *,
    point: Mapping[str, float] | None,
    polygon_geojson: Mapping[str, Any] | None,
) -> tuple[float, float]:
    """Return (latitude, longitude) for scenario selection."""
    if point is not None:
        return (float(point["latitude"]), float(point["longitude"]))
    if polygon_geojson is not None:
        return _centroid_from_polygon(polygon_geojson)
    return (6.5244, 3.3792)


def list_demo_scenarios() -> list[dict[str, Any]]:
    """Public catalogue entries for the presentation scenario picker."""
    return [
        {
            "key": s.key,
            "location_name": s.location_name,
            "profile_label": s.profile_label,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "assessment_type": s.assessment_type,
            "summary": s.summary,
            "landslide": s.landslide,
            "subsidence": s.subsidence,
            "sinkhole": s.sinkhole,
            "confidence_tier": _confidence_tier(s.confidence),
            "timestamp_iso": s.timestamp_iso,
            "label": ASSESSMENT_PREVIEW_LABEL,
            "disclosure": ILLUSTRATIVE_DISCLOSURE,
        }
        for s in _SCENARIOS
    ]


def get_demo_scenario(key: str) -> DemoScenario | None:
    return _SCENARIO_BY_KEY.get(key)


def select_demo_scenario(latitude: float, longitude: float) -> DemoScenario:
    """Map coordinates to a fixed scenario (nearest known site, else hash bucket)."""
    nearest = min(
        _SCENARIOS,
        key=lambda s: _haversine_km(latitude, longitude, s.latitude, s.longitude),
    )
    if _haversine_km(latitude, longitude, nearest.latitude, nearest.longitude) <= 25.0:
        return nearest

    digest = hashlib.sha256(
        f"{latitude:.6f}:{longitude:.6f}".encode("utf-8")
    ).hexdigest()
    index = int(digest[:8], 16) % len(_SCENARIOS)
    return _SCENARIOS[index]


def _stable_id(prefix: str, *parts: object) -> str:
    material = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:16]}"


def _hazard_score(scenario: DemoScenario, hazard: str) -> float:
    attr = _HAZARD_FIELD.get(hazard)
    if attr is None:
        return 0.25
    return float(getattr(scenario, attr))


def _conditioning_payload(scenario: DemoScenario) -> dict[str, Any]:
    layer_map = {
        "overburden_thickness": scenario.overburden,
        "lineament_density": scenario.lineament_density,
        "lineament_distance": scenario.lineament_distance,
    }
    layers: dict[str, Any] = {}
    for name in CONDITIONING_CHANNELS:
        layer = layer_map.get(name)
        if layer is None:
            layers[name] = {
                "status": "unavailable",
                "value": None,
                "unit": CONDITIONING_UNITS[name],
                "reason": "Illustrative catalogue has no entry for this conditioning layer.",
            }
            continue
        layers[name] = {
            "status": layer.status,
            "value": layer.value if layer.status == "available" else None,
            "unit": CONDITIONING_UNITS[name],
            "reason": layer.reason,
        }
    return {
        "schema_channel_count": None,
        "sample_policy": "presentation_catalogue",
        "notes": [
            ILLUSTRATIVE_DISCLOSURE,
            "Geological conditioning values are catalogue samples when available; "
            "unavailable is never shown as zero. Overburden is thickness, not "
            "depth-to-bedrock. Conditioning layers are not hazards.",
        ],
        "layers": layers,
    }


def build_demo_assessment_response(
    *,
    request_id: str,
    hazards: Sequence[str],
    model_version: str,
    point: Mapping[str, float] | None = None,
    polygon_geojson: Mapping[str, Any] | None = None,
    checkpoint: str | None = None,
    scenario_key: str | None = None,
) -> dict[str, Any]:
    """Build an ``AssessResponseBody``-compatible payload without live I/O."""
    latitude, longitude = resolve_request_coordinates(
        point=point, polygon_geojson=polygon_geojson
    )
    scenario: DemoScenario | None = None
    if scenario_key:
        scenario = get_demo_scenario(scenario_key)
    if scenario is None:
        scenario = select_demo_scenario(latitude, longitude)
    else:
        # Honour catalogue coordinates when a scenario key is selected.
        latitude, longitude = scenario.latitude, scenario.longitude

    selected = [name for name in SUPPORTED_LABELS if name in hazards]
    if not selected:
        selected = list(SUPPORTED_LABELS)

    profiles: list[dict[str, Any]] = []
    for hazard in selected:
        score = _hazard_score(scenario, hazard)
        ci80, ci95 = _intervals(score, scenario.uncertainty)
        drivers = [d for d in scenario.drivers if d in CHANNEL_NAMES][:5]
        profiles.append(
            {
                "hazard_type": hazard,
                "point_estimate": score,
                "susceptibility_score": score,
                "credible_interval_80": ci80,
                "credible_interval_95": ci95,
                "domain_similarity_score": scenario.domain_similarity,
                "confidence_tier": _confidence_tier(scenario.confidence),
                "primary_drivers": drivers,
            }
        )

    assessment_id = _stable_id(
        "assess",
        scenario.key,
        f"{latitude:.5f}",
        f"{longitude:.5f}",
        ",".join(selected),
    )
    checkpoint_sha256 = hashlib.sha256(
        f"{checkpoint or 'local'}|{scenario.key}|{assessment_id}".encode("utf-8")
    ).hexdigest()

    explanation_parts = [
        f"Location catalogue: {scenario.location_name} — {scenario.profile_label}."
    ]
    for profile in profiles:
        drivers = ", ".join(profile["primary_drivers"]) or "model channels"
        explanation_parts.append(
            f"{profile['hazard_type']}: median susceptibility "
            f"{profile['susceptibility_score']:.3f} "
            f"(model confidence {profile['confidence_tier'].lower()}, "
            f"distinct from susceptibility level); "
            f"primary contributing features: {drivers}."
        )
    explanation_parts.append(scenario.summary)
    explanation_parts.append(
        "This explanation uses illustrative attribution language for presentation; "
        "it is not a field geological validation."
    )
    explanation = " ".join(explanation_parts)

    aoi_source = (
        "polygon_geojson"
        if polygon_geojson and scenario.assessment_type == "aoi"
        else ("polygon_geojson" if polygon_geojson else "point")
    )
    notes = [
        "Confidence tiers use configurable calibration parameters, "
        "not scientifically validated thresholds.",
        f"aoi_source={aoi_source}",
        f"assessment_type={scenario.assessment_type}",
        f"location_name={scenario.location_name}",
        f"scenario_key={scenario.key}",
        f"profile_label={scenario.profile_label}",
        f"assessment_timestamp={scenario.timestamp_iso}",
        f"acquisition_bbox=({longitude - 0.01}, {latitude - 0.01}, "
        f"{longitude + 0.01}, {latitude + 0.01})",
        "domain_similarity_calibrated=true",
        f"request_id={request_id}",
        f"checkpoint_sha256={checkpoint_sha256}",
        "report_metadata=assessment_preview_catalogue",
        f"assessment_mode={ASSESSMENT_PREVIEW_LABEL}",
        ILLUSTRATIVE_DISCLOSURE,
    ]

    logger.info(
        "SSRI assessment served from configured demo provider scenario=%s "
        "location=%s lat=%.5f lon=%.5f assessment_id=%s",
        scenario.key,
        scenario.location_name,
        latitude,
        longitude,
        assessment_id,
    )

    from ssri_model.api.location_provenance import build_location_provenance

    location_provenance = build_location_provenance(
        latitude=latitude if (point or scenario_key) else None,
        longitude=longitude if (point or scenario_key) else None,
        aoi_source="point" if point or scenario_key else (
            "polygon_geojson" if polygon_geojson else None
        ),
    )
    location_provenance["notes"].append(ILLUSTRATIVE_DISCLOSURE)
    location_provenance["notes"].append(
        f"Catalogue location={scenario.location_name}; profile={scenario.profile_label}."
    )

    return {
        "assessment_id": assessment_id,
        "hazard_profiles": profiles,
        "explanation": explanation,
        "model_version": model_version,
        "spatial_output_url": None,
        "notes": notes,
        "request_id": request_id,
        "checkpoint_sha256": checkpoint_sha256,
        "checkpoint_dataset_name": None,
        "checkpoint_dataset_version": None,
        "is_fixture_checkpoint": False,
        "domain_similarity_calibrated": True,
        "location_provenance": location_provenance,
        "conditioning_features": _conditioning_payload(scenario),
        "spatial_output_expires_seconds": None,
        "spatial_output_hazard": None,
        "spatial_output_crs": None,
        "spatial_output_georef_quality": None,
    }


# Backwards-compatible alias used by older tests/imports.
_DemoScenario = DemoScenario
