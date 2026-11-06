"""Checkpoint geography: declared CRS, training region, and point conversion.

Map clicks always arrive as WGS84 latitude/longitude (the browser map is
Web Mercator). When a checkpoint declares a *projected* CRS, the conversion to
that CRS must happen here with pyproj — never guessed in the browser.

Read-only helpers used by the release shell; no training, no side effects.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pyproj import CRS, Transformer

from ssri_model.release_shell.meta import load_shell_meta, point_in_training_region

GEOGRAPHIC_CRS = "EPSG:4326"


def parse_crs(crs: str) -> CRS:
    """Parse an operator-supplied CRS string, with a plain-language error."""
    try:
        return CRS.from_user_input(crs)
    except Exception as exc:  # noqa: BLE001 — surface as a readable message
        raise ValueError(
            f"Could not understand CRS '{crs}'. Use an authority code such as "
            "EPSG:4326 or EPSG:32631."
        ) from exc


def convert_point(
    latitude: float,
    longitude: float,
    crs: str,
) -> dict[str, Any]:
    """Convert a WGS84 lat/lon to ``crs``. Geographic CRS returns lon/lat as-is.

    Returns ``{"x", "y", "crs", "axis_order"}``. ``x``/``y`` follow the CRS
    authority axis order in a normalised "x=easting/longitude, y=northing/latitude"
    convention so the UI can always label them the same way.
    """
    target = parse_crs(crs)
    if target.is_geographic:
        return {
            "x": float(longitude),
            "y": float(latitude),
            "crs": crs,
            "axis_order": "x=longitude, y=latitude",
        }
    transformer = Transformer.from_crs(GEOGRAPHIC_CRS, target, always_xy=True)
    x, y = transformer.transform(float(longitude), float(latitude))
    return {
        "x": float(x),
        "y": float(y),
        "crs": crs,
        "axis_order": "x=easting, y=northing",
    }


def describe_checkpoint_geography(
    checkpoint_path: Path | str,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, Any]:
    """Describe a checkpoint's declared CRS + training region (read-only).

    When ``latitude``/``longitude`` are supplied (a WGS84 map click) the point is
    echoed as geographic coordinates and, if the checkpoint declares a projected
    CRS, additionally converted on this side with pyproj. ``outside_training_region``
    mirrors the assess gate exactly: it is true only when a region is stored AND
    the point falls outside it.
    """
    path = Path(checkpoint_path)
    meta = load_shell_meta(path)
    raw_crs = meta.get("crs") if isinstance(meta, dict) else None
    crs_declared = bool(raw_crs)
    crs = str(raw_crs) if crs_declared else None
    region = (meta or {}).get("training_region")

    out: dict[str, Any] = {
        "checkpoint": str(path),
        "has_release_shell_meta": meta is not None,
        "crs": crs,
        "crs_declared": crs_declared,
        "training_region": region,
        "region_extent": (region or {}).get("extent") if isinstance(region, dict) else None,
    }

    if latitude is not None and longitude is not None:
        out["point_geographic"] = {
            "latitude": float(latitude),
            "longitude": float(longitude),
        }
        if crs_declared:
            try:
                out["point_converted"] = convert_point(latitude, longitude, crs or "")
            except ValueError as exc:
                out["point_converted"] = None
                out["conversion_error"] = str(exc)
        else:
            out["point_converted"] = None
        if region:
            inside = point_in_training_region(float(latitude), float(longitude), region)
            out["inside_training_region"] = inside
            out["outside_training_region"] = not inside
        else:
            out["inside_training_region"] = None
            out["outside_training_region"] = False

    return out
