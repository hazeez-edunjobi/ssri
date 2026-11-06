"""Derive lineament_density and lineament_distance from vector lines.

Method (documented):
- Input: GeoJSON LineString/MultiLineString (EPSG declared separately).
- Window: square window of ``window_m`` metres (default 500 m) centred on each
  grid cell for density = total line length inside window / window area (m/m²).
- Distance: Euclidean distance (metres) from cell centre to nearest line
  vertex-segment in the working CRS (projected metres assumed).

A precomputed raster may be supplied instead; this module only builds from vectors.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from ssri_model.ml.constants import FEATURE_NODATA

DEFAULT_WINDOW_M = 500.0


@dataclass(frozen=True)
class LineamentMethod:
    window_m: float = DEFAULT_WINDOW_M
    density_units: str = "m_per_m2"
    distance_units: str = "m"
    notes: str = (
        "Density = sum of segment lengths intersecting a square window / window area. "
        "Distance = minimum distance from cell centre to any segment."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_m": self.window_m,
            "density_units": self.density_units,
            "distance_units": self.distance_units,
            "notes": self.notes,
        }


def _segments_from_geojson(payload: dict) -> list[tuple[float, float, float, float]]:
    segs: list[tuple[float, float, float, float]] = []

    def add_coords(coords: Sequence[Sequence[float]]) -> None:
        for i in range(len(coords) - 1):
            x1, y1 = float(coords[i][0]), float(coords[i][1])
            x2, y2 = float(coords[i + 1][0]), float(coords[i + 1][1])
            segs.append((x1, y1, x2, y2))

    def handle_geom(geom: dict) -> None:
        if not geom:
            return
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if gtype == "LineString" and coords:
            add_coords(coords)
        elif gtype == "MultiLineString" and coords:
            for part in coords:
                add_coords(part)
        elif gtype == "GeometryCollection":
            for g in geom.get("geometries") or []:
                handle_geom(g)

    if payload.get("type") == "FeatureCollection":
        for feat in payload.get("features") or []:
            handle_geom(feat.get("geometry") or {})
    elif payload.get("type") == "Feature":
        handle_geom(payload.get("geometry") or {})
    else:
        handle_geom(payload)
    return segs


def load_lineament_segments(path_or_bytes: Path | bytes | str | dict) -> list[tuple[float, float, float, float]]:
    if isinstance(path_or_bytes, dict):
        return _segments_from_geojson(path_or_bytes)
    if isinstance(path_or_bytes, bytes):
        return _segments_from_geojson(json.loads(path_or_bytes.decode("utf-8")))
    path = Path(path_or_bytes)
    return _segments_from_geojson(json.loads(path.read_text(encoding="utf-8")))


def _point_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _segment_length_in_window(
    x1: float, y1: float, x2: float, y2: float, xmin: float, xmax: float, ymin: float, ymax: float
) -> float:
    """Approximate length of segment clipped to axis-aligned window (Liang-Barsky)."""
    dx, dy = x2 - x1, y2 - y1
    p = [-dx, dx, -dy, dy]
    q = [x1 - xmin, xmax - x1, y1 - ymin, ymax - y1]
    u1, u2 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:
                return 0.0
            continue
        t = qi / pi
        if pi < 0:
            u1 = max(u1, t)
        else:
            u2 = min(u2, t)
        if u1 > u2:
            return 0.0
    cx1, cy1 = x1 + u1 * dx, y1 + u1 * dy
    cx2, cy2 = x1 + u2 * dx, y1 + u2 * dy
    return math.hypot(cx2 - cx1, cy2 - cy1)


def derive_lineament_rasters(
    xs: Sequence[float],
    ys: Sequence[float],
    segments: Sequence[tuple[float, float, float, float]],
    *,
    window_m: float = DEFAULT_WINDOW_M,
) -> tuple[np.ndarray, np.ndarray, LineamentMethod]:
    """Return (density, distance) arrays shaped (len(ys), len(xs)), north-up."""
    method = LineamentMethod(window_m=window_m)
    height, width = len(ys), len(xs)
    density = np.full((height, width), FEATURE_NODATA, dtype=np.float64)
    distance = np.full((height, width), FEATURE_NODATA, dtype=np.float64)
    if not segments:
        return density, distance, method

    half = window_m / 2.0
    area = window_m * window_m
    north = list(reversed(list(ys)))
    for r, y in enumerate(north):
        for c, x in enumerate(xs):
            xmin, xmax = x - half, x + half
            ymin, ymax = y - half, y + half
            length = 0.0
            best = float("inf")
            for x1, y1, x2, y2 in segments:
                length += _segment_length_in_window(x1, y1, x2, y2, xmin, xmax, ymin, ymax)
                best = min(best, _point_segment_distance(x, y, x1, y1, x2, y2))
            density[r, c] = length / area if area > 0 else FEATURE_NODATA
            distance[r, c] = best if best < float("inf") else FEATURE_NODATA
    return density, distance, method
