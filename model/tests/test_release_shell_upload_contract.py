"""UI ⇄ backend upload contract tests for the release-shell (flag ON).

These tests mirror the exact request the Next.js shell client makes in
``frontend/lib/api.ts`` so a field-name or type drift fails here rather than in
the browser. Route ↔ UI-function mapping:

| UI function (frontend/lib/api.ts)   | method + route                                   | payload                              |
|--------------------------------------|--------------------------------------------------|--------------------------------------|
| ``getShellStatusFull``               | GET  /api/v1/release-shell/status                | —                                    |
| ``createTrainingDataset``            | POST /api/v1/training/datasets                   | JSON name/notes/hazard_notes         |
| ``uploadShellDatasetZip``            | POST /api/v1/release-shell/datasets/{id}/upload  | multipart ``file``                   |
| ``validateShellDataset``             | POST /api/v1/release-shell/datasets/{id}/validate| —                                    |
| ``startShellTrainingJob``            | POST /api/v1/release-shell/jobs                   | JSON dataset_id/epochs/seeds/device  |
| ``validateShellLayer``               | POST /api/v1/release-shell/layers/validate       | multipart file/layer_name/crs/[working_crs] |
| ``uploadShellLabelInventory``        | POST /api/v1/release-shell/labels/inventory      | multipart file/crs                   |
| ``inspectShellLineaments``           | POST /api/v1/release-shell/lineaments/inspect    | multipart file                       |

Every error body must be plain language (``error.message``), never a stack trace.
"""

from __future__ import annotations

import io
import json
import zipfile

import numpy as np
from fastapi.testclient import TestClient
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from ssri_model.api.app import create_app
from ssri_model.ml.constants import CHANNEL_NAMES
from tests.api_helpers import build_api_config

BLOCK_CENTERS = [
    (32.5, -117.5),
    (37.5, -122.5),
    (42.5, -122.5),
    (47.5, -122.5),
    (32.5, -110.5),
    (37.5, -110.5),
    (42.5, -105.5),
    (35.5, -95.5),
]


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SSRI_RELEASE_SHELL", "true")
    return TestClient(create_app(build_api_config(tmp_path)))


def _new_dataset(client: TestClient, name: str = "contract") -> str:
    created = client.post(
        "/api/v1/training/datasets",
        json={"name": name, "notes": "release-shell contract test"},
    )
    assert created.status_code in {200, 201}, created.text
    return created.json()["dataset"]["dataset_id"]


def _label_tif_bytes(lat: float, lon: float, *, h: int = 8, w: int = 8) -> bytes:
    label = np.full((h, w), -1, dtype=np.int16)
    with MemoryFile() as mem:
        with mem.open(
            driver="GTiff",
            height=h,
            width=w,
            count=1,
            dtype="int16",
            crs="EPSG:4326",
            transform=from_origin(lon - 0.01, lat + 0.01, 0.0025, 0.0025),
            nodata=-1,
        ) as ds:
            ds.write(label, 1)
        return mem.read()


def _dataset_zip(*, channels: int = 13, manifest: dict | None = None) -> bytes:
    """Zip whose feature stacks have ``channels`` bands (13 = schema v1)."""
    buf = io.BytesIO()
    ids: list[str] = []
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, (lat, lon) in enumerate(BLOCK_CENTERS):
            sid = f"t{i:02d}"
            ids.append(sid)
            rng = np.random.default_rng(1000 + i)
            feats = rng.normal(0.0, 1.0, size=(channels, 8, 8)).astype(np.float32)
            npy = io.BytesIO()
            np.save(npy, feats)
            zf.writestr(f"train/{sid}/feature_stack.npy", npy.getvalue())
            zf.writestr(f"train/{sid}/label.tif", _label_tif_bytes(lat, lon))
            zf.writestr(
                f"train/{sid}/metadata.json",
                json.dumps({"centroid_lat": lat, "centroid_lon": lon, "sample_id": sid}),
            )
        man = manifest if manifest is not None else {
            "channel_names": list(CHANNEL_NAMES),
            "channels": list(CHANNEL_NAMES),
            "splits": {"train": ids, "validation": [], "test": []},
        }
        zf.writestr("manifest.json", json.dumps(man))
        zf.writestr("statistics.json", "{}")
    return buf.getvalue()


# --- status contract (drives the whole shell UI) ------------------------------


def test_status_field_names_and_types_match_ui(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/v1/release-shell/status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["release_shell_enabled"], bool)
    assert isinstance(body["limitations"], list)

    s = body["settings"]
    # Fields the shell page reads directly (app/shell/page.tsx).
    assert isinstance(s["block_size_deg"], (int, float)) or s["block_size_deg"] is None
    assert isinstance(s["default_block_size_deg"], (int, float))
    assert isinstance(s["buffer_km"], (int, float))
    for key in ("tiles_per_hazard", "blocks", "held_out_blocks"):
        assert isinstance(s["minimums"][key], int)
    assert isinstance(s["preview_unevaluated_scores"], bool)
    assert s["supported_channel_schemas"] == ["v1", "v2"]
    assert s["default_channel_schema"] == "v1"
    assert s["channel_schemas"]["v1"]["channel_count"] == 13
    assert s["channel_schemas"]["v2"]["channel_count"] == 16
    assert isinstance(s["channel_schemas"]["v2"]["channel_names"], list)
    # Hazard registry (name/class_id/enabled_by_default), used by every surface.
    for hazard in s["hazards"]:
        assert set(hazard) >= {"name", "class_id", "enabled_by_default"}
        assert isinstance(hazard["class_id"], int)
        assert isinstance(hazard["enabled_by_default"], bool)


# --- ZIP upload ---------------------------------------------------------------


def test_zip_upload_success(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    ds = _new_dataset(client)
    raw = _dataset_zip()
    resp = client.post(
        f"/api/v1/release-shell/datasets/{ds}/upload",
        files={"file": ("dataset.zip", raw, "application/zip")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dataset_id"] == ds
    assert body["uploaded"] is True
    assert body["bytes"] == len(raw)


def test_zip_upload_rejects_non_zip(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    ds = _new_dataset(client)
    resp = client.post(
        f"/api/v1/release-shell/datasets/{ds}/upload",
        files={"file": ("dataset.zip", b"this is not a zip", "application/zip")},
    )
    assert resp.status_code == 400, resp.text
    err = resp.json()["error"]
    assert err["code"] == "INVALID_ZIP"
    # Plain language, no traceback.
    assert "zip" in err["message"].lower()
    assert "Traceback" not in err["message"]


def test_zip_upload_rejects_unsupported_type(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    ds = _new_dataset(client)
    resp = client.post(
        f"/api/v1/release-shell/datasets/{ds}/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400, resp.text
    err = resp.json()["error"]
    assert err["code"] == "UNSUPPORTED_UPLOAD"
    assert ".zip" in err["message"]


def test_zip_upload_oversize_returns_413(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("SSRI_UPLOAD_MAX_BYTES", "64")
    ds = _new_dataset(client)
    raw = _dataset_zip()
    assert len(raw) > 64
    resp = client.post(
        f"/api/v1/release-shell/datasets/{ds}/upload",
        files={"file": ("big.zip", raw, "application/zip")},
    )
    assert resp.status_code == 413, resp.text
    err = resp.json()["error"]
    assert err["code"] == "UPLOAD_TOO_LARGE"
    assert "maximum upload size" in err["message"].lower()


def test_zip_upload_malformed_manifest_is_not_a_500(tmp_path, monkeypatch):
    """A malformed manifest (non-list ``channels``, non-dict ``channel_schema``)
    must degrade to a reportable result, never an unhandled server error."""
    client = _client(tmp_path, monkeypatch)
    ds = _new_dataset(client)
    raw = _dataset_zip(manifest={"channels": 13, "channel_schema": "v1"})
    up = client.post(
        f"/api/v1/release-shell/datasets/{ds}/upload",
        files={"file": ("malformed.zip", raw, "application/zip")},
    )
    assert up.status_code == 200, up.text
    val = client.post(f"/api/v1/release-shell/datasets/{ds}/validate")
    assert val.status_code == 200, val.text
    assert "overall" in val.json()["validation"]


def test_validate_then_train_refuses_on_schema_fail(tmp_path, monkeypatch):
    """Schema-mismatch ZIP: /validate FAILs and /jobs refuses with plain language."""
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("SSRI_RELEASE_SHELL_MIN_TILES", "1")
    monkeypatch.setenv("SSRI_RELEASE_SHELL_MIN_BLOCKS", "1")
    monkeypatch.setenv("SSRI_RELEASE_SHELL_MIN_HELD_OUT", "1")
    monkeypatch.setenv("SSRI_RELEASE_SHELL_BUFFER_KM", "0")
    ds = _new_dataset(client)
    raw = _dataset_zip(channels=5)  # schema v1 expects 13 channels
    up = client.post(
        f"/api/v1/release-shell/datasets/{ds}/upload",
        files={"file": ("bad_schema.zip", raw, "application/zip")},
    )
    assert up.status_code == 200, up.text

    val = client.post(f"/api/v1/release-shell/datasets/{ds}/validate")
    assert val.status_code == 200, val.text
    report = val.json()["validation"]
    shapes = next(c for c in report["checks"] if c["name"] == "schema_shapes")
    assert shapes["status"] == "FAIL"
    assert report["can_train"] is False

    # UI body exactly as startShellTrainingJob builds it.
    refused = client.post(
        "/api/v1/release-shell/jobs",
        json={"dataset_id": ds, "epochs": 3, "seeds": [42, 43, 44], "device": "cpu"},
    )
    assert refused.status_code == 400, refused.text
    err = refused.json()["error"]
    assert err["code"] == "VALIDATION_FAILED"
    assert err["message"].startswith("Training refused:")
    assert "Traceback" not in err["message"]


def test_jobs_body_type_contract(tmp_path, monkeypatch):
    """The exact UI field set is accepted; a wrong type is rejected (422)."""
    client = _client(tmp_path, monkeypatch)
    # Wrong type for epochs proves the request model is enforced.
    bad = client.post(
        "/api/v1/release-shell/jobs",
        json={"dataset_id": "x", "epochs": "three", "seeds": [42], "device": "cpu"},
    )
    assert bad.status_code == 422, bad.text
    # Wrong device enum is rejected too.
    bad_device = client.post(
        "/api/v1/release-shell/jobs",
        json={"dataset_id": "x", "epochs": 1, "seeds": [42], "device": "tpu"},
    )
    assert bad_device.status_code == 422, bad_device.text


def test_release_shell_disabled_when_flag_off(tmp_path, monkeypatch):
    """Flag OFF keeps flag-off behaviour: the shell routes refuse with a message."""
    monkeypatch.delenv("SSRI_RELEASE_SHELL", raising=False)
    client = TestClient(create_app(build_api_config(tmp_path)))
    # uploading to a shell route must be refused, not silently accepted
    resp = client.post(
        "/api/v1/release-shell/datasets/whatever/upload",
        files={"file": ("dataset.zip", _dataset_zip(), "application/zip")},
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "RELEASE_SHELL_DISABLED"


# --- point-grid CSV layer (headed/headerless, delimiters, CRS) ----------------


def _layer_post(
    client: TestClient,
    csv: bytes,
    *,
    crs: str,
    name: str = "overburden_thickness",
    filename: str = "layer.csv",
    working_crs: str | None = None,
    measurement_type: str | None = "thickness",
    units: str | None = "m",
):
    data = {"layer_name": name, "crs": crs}
    if working_crs is not None:
        data["working_crs"] = working_crs
    if measurement_type is not None:
        data["measurement_type"] = measurement_type
    if units is not None:
        data["units"] = units
    return client.post(
        "/api/v1/release-shell/layers/validate",
        data=data,
        files={"file": (filename, csv, "text/csv")},
    )


def test_layer_headed_comma_csv(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    csv = b"X,Y,Z\n0,0,10\n100,0,11\n0,100,12\n100,100,13\n"
    resp = _layer_post(client, csv, crs="EPSG:32631")
    assert resp.status_code == 200, resp.text
    layer = resp.json()["layer"]
    assert layer["overall"] == "PASS"
    assert layer["status"] == "FEATURE_LAYER_ONLY"
    assert layer["trainable"] is False


def test_layer_headerless_comma_csv(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    csv = b"0,0,10\n100,0,11\n0,100,12\n100,100,13\n"
    resp = _layer_post(client, csv, crs="EPSG:32631")
    assert resp.status_code == 200, resp.text
    assert resp.json()["layer"]["overall"] == "PASS"


def test_layer_tab_delimited_csv(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    csv = b"X\tY\tZ\n0\t0\t10\n100\t0\t11\n0\t100\t12\n100\t100\t13\n"
    resp = _layer_post(client, csv, crs="EPSG:32631")
    assert resp.status_code == 200, resp.text
    assert resp.json()["layer"]["overall"] == "PASS"


def test_layer_space_delimited_headerless_csv(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    csv = b"0 0 10\n100 0 11\n0 100 12\n100 100 13\n"
    resp = _layer_post(client, csv, crs="EPSG:32631")
    assert resp.status_code == 200, resp.text
    assert resp.json()["layer"]["overall"] == "PASS"


def test_layer_requires_crs(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    csv = b"X,Y,Z\n0,0,10\n100,0,11\n0,100,12\n100,100,13\n"
    resp = _layer_post(client, csv, crs="")
    assert resp.status_code == 400, resp.text
    layer = resp.json()["layer"]
    assert layer["overall"] == "FAIL"
    assert layer["checks"][0]["name"] == "crs_declared"
    assert "CRS is required" in layer["checks"][0]["message"]


def test_layer_invalid_crs(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    csv = b"X,Y,Z\n0,0,10\n100,0,11\n0,100,12\n100,100,13\n"
    resp = _layer_post(client, csv, crs="NOPE")
    assert resp.status_code == 400, resp.text
    msg = resp.json()["layer"]["checks"][0]["message"]
    assert "could not be parsed" in msg
    assert "EPSG" in msg


def test_layer_working_crs_reprojects(tmp_path, monkeypatch):
    """Declared Web Mercator + working EPSG:4326 reprojects (Abeokuta region)."""
    client = _client(tmp_path, monkeypatch)
    # Web Mercator metres near 3.35E, 7.16N (separable projection → regular grid).
    csv = b"X,Y,Z\n372000,772000,10\n373000,772000,11\n372000,773000,12\n373000,773000,13\n"
    resp = _layer_post(client, csv, crs="EPSG:3857", working_crs="EPSG:4326")
    assert resp.status_code == 200, resp.text
    layer = resp.json()["layer"]
    crs_check = next(c for c in layer["checks"] if c["name"] == "crs_declared")
    assert "EPSG:4326" in crs_check["message"]


def test_layer_bad_file_non_numeric(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    csv = b"X,Y,Z\na,b,c\nd,e,f\n"
    resp = _layer_post(client, csv, crs="EPSG:32631")
    assert resp.status_code == 400, resp.text
    layer = resp.json()["layer"]
    assert layer["overall"] == "FAIL"
    assert "non-numeric" in layer["checks"][0]["message"]


# --- label inventory (CSV + GeoJSON) -----------------------------------------


def test_labels_csv_success(tmp_path, monkeypatch):
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


def test_labels_geojson_success(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    geojson = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"hazard": "sinkhole"},
                    "geometry": {"type": "Point", "coordinates": [3.35, 7.16]},
                }
            ],
        }
    ).encode()
    resp = client.post(
        "/api/v1/release-shell/labels/inventory",
        data={"crs": "EPSG:4326"},
        files={"file": ("labels.geojson", geojson, "application/geo+json")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["labels"]["counts_by_hazard"]["sinkhole"] == 1


def test_labels_requires_crs(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    csv = b"X,Y,hazard\n3.0,7.0,landslide\n"
    resp = client.post(
        "/api/v1/release-shell/labels/inventory",
        data={"crs": ""},
        files={"file": ("labels.csv", csv, "text/csv")},
    )
    assert resp.status_code == 400, resp.text
    err = resp.json()["error"]
    assert err["code"] == "CRS_REQUIRED"
    assert "CRS is required" in err["message"]


def test_labels_unknown_hazard_is_plain_language(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    csv = b"X,Y,hazard\n3.0,7.0,liquefaction\n"
    resp = client.post(
        "/api/v1/release-shell/labels/inventory",
        data={"crs": "EPSG:4326"},
        files={"file": ("labels.csv", csv, "text/csv")},
    )
    assert resp.status_code == 400, resp.text
    err = resp.json()["error"]
    assert err["code"] == "LABEL_HAZARD"
    assert "Unrecognised hazard label" in err["message"]
    # names the real hazards, not an invented class
    assert "subsidence" in err["message"]


# --- lineament vectors (GeoJSON) ---------------------------------------------


def test_lineaments_success(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    geojson = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "LineString", "coordinates": [[0.0, 0.0], [1.0, 1.0]]},
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


def test_lineaments_bad_json_is_plain_language(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post(
        "/api/v1/release-shell/lineaments/inspect",
        files={"file": ("lines.geojson", b"{not json", "application/geo+json")},
    )
    assert resp.status_code == 400, resp.text
    err = resp.json()["error"]
    assert err["code"] == "LINEAMENT_PARSE"
    assert "Could not read lineament GeoJSON" in err["message"]
    assert "Traceback" not in err["message"]
