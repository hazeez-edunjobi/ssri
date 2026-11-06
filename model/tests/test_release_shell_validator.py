"""Upload validator PASS/WARN/FAIL behaviour."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from ssri_model.api.app import create_app
from ssri_model.ml.constants import CHANNEL_NAMES, FEATURE_NODATA
from ssri_model.release_shell.validator import validate_release_shell_dataset
from tests.api_helpers import build_api_config


def _write_tile(root: Path, sid: str, *, all_nodata_spectral: bool = False) -> None:
    d = root / "train" / sid
    d.mkdir(parents=True)
    h, w = 8, 8
    feats = np.zeros((13, h, w), dtype=np.float32)
    feats[0] = 100
    feats[1] = 10
    for i in range(2, 13):
        if all_nodata_spectral and i >= 7:
            feats[i] = FEATURE_NODATA
        else:
            feats[i] = float(i)
    np.save(d / "feature_stack.npy", feats)
    label = np.zeros((h, w), dtype=np.int16)
    label[2:6, 2:6] = 1
    with rasterio.open(
        d / "label.tif",
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="int16",
        crs="EPSG:4326",
        transform=from_origin(-120, 40, 0.001, 0.001),
        nodata=-1,
    ) as ds:
        ds.write(label, 1)
    (d / "metadata.json").write_text(
        json.dumps(
            {
                "centroid_lat": 37.5,
                "centroid_lon": -122.5,
                "synthetic": True,
            }
        ),
        encoding="utf-8",
    )


def test_validator_fails_all_sentinel_channels(tmp_path, monkeypatch):
    monkeypatch.setenv("SSRI_RELEASE_SHELL_MIN_TILES", "1")
    monkeypatch.setenv("SSRI_RELEASE_SHELL_MIN_BLOCKS", "1")
    root = tmp_path / "ds"
    # Need several blocks for split — write 9 tiles; one with bad channels is enough to FAIL channel_quality
    coords = [
        (32.5, -117.5),
        (37.5, -122.5),
        (42.5, -122.5),
        (47.5, -122.5),
        (32.5, -110.5),
        (37.5, -110.5),
        (42.5, -105.5),
        (35.5, -95.5),
        (40.5, -85.5),
    ]
    for i, (lat, lon) in enumerate(coords):
        sid = f"t{i}"
        _write_tile(root, sid, all_nodata_spectral=True)
        meta = json.loads((root / "train" / sid / "metadata.json").read_text(encoding="utf-8"))
        meta["centroid_lat"] = lat
        meta["centroid_lon"] = lon
        (root / "train" / sid / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "splits": {
                    "train": [f"t{i}" for i in range(9)],
                    "validation": [],
                    "test": [],
                },
                "channels": list(CHANNEL_NAMES),
            }
        ),
        encoding="utf-8",
    )
    (root / "statistics.json").write_text("{}", encoding="utf-8")
    report = validate_release_shell_dataset(root)
    channel = next(c for c in report["checks"] if c["name"] == "channel_quality")
    assert channel["status"] == "FAIL"
    assert report["can_train"] is False


# --- Owner input surfaces (flag-gated routes) ---------------------------------


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SSRI_RELEASE_SHELL", "true")
    return TestClient(create_app(build_api_config(tmp_path)))


def test_status_reports_owner_settings(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/v1/release-shell/status")
    assert resp.status_code == 200, resp.text
    settings = resp.json()["settings"]
    assert settings["supported_channel_schemas"] == ["v1", "v2"]
    assert settings["channel_schemas"]["v2"]["channel_count"] == 16
    assert "block_size_deg" in settings
    assert "preview_unevaluated_scores" in settings


def test_layers_validate_route_flags_negative_overburden(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    csv = b"X,Y,Z\n0,0,10\n100,0,-3\n0,100,12\n100,100,-1.5\n"
    resp = client.post(
        "/api/v1/release-shell/layers/validate",
        data={"layer_name": "overburden_thickness", "crs": "EPSG:32631"},
        files={"file": ("SYNTHETIC_overburden.csv", csv, "text/csv")},
    )
    assert resp.status_code == 200, resp.text  # overall WARN (visible), not FAIL
    layer = resp.json()["layer"]
    unit = next(c for c in layer["checks"] if c["name"] == "unit_sanity")
    assert unit["status"] in {"WARN", "FAIL"}
    assert "negative" in unit["message"].lower()
    assert layer["status"] == "FEATURE_LAYER_ONLY"


def test_layers_validate_route_requires_crs(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    csv = b"X,Y,Z\n0,0,10\n100,0,11\n0,100,12\n100,100,13\n"
    resp = client.post(
        "/api/v1/release-shell/layers/validate",
        data={"layer_name": "overburden_thickness", "crs": ""},
        files={"file": ("no_crs.csv", csv, "text/csv")},
    )
    assert resp.status_code == 400, resp.text
    layer = resp.json()["layer"]
    assert layer["overall"] == "FAIL"
    assert layer["checks"][0]["name"] == "crs_declared"


def test_labels_inventory_route(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    csv = b"X,Y,hazard,date\n3.0,7.0,landslide,2024-01-01\n3.1,7.1,subsidence,2024-02-01\n"
    resp = client.post(
        "/api/v1/release-shell/labels/inventory",
        data={"crs": "EPSG:4326"},
        files={"file": ("labels.csv", csv, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    labels = resp.json()["labels"]
    assert labels["n_labels"] == 2
    assert labels["counts_by_hazard"]["landslide"] == 1


def test_lineaments_inspect_route(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    geojson = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[0.0, 0.0], [1.0, 1.0]],
                    },
                }
            ],
        }
    ).encode()
    resp = client.post(
        "/api/v1/release-shell/lineaments/inspect",
        files={"file": ("lines.geojson", geojson, "application/geo+json")},
    )
    assert resp.status_code == 200, resp.text
    lin = resp.json()["lineaments"]
    assert lin["n_segments"] == 1
    assert lin["bbox"]["x_max"] == 1.0
