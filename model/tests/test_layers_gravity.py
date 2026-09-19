"""Tests for read-only gravity map layer endpoint."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from ssri_model.api.app import create_app
from ssri_model.api.config import APIConfig


def _write_gravity_tif(path: Path) -> None:
    data = np.array(
        [
            [120.0, 130.0, 140.0],
            [125.0, 135.0, 145.0],
            [128.0, 138.0, -9999.0],
        ],
        dtype=np.float32,
    )
    transform = from_origin(3.0, 7.0, 0.1, 0.1)
    profile = {
        "driver": "GTiff",
        "height": data.shape[0],
        "width": data.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": transform,
        "nodata": -9999.0,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(data, 1)


@pytest.fixture
def gravity_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    geotiff = tmp_path / "lagos_gravity_wgm2012_bouguer.tif"
    _write_gravity_tif(geotiff)
    monkeypatch.setenv("GRAVITY_DATA_PATH", str(geotiff))
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "development")
    monkeypatch.setenv("SSRI_AUTH_ENABLED", "false")
    app = create_app(APIConfig.from_env())
    return TestClient(app)


def test_gravity_layer_returns_geojson_with_provenance(
    gravity_client: TestClient,
) -> None:
    response = gravity_client.get("/api/v1/layers/gravity")
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) >= 1
    assert body["metadata"]["dataset"] == "WGM2012 Complete Spherical Bouguer anomaly"
    assert "eigen6c4" not in body["metadata"]["dataset"].lower()
    assert body["metadata"]["units"] == "mGal"
    assert body["metadata"]["crs"] == "EPSG:4326"
    first = body["features"][0]
    assert first["geometry"]["type"] == "Polygon"
    assert "value" in first["properties"]
    # Coordinates must be lon/lat in Lagos-ish range for fixture.
    ring = first["geometry"]["coordinates"][0]
    assert 2.0 < ring[0][0] < 5.0
    assert 5.0 < ring[0][1] < 8.0


def test_gravity_layer_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRAVITY_DATA_PATH", "/no/such/gravity.tif")
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "development")
    monkeypatch.setenv("SSRI_AUTH_ENABLED", "false")
    app = create_app(APIConfig.from_env())
    client = TestClient(app)
    response = client.get("/api/v1/layers/gravity")
    assert response.status_code == 404
