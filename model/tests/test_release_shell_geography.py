"""Release-shell geography: CRS conversion + training-region contract (flag ON).

Covers the Task-3 map/coordinate guarantees:

* map clicks arrive as WGS84 lat/lon; projected-CRS conversion happens here with
  pyproj (never guessed in the browser);
* round trips match to 6 decimals for points in every quadrant;
* ``outside_training_region`` mirrors the assess gate exactly;
* a checkpoint with no declared CRS is reported as ``crs_declared: false`` so the
  UI can block the assessment with a clear message.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyproj import Transformer

from ssri_model.api.app import create_app
from ssri_model.release_shell.geography import (
    convert_point,
    describe_checkpoint_geography,
)
from tests.api_helpers import build_api_config

# Known points in four quadrants: (lat, lon, label).
QUADRANT_POINTS = [
    (7.16, 3.35, "Abeokuta (NE)"),
    (-33.92, 18.42, "Cape Town (SW)"),
    (40.71, -74.01, "New York (NW)"),
    (-23.70, 133.88, "Alice Springs (SE)"),
]

REGION = {
    "blocks": ["7.0,3.0"],
    "extent": {"lat_min": 7.0, "lat_max": 7.3, "lon_min": 3.2, "lon_max": 3.5},
    "n_tiles": 3,
}


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SSRI_RELEASE_SHELL", "true")
    return TestClient(create_app(build_api_config(tmp_path)))


def _checkpoint_with_meta(tmp_path: Path, meta: dict) -> Path:
    ckpt = tmp_path / "ckpt"
    ckpt.mkdir(parents=True, exist_ok=True)
    path = ckpt / "best.pt"
    path.write_bytes(b"not-a-real-checkpoint")
    (ckpt / "release_shell_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return path


def _shell_meta(crs: str | None) -> dict:
    return {
        "schema": "ssri_release_shell_meta_v1",
        "seeds": [42, 43, 44],
        "training_region": REGION,
        "crs": crs,
        "hazards": {},
        "scientific_validation_status": "NOT_VALIDATED",
    }


# --- pure helpers ----------------------------------------------------------


def test_convert_point_geographic_is_identity():
    out = convert_point(7.16, 3.35, "EPSG:4326")
    assert out["x"] == pytest.approx(3.35, abs=1e-9)
    assert out["y"] == pytest.approx(7.16, abs=1e-9)
    assert out["axis_order"] == "x=longitude, y=latitude"


@pytest.mark.parametrize("lat,lon,label", QUADRANT_POINTS)
def test_geographic_round_trip_6dp(lat, lon, label):
    out = convert_point(lat, lon, "EPSG:4326")
    assert round(out["y"], 6) == round(lat, 6), label
    assert round(out["x"], 6) == round(lon, 6), label


def test_projected_conversion_and_round_trip_6dp():
    """Abeokuta → UTM 31N → back must match to 6 decimals (backend, pyproj)."""
    lat, lon = 7.16, 3.35
    projected = convert_point(lat, lon, "EPSG:32631")
    assert projected["axis_order"] == "x=easting, y=northing"
    # UTM easting/northing for Abeokuta are large metre values (not degrees).
    assert projected["x"] > 100_000
    assert projected["y"] > 100_000

    back = Transformer.from_crs("EPSG:32631", "EPSG:4326", always_xy=True)
    lon_back, lat_back = back.transform(projected["x"], projected["y"])
    assert round(lat_back, 6) == round(lat, 6)
    assert round(lon_back, 6) == round(lon, 6)


def test_convert_point_invalid_crs_is_plain_language():
    with pytest.raises(ValueError) as exc:
        convert_point(7.16, 3.35, "NOT-A-CRS")
    message = str(exc.value)
    assert "Could not understand CRS" in message
    assert "EPSG:4326" in message


def test_describe_region_inside_and_outside(tmp_path):
    ckpt = _checkpoint_with_meta(tmp_path, _shell_meta("EPSG:4326"))
    inside = describe_checkpoint_geography(ckpt, latitude=7.15, longitude=3.35)
    assert inside["inside_training_region"] is True
    assert inside["outside_training_region"] is False

    far = describe_checkpoint_geography(ckpt, latitude=51.5, longitude=-0.12)
    assert far["inside_training_region"] is False
    assert far["outside_training_region"] is True


def test_describe_no_crs_reports_not_declared(tmp_path):
    ckpt = _checkpoint_with_meta(tmp_path, _shell_meta(None))
    out = describe_checkpoint_geography(ckpt, latitude=7.16, longitude=3.35)
    assert out["crs_declared"] is False
    assert out["crs"] is None
    assert out["point_converted"] is None


# --- HTTP contract ---------------------------------------------------------


def test_geography_flag_off_returns_403(tmp_path, monkeypatch):
    monkeypatch.setenv("SSRI_RELEASE_SHELL", "false")
    client = TestClient(create_app(build_api_config(tmp_path)))
    resp = client.post("/api/v1/release-shell/geography", json={"checkpoint": "x"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "RELEASE_SHELL_DISABLED"


def test_geography_endpoint_returns_crs_region_and_converted_point(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    path = _checkpoint_with_meta(tmp_path, _shell_meta("EPSG:32631"))
    resp = client.post(
        "/api/v1/release-shell/geography",
        json={
            "checkpoint": str(path),
            "point": {"latitude": 7.16, "longitude": 3.35},
        },
    )
    assert resp.status_code == 200, resp.text
    geo = resp.json()["geography"]
    assert geo["crs"] == "EPSG:32631"
    assert geo["crs_declared"] is True
    assert geo["region_extent"] == REGION["extent"]
    assert geo["point_geographic"] == {"latitude": 7.16, "longitude": 3.35}
    assert geo["point_converted"]["crs"] == "EPSG:32631"
    assert geo["inside_training_region"] is True
    assert geo["outside_training_region"] is False


def test_geography_endpoint_outside_region_matches_gate(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    path = _checkpoint_with_meta(tmp_path, _shell_meta("EPSG:4326"))
    resp = client.post(
        "/api/v1/release-shell/geography",
        json={
            "checkpoint": str(path),
            "point": {"latitude": 51.5, "longitude": -0.12},
        },
    )
    assert resp.status_code == 200, resp.text
    geo = resp.json()["geography"]
    assert geo["outside_training_region"] is True
    assert geo["inside_training_region"] is False


def test_geography_endpoint_no_crs_declared(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    path = _checkpoint_with_meta(tmp_path, _shell_meta(None))
    resp = client.post(
        "/api/v1/release-shell/geography", json={"checkpoint": str(path)}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["geography"]["crs_declared"] is False


def test_geography_endpoint_missing_checkpoint_404(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post(
        "/api/v1/release-shell/geography", json={"checkpoint": str(tmp_path / "nope.pt")}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CHECKPOINT_NOT_FOUND"


def test_geography_endpoint_rejects_path_traversal(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post(
        "/api/v1/release-shell/geography", json={"checkpoint": "../../etc/passwd"}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_CHECKPOINT_PATH"


def test_geography_endpoint_rejects_bad_point_type(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    path = _checkpoint_with_meta(tmp_path, _shell_meta("EPSG:4326"))
    resp = client.post(
        "/api/v1/release-shell/geography",
        json={"checkpoint": str(path), "point": {"latitude": "abc", "longitude": 3.35}},
    )
    assert resp.status_code == 422
