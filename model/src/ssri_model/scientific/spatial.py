"""Spatial validation utilities for SSRI datasets."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

SplitName = Literal["train", "validation", "test"]


@dataclass(frozen=True)
class BoundingBox:
    """WGS84 bounding box."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def overlaps(self, other: BoundingBox) -> bool:
        return not (
            self.max_lon < other.min_lon
            or self.min_lon > other.max_lon
            or self.max_lat < other.min_lat
            or self.min_lat > other.max_lat
        )

    def centroid(self) -> tuple[float, float]:
        return (
            (self.min_lon + self.max_lon) / 2.0,
            (self.min_lat + self.max_lat) / 2.0,
        )


@dataclass
class SpatialOverlapFinding:
    """One spatial overlap or proximity finding."""

    sample_a: str
    split_a: SplitName
    sample_b: str
    split_b: SplitName
    overlap: bool
    distance_m: float | None
    within_buffer: bool
    explanation: str


@dataclass
class SpatialValidationResult:
    """Structured spatial validation output."""

    overlapping_samples: list[tuple[str, str, SplitName, SplitName]] = field(
        default_factory=list
    )
    buffered_samples: list[tuple[str, str, SplitName, SplitName]] = field(
        default_factory=list
    )
    findings: list[SpatialOverlapFinding] = field(default_factory=list)
    minimum_distance_m: float | None = None
    maximum_distance_m: float | None = None
    status: Literal["PASS", "WARNING", "FAIL"] = "PASS"
    messages: list[str] = field(default_factory=list)


def bbox_from_aoi(aoi: dict[str, object]) -> BoundingBox | None:
    bbox = aoi.get("bbox_wgs84")
    if not isinstance(bbox, dict):
        return None
    try:
        return BoundingBox(
            min_lon=float(bbox["min_lon"]),
            min_lat=float(bbox["min_lat"]),
            max_lon=float(bbox["max_lon"]),
            max_lat=float(bbox["max_lat"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def haversine_distance_m(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
) -> float:
    radius = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bbox_min_distance_m(a: BoundingBox, b: BoundingBox) -> float:
    if a.overlaps(b):
        return 0.0
    dx = max(b.min_lon - a.max_lon, a.min_lon - b.max_lon, 0.0)
    dy = max(b.min_lat - a.max_lat, a.min_lat - b.max_lat, 0.0)
    lon_a, lat_a = a.centroid()
    lon_b, lat_b = b.centroid()
    if dx == 0.0 and dy == 0.0:
        return haversine_distance_m(lon_a, lat_a, lon_b, lat_b)
    edge_lon = a.max_lon if b.min_lon > a.max_lon else a.min_lon
    edge_lat = a.max_lat if b.min_lat > a.max_lat else a.min_lat
    other_lon = b.min_lon if b.min_lon > a.max_lon else b.max_lon
    other_lat = b.min_lat if b.min_lat > a.max_lat else b.max_lat
    return haversine_distance_m(edge_lon, edge_lat, other_lon, other_lat)


def compute_spatial_distance(
    sample_a: dict[str, object],
    sample_b: dict[str, object],
) -> float | None:
    """Compute approximate minimum distance in meters between two sample AOIs."""
    aoi_a = sample_a.get("aoi")
    aoi_b = sample_b.get("aoi")
    if not isinstance(aoi_a, dict) or not isinstance(aoi_b, dict):
        return None
    bbox_a = bbox_from_aoi(aoi_a)
    bbox_b = bbox_from_aoi(aoi_b)
    if bbox_a is None or bbox_b is None:
        return None
    return bbox_min_distance_m(bbox_a, bbox_b)


def check_spatial_overlap(
    sample_a: dict[str, object],
    sample_b: dict[str, object],
) -> bool:
    aoi_a = sample_a.get("aoi")
    aoi_b = sample_b.get("aoi")
    if not isinstance(aoi_a, dict) or not isinstance(aoi_b, dict):
        return False
    bbox_a = bbox_from_aoi(aoi_a)
    bbox_b = bbox_from_aoi(aoi_b)
    if bbox_a is None or bbox_b is None:
        return False
    return bbox_a.overlaps(bbox_b)


def validate_spatial_splits(
    samples_by_split: dict[SplitName, dict[str, dict[str, object]]],
    *,
    spatial_buffer_m: float = 0.0,
    max_train_test_overlap: int = 0,
    max_validation_test_overlap: int = 0,
) -> SpatialValidationResult:
    """Validate spatial relationships between dataset splits."""
    result = SpatialValidationResult()
    split_pairs: list[tuple[SplitName, SplitName, int]] = [
        ("train", "validation", max_train_test_overlap),
        ("train", "test", max_train_test_overlap),
        ("validation", "test", max_validation_test_overlap),
    ]
    distances: list[float] = []

    for split_a, split_b, max_allowed in split_pairs:
        overlap_count = 0
        for sample_id_a, meta_a in samples_by_split.get(split_a, {}).items():
            for sample_id_b, meta_b in samples_by_split.get(split_b, {}).items():
                overlap = check_spatial_overlap(meta_a, meta_b)
                distance = compute_spatial_distance(meta_a, meta_b)
                within_buffer = (
                    distance is not None
                    and spatial_buffer_m > 0.0
                    and distance < spatial_buffer_m
                )
                if overlap:
                    overlap_count += 1
                    result.overlapping_samples.append(
                        (sample_id_a, sample_id_b, split_a, split_b)
                    )
                if within_buffer and not overlap:
                    result.buffered_samples.append(
                        (sample_id_a, sample_id_b, split_a, split_b)
                    )
                if overlap or within_buffer:
                    result.findings.append(
                        SpatialOverlapFinding(
                            sample_a=sample_id_a,
                            split_a=split_a,
                            sample_b=sample_id_b,
                            split_b=split_b,
                            overlap=overlap,
                            distance_m=distance,
                            within_buffer=within_buffer,
                            explanation=(
                                "AOI bounding boxes overlap"
                                if overlap
                                else f"Samples within spatial buffer ({spatial_buffer_m} m)"
                            ),
                        )
                    )
                if distance is not None:
                    distances.append(distance)

        limit = max_allowed if split_b == "test" or split_a == "test" else 0
        if overlap_count > limit:
            result.status = "FAIL"
            result.messages.append(
                f"Spatial overlap count between {split_a}/{split_b} "
                f"({overlap_count}) exceeds limit ({limit})"
            )

    if result.buffered_samples and result.status != "FAIL":
        result.status = "WARNING"
        result.messages.append(
            f"{len(result.buffered_samples)} sample pairs fall within "
            f"spatial buffer ({spatial_buffer_m} m)"
        )

    if distances:
        result.minimum_distance_m = min(distances)
        result.maximum_distance_m = max(distances)

    if not result.overlapping_samples and not result.buffered_samples:
        result.status = "PASS"

    return result
