"""Traceable coordinate provenance for assessment requests.

Map clicks are WGS84 (EPSG:4326) named latitude/longitude. Live acquisition
builds a UTM metre grid from the point bbox; this module records the submitted
point, the acquisition bbox, the derived grid CRS, and the pixel index of the
query point when a grid can be computed without fabricating values.
"""

from __future__ import annotations

from typing import Any

from ssri_model.api.geojson import point_bbox


SUBMITTED_CRS = "EPSG:4326"


def build_location_provenance(
    *,
    latitude: float | None,
    longitude: float | None,
    resolution_m: float = 30.0,
    half_width_deg: float = 0.01,
    aoi_source: str | None = None,
    acquisition_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a client-safe provenance record for an assessment location.

    Does not invent coordinates. When no point is provided, returns a sparse
    record stating that feature sampling was not driven by a map point.
    """
    record: dict[str, Any] = {
        "submitted_crs": SUBMITTED_CRS,
        "submitted_axis_order": "latitude, longitude (named fields); GeoJSON uses lon, lat",
        "aoi_source": aoi_source,
        "submitted": None,
        "acquisition_bbox_wgs84": None,
        "model_grid": None,
        "outside_acquisition_grid": None,
        "notes": [],
    }
    if latitude is None or longitude is None:
        record["notes"].append(
            "No WGS84 point was submitted; location provenance is limited to the AOI source."
        )
        if acquisition_meta and acquisition_meta.get("bbox") is not None:
            record["acquisition_bbox_wgs84"] = list(acquisition_meta["bbox"])
        return record

    record["submitted"] = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "crs": SUBMITTED_CRS,
    }
    bbox = point_bbox(float(longitude), float(latitude), half_width_deg=half_width_deg)
    record["acquisition_bbox_wgs84"] = list(bbox)

    if acquisition_meta and acquisition_meta.get("bbox") is not None:
        record["acquisition_bbox_wgs84"] = list(acquisition_meta["bbox"])

    try:
        grid_info = map_wgs84_point_to_acquisition_cell(
            float(longitude),
            float(latitude),
            resolution_m=float(resolution_m),
            half_width_deg=float(half_width_deg),
        )
        record["model_grid"] = grid_info
        record["outside_acquisition_grid"] = bool(grid_info.get("outside_grid"))
        if grid_info.get("outside_grid"):
            record["notes"].append(
                "Submitted point falls outside the derived acquisition grid after UTM snap."
            )
    except Exception as exc:  # noqa: BLE001 — provenance must never fail assess
        record["notes"].append(
            f"Model grid cell could not be computed for this request ({type(exc).__name__})."
        )
    return record


def map_wgs84_point_to_acquisition_cell(
    longitude: float,
    latitude: float,
    *,
    resolution_m: float = 30.0,
    half_width_deg: float = 0.01,
) -> dict[str, Any]:
    """Map a WGS84 point to the live-acquisition UTM grid cell for its point bbox.

    Pixel convention matches ``build_grid_spec_from_aoi``: Affine upper-left
    origin, north-up, ``rowcol`` with round-to-nearest centre.
    """
    from rasterio.transform import rowcol
    from rasterio.warp import transform as rio_transform

    from ssri_model.data.feature_engineering import build_grid_spec_from_aoi

    if not (-180.0 <= longitude <= 180.0 and -90.0 <= latitude <= 90.0):
        raise ValueError("point coordinates out of range")
    if resolution_m <= 0:
        raise ValueError("resolution_m must be greater than zero")

    bbox = point_bbox(longitude, latitude, half_width_deg=half_width_deg)
    grid = build_grid_spec_from_aoi(bbox, resolution_m)
    xs, ys = rio_transform("EPSG:4326", grid.crs, [longitude], [latitude])
    easting, northing = float(xs[0]), float(ys[0])
    row, col = rowcol(grid.transform, easting, northing, op=round)
    outside = row < 0 or col < 0 or row >= grid.height or col >= grid.width
    crs_str = grid.crs.to_string() if grid.crs is not None else None
    return {
        "crs": crs_str,
        "resolution_m": float(resolution_m),
        "width": int(grid.width),
        "height": int(grid.height),
        "transform": [
            float(grid.transform.a),
            float(grid.transform.b),
            float(grid.transform.c),
            float(grid.transform.d),
            float(grid.transform.e),
            float(grid.transform.f),
        ],
        "pixel_origin": "upper_left",
        "pixel_indexing": "rowcol_round_to_nearest",
        "transformed": {
            "x": easting,
            "y": northing,
            "crs": crs_str,
            "axis_order": "easting, northing",
        },
        "pixel_row": int(row),
        "pixel_col": int(col),
        "outside_grid": bool(outside),
        "acquisition_bbox_wgs84": list(bbox),
    }
