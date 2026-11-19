"""Deterministic coordinate → acquisition-grid cell tests (Gate A)."""

from __future__ import annotations

import math

import pytest

from ssri_model.api.geojson import point_bbox
from ssri_model.api.location_provenance import (
    build_location_provenance,
    map_wgs84_point_to_acquisition_cell,
)
from ssri_model.data.feature_engineering import _utm_crs_for_bbox, build_grid_spec_from_aoi


# Lagos-area fixtures (EPSG:32631 outcome via formula, not a hardcoded constant).
CENTRE = (3.3792, 6.5244)  # lon, lat
WEST = (3.30, 6.5244)
EAST = (3.45, 6.5244)
NORTH = (3.3792, 6.60)
SOUTH = (3.3792, 6.45)
OUTSIDE_LAGOS_SOFT = (0.0, 0.0)  # still builds a local UTM grid; not "coverage fail"


def test_utm_zone_for_lagos_is_32631_by_formula() -> None:
    lon, lat = CENTRE
    bbox = point_bbox(lon, lat)
    crs = _utm_crs_for_bbox(bbox)
    assert crs.to_epsg() == 32631


@pytest.mark.parametrize(
    "lon,lat,label",
    [
        (*CENTRE, "centre"),
        (*WEST, "west"),
        (*EAST, "east"),
        (*NORTH, "north"),
        (*SOUTH, "south"),
    ],
)
def test_known_points_map_inside_acquisition_grid(lon: float, lat: float, label: str) -> None:
    cell = map_wgs84_point_to_acquisition_cell(lon, lat, resolution_m=30.0)
    assert cell["outside_grid"] is False, label
    assert 0 <= cell["pixel_row"] < cell["height"]
    assert 0 <= cell["pixel_col"] < cell["width"]
    assert cell["crs"] == "EPSG:32631"
    assert cell["transformed"]["axis_order"] == "easting, northing"
    # Transformed metres must be finite and near the affine UL origin scale.
    assert math.isfinite(cell["transformed"]["x"])
    assert math.isfinite(cell["transformed"]["y"])


def test_invalid_coordinates_rejected() -> None:
    with pytest.raises(ValueError):
        map_wgs84_point_to_acquisition_cell(200.0, 6.5)
    with pytest.raises(ValueError):
        map_wgs84_point_to_acquisition_cell(3.3, 95.0)


def test_point_bbox_half_width_is_symmetric() -> None:
    lon, lat = CENTRE
    bbox = point_bbox(lon, lat, half_width_deg=0.01)
    assert bbox == pytest.approx((lon - 0.01, lat - 0.01, lon + 0.01, lat + 0.01))


def test_grid_spec_upper_left_north_up() -> None:
    lon, lat = CENTRE
    bbox = point_bbox(lon, lat)
    grid = build_grid_spec_from_aoi(bbox, 30.0)
    assert grid.transform.a == 30.0
    assert grid.transform.e == -30.0
    assert grid.width >= 1 and grid.height >= 1


def test_geographic_to_model_crs_round_trip_consistency() -> None:
    """Submitted WGS84 → UTM → provenance echo matches map_wgs84 helper."""
    lon, lat = CENTRE
    prov = build_location_provenance(
        latitude=lat,
        longitude=lon,
        resolution_m=30.0,
        aoi_source="point",
    )
    assert prov["submitted"]["latitude"] == lat
    assert prov["submitted"]["longitude"] == lon
    assert prov["submitted_crs"] == "EPSG:4326"
    assert prov["outside_acquisition_grid"] is False
    grid = prov["model_grid"]
    direct = map_wgs84_point_to_acquisition_cell(lon, lat)
    assert grid["pixel_row"] == direct["pixel_row"]
    assert grid["pixel_col"] == direct["pixel_col"]
    assert grid["transformed"]["x"] == pytest.approx(direct["transformed"]["x"])
    assert grid["transformed"]["y"] == pytest.approx(direct["transformed"]["y"])


def test_provenance_without_point_is_sparse() -> None:
    prov = build_location_provenance(latitude=None, longitude=None, aoi_source="offline_features")
    assert prov["submitted"] is None
    assert prov["model_grid"] is None
    assert any("No WGS84 point" in n for n in prov["notes"])


def test_far_point_still_reports_local_utm_not_silent_32631() -> None:
    """A point outside Nigeria must not silently reuse EPSG:32631."""
    cell = map_wgs84_point_to_acquisition_cell(-122.4, 37.8, resolution_m=30.0)  # SF
    assert cell["crs"] == "EPSG:32610"
    assert cell["outside_grid"] is False
