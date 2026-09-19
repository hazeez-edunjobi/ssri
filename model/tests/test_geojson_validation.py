"""Polygon GeoJSON validation tests."""

from __future__ import annotations

import pytest

from ssri_model.api.geojson import point_bbox, validate_polygon_geojson
from ssri_model.service.exceptions import InvalidServiceRequestError


def test_valid_polygon() -> None:
    bbox = validate_polygon_geojson(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [3.0, 6.0],
                    [3.1, 6.0],
                    [3.1, 6.1],
                    [3.0, 6.1],
                    [3.0, 6.0],
                ]
            ],
        }
    )
    assert bbox[0] == 3.0
    assert bbox[2] == 3.1


def test_empty_geometry_rejected() -> None:
    with pytest.raises(InvalidServiceRequestError):
        validate_polygon_geojson({"type": "Polygon", "coordinates": []})


def test_wrong_geometry_type_rejected() -> None:
    with pytest.raises(InvalidServiceRequestError):
        validate_polygon_geojson({"type": "Point", "coordinates": [3.0, 6.0]})


def test_unclosed_ring_rejected() -> None:
    with pytest.raises(InvalidServiceRequestError):
        validate_polygon_geojson(
            {
                "type": "Polygon",
                "coordinates": [[[3.0, 6.0], [3.1, 6.0], [3.1, 6.1], [3.0, 6.1]]],
            }
        )


def test_oversized_bbox_rejected() -> None:
    with pytest.raises(InvalidServiceRequestError):
        validate_polygon_geojson(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [0.0, 0.0],
                        [5.0, 0.0],
                        [5.0, 5.0],
                        [0.0, 5.0],
                        [0.0, 0.0],
                    ]
                ],
            }
        )


def test_self_intersecting_polygon_rejected() -> None:
    # Bow-tie / hourglass polygon
    with pytest.raises(InvalidServiceRequestError, match="self-intersecting"):
        validate_polygon_geojson(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [0.0, 0.0],
                        [1.0, 1.0],
                        [0.0, 1.0],
                        [1.0, 0.0],
                        [0.0, 0.0],
                    ]
                ],
            }
        )


def test_point_bbox() -> None:
    bbox = point_bbox(3.38, 6.52, half_width_deg=0.01)
    assert bbox[0] < 3.38 < bbox[2]
    assert bbox[1] < 6.52 < bbox[3]
