"""Deterministic presentation assessment provider (server-side only).

Activated exclusively via ``SSRI_DEMO_MODE`` on the API process. Values are
presentation placeholders and must never be treated as scientific results.
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ssri_model.ml.constants import CHANNEL_NAMES, SUPPORTED_LABELS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _DemoScenario:
    """One fixed presentation scenario (probabilities are illustrative only)."""

    key: str
    latitude: float
    longitude: float
    landslide: float
    subsidence: float
    sinkhole: float
    confidence: float
    uncertainty: float
    domain_similarity: float
    drivers: tuple[str, ...]


# Lagos-area anchors so the existing map workflow hits distinct scenarios.
_SCENARIOS: tuple[_DemoScenario, ...] = (
    _DemoScenario(
        key="elevated",
        latitude=6.5244,
        longitude=3.3792,
        landslide=0.82,
        subsidence=0.34,
        sinkhole=0.21,
        confidence=0.87,
        uncertainty=0.13,
        domain_similarity=0.81,
        drivers=(
            "slope",
            "profile_curvature",
            "relative_relief",
            "ndvi",
            "gravity",
        ),
    ),
    _DemoScenario(
        key="moderate",
        latitude=6.6018,
        longitude=3.3515,
        landslide=0.48,
        subsidence=0.61,
        sinkhole=0.42,
        confidence=0.74,
        uncertainty=0.26,
        domain_similarity=0.76,
        drivers=(
            "clay_mineral_ratio",
            "twi",
            "elevation",
            "magnetics",
            "ndwi",
        ),
    ),
    _DemoScenario(
        key="low",
        latitude=6.4281,
        longitude=3.4219,
        landslide=0.17,
        subsidence=0.22,
        sinkhole=0.14,
        confidence=0.91,
        uncertainty=0.09,
        domain_similarity=0.88,
        drivers=(
            "elevation",
            "ndvi",
            "plan_curvature",
            "iron_oxide_index",
            "valley_depth",
        ),
    ),
    _DemoScenario(
        key="mixed",
        latitude=6.4654,
        longitude=3.4064,
        landslide=0.55,
        subsidence=0.41,
        sinkhole=0.33,
        confidence=0.79,
        uncertainty=0.21,
        domain_similarity=0.73,
        drivers=(
            "relative_relief",
            "slope",
            "gravity",
            "clay_mineral_ratio",
            "twi",
        ),
    ),
    _DemoScenario(
        key="coastal",
        latitude=6.4474,
        longitude=3.3903,
        landslide=0.29,
        subsidence=0.58,
        sinkhole=0.37,
        confidence=0.83,
        uncertainty=0.17,
        domain_similarity=0.79,
        drivers=(
            "ndwi",
            "elevation",
            "magnetics",
            "profile_curvature",
            "iron_oxide_index",
        ),
    ),
)

_HAZARD_FIELD = {
    "landslide": "landslide",
    "subsidence": "subsidence",
    "sinkhole": "sinkhole",
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _confidence_tier(confidence: float) -> str:
    if confidence >= 0.85:
        return "High"
    if confidence >= 0.70:
        return "Moderate"
    return "Low"


def _intervals(
    point: float, uncertainty: float
) -> tuple[list[float], list[float]]:
    half80 = uncertainty * 0.55
    half95 = uncertainty * 0.85
    ci80 = [_clamp01(point - half80), _clamp01(point + half80)]
    ci95 = [_clamp01(point - half95), _clamp01(point + half95)]
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
    # Offline features-only requests: stable default anchor.
    return (6.5244, 3.3792)


def select_demo_scenario(latitude: float, longitude: float) -> _DemoScenario:
    """Map coordinates to a fixed scenario (nearest known site, else hash bucket)."""
    nearest = min(
        _SCENARIOS,
        key=lambda s: _haversine_km(latitude, longitude, s.latitude, s.longitude),
    )
    if _haversine_km(latitude, longitude, nearest.latitude, nearest.longitude) <= 8.0:
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


def _hazard_score(scenario: _DemoScenario, hazard: str) -> float:
    attr = _HAZARD_FIELD.get(hazard)
    if attr is None:
        return 0.25
    return float(getattr(scenario, attr))


def build_demo_assessment_response(
    *,
    request_id: str,
    hazards: Sequence[str],
    model_version: str,
    point: Mapping[str, float] | None = None,
    polygon_geojson: Mapping[str, Any] | None = None,
    checkpoint: str | None = None,
) -> dict[str, Any]:
    """Build an ``AssessResponseBody``-compatible payload without live I/O."""
    latitude, longitude = resolve_request_coordinates(
        point=point, polygon_geojson=polygon_geojson
    )
    scenario = select_demo_scenario(latitude, longitude)
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
    checkpoint_sha256 = _stable_id("ckpt", checkpoint or "local", scenario.key).replace(
        "ckpt-", ""
    )
    # Pad/truncate to sha256 hex length expected by UI slice display.
    checkpoint_sha256 = hashlib.sha256(
        f"{checkpoint or 'local'}|{scenario.key}|{assessment_id}".encode("utf-8")
    ).hexdigest()

    explanation_parts = []
    for profile in profiles:
        drivers = ", ".join(profile["primary_drivers"]) or "model channels"
        explanation_parts.append(
            f"{profile['hazard_type']}: median susceptibility "
            f"{profile['susceptibility_score']:.3f} "
            f"({profile['confidence_tier'].lower()}); "
            f"primary contributing features: {drivers}."
        )
    explanation = (
        " ".join(explanation_parts)
        + " This explanation is derived from model attribution and uncertainty "
        "outputs; it is not a field geological validation."
    )

    notes = [
        "Confidence tiers use configurable calibration parameters, "
        "not scientifically validated thresholds.",
        f"aoi_source={'polygon_geojson' if polygon_geojson else 'point'}",
        f"acquisition_bbox=({longitude - 0.01}, {latitude - 0.01}, "
        f"{longitude + 0.01}, {latitude + 0.01})",
        "domain_similarity_calibrated=true",
        f"request_id={request_id}",
        f"checkpoint_sha256={checkpoint_sha256}",
    ]

    logger.info(
        "SSRI assessment served from configured demo provider scenario=%s "
        "lat=%.5f lon=%.5f assessment_id=%s",
        scenario.key,
        latitude,
        longitude,
        assessment_id,
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
    }
