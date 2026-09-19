"""GeoJSON polygon validation for assessment AOIs."""

from __future__ import annotations

from typing import Any

from ssri_model.service.exceptions import InvalidServiceRequestError

# Soft operational limits (not scientific claims).
MAX_POLYGON_VERTICES = 5_000
MAX_BBOX_AREA_DEG2 = 1.0  # ~ roughly 10_000 km^2 near equator; coarse guardrail


def _ring_area(ring: list[list[float]]) -> float:
    """Shoelace area in degree-space (absolute)."""
    if len(ring) < 4:
        return 0.0
    area = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = float(ring[i][0]), float(ring[i][1])
        x2, y2 = float(ring[i + 1][0]), float(ring[i + 1][1])
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def _validate_position(pos: Any, *, field: str) -> tuple[float, float]:
    if not isinstance(pos, (list, tuple)) or len(pos) < 2:
        raise InvalidServiceRequestError(f"{field} coordinates must be [lon, lat]")
    lon, lat = float(pos[0]), float(pos[1])
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        raise InvalidServiceRequestError(f"{field} coordinates out of range")
    return lon, lat


def _segments_intersect(
    a1: list[float],
    a2: list[float],
    b1: list[float],
    b2: list[float],
) -> bool:
    """Proper intersection of open segments (shared endpoints do not count)."""

    def orient(p: list[float], q: list[float], r: list[float]) -> float:
        return (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])

    def on_segment(p: list[float], q: list[float], r: list[float]) -> bool:
        return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[
            1
        ] <= max(p[1], r[1])

    o1 = orient(a1, a2, b1)
    o2 = orient(a1, a2, b2)
    o3 = orient(b1, b2, a1)
    o4 = orient(b1, b2, a2)
    if o1 == 0 and on_segment(a1, b1, a2):
        return False
    if o2 == 0 and on_segment(a1, b2, a2):
        return False
    if o3 == 0 and on_segment(b1, a1, b2):
        return False
    if o4 == 0 and on_segment(b1, a2, b2):
        return False
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def _ring_self_intersects(ring: list[list[float]]) -> bool:
    """Detect proper self-intersections on a closed ring (excluding consecutive edges)."""
    n = len(ring) - 1  # last equals first
    if n < 4:
        return False
    for i in range(n):
        a1, a2 = ring[i], ring[i + 1]
        for j in range(i + 1, n):
            # Skip adjacent edges and the closing edge pair (0 with n-1).
            if abs(i - j) <= 1 or (i == 0 and j == n - 1):
                continue
            b1, b2 = ring[j], ring[j + 1]
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False


def _validate_ring(ring: Any, *, field: str) -> list[list[float]]:
    if not isinstance(ring, list) or len(ring) < 4:
        raise InvalidServiceRequestError(f"{field} ring must have at least 4 positions")
    normalized: list[list[float]] = []
    for pos in ring:
        lon, lat = _validate_position(pos, field=field)
        normalized.append([lon, lat])
    if normalized[0] != normalized[-1]:
        raise InvalidServiceRequestError(f"{field} ring must be closed")
    if _ring_self_intersects(normalized):
        raise InvalidServiceRequestError(f"{field} ring is self-intersecting")
    if _ring_area(normalized) <= 0.0:
        raise InvalidServiceRequestError(f"{field} ring has zero area")
    return normalized


def validate_polygon_geojson(
    payload: dict[str, Any],
    *,
    max_vertices: int = MAX_POLYGON_VERTICES,
    max_bbox_area_deg2: float = MAX_BBOX_AREA_DEG2,
) -> tuple[float, float, float, float]:
    """Validate a GeoJSON Polygon/MultiPolygon and return WGS84 bbox.

    Returns (min_lon, min_lat, max_lon, max_lat).
    """
    if not isinstance(payload, dict):
        raise InvalidServiceRequestError("polygon_geojson must be an object")
    geom_type = payload.get("type")
    coords = payload.get("coordinates")
    if geom_type not in {"Polygon", "MultiPolygon"}:
        raise InvalidServiceRequestError(
            "polygon_geojson.type must be Polygon or MultiPolygon"
        )
    if coords is None:
        raise InvalidServiceRequestError("polygon_geojson.coordinates is required")

    rings: list[list[list[float]]] = []
    if geom_type == "Polygon":
        if not isinstance(coords, list) or not coords:
            raise InvalidServiceRequestError("Polygon coordinates must be non-empty")
        rings.append(_validate_ring(coords[0], field="Polygon exterior"))
        for idx, hole in enumerate(coords[1:], start=1):
            rings.append(_validate_ring(hole, field=f"Polygon hole[{idx}]"))
    else:
        if not isinstance(coords, list) or not coords:
            raise InvalidServiceRequestError("MultiPolygon coordinates must be non-empty")
        for p_idx, polygon in enumerate(coords):
            if not isinstance(polygon, list) or not polygon:
                raise InvalidServiceRequestError(
                    f"MultiPolygon[{p_idx}] must contain at least an exterior ring"
                )
            rings.append(
                _validate_ring(polygon[0], field=f"MultiPolygon[{p_idx}] exterior")
            )

    vertex_count = sum(len(ring) for ring in rings)
    if vertex_count > max_vertices:
        raise InvalidServiceRequestError(
            f"polygon exceeds max_vertices={max_vertices} (got {vertex_count})"
        )

    lons = [pt[0] for ring in rings for pt in ring]
    lats = [pt[1] for ring in rings for pt in ring]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    bbox_area = abs(max_lon - min_lon) * abs(max_lat - min_lat)
    if bbox_area > max_bbox_area_deg2:
        raise InvalidServiceRequestError(
            f"polygon bbox area {bbox_area:.4f} deg^2 exceeds limit {max_bbox_area_deg2}"
        )
    return min_lon, min_lat, max_lon, max_lat


def point_bbox(longitude: float, latitude: float, *, half_width_deg: float = 0.01) -> tuple[float, float, float, float]:
    """Build a small bbox around a point for feature acquisition."""
    if not (-180.0 <= longitude <= 180.0 and -90.0 <= latitude <= 90.0):
        raise InvalidServiceRequestError("point coordinates out of range")
    if half_width_deg <= 0:
        raise InvalidServiceRequestError("half_width_deg must be positive")
    return (
        max(-180.0, longitude - half_width_deg),
        max(-90.0, latitude - half_width_deg),
        min(180.0, longitude + half_width_deg),
        min(90.0, latitude + half_width_deg),
    )
