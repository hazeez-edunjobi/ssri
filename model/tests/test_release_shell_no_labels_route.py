"""Training with no labels must error through the real release-shell /jobs route."""

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


def _build_unlabelled_zip() -> bytes:
    """Stage 2.5 ZIP with feature stacks but every label pixel = nodata (-1)."""
    buf = io.BytesIO()
    ids: list[str] = []
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, (lat, lon) in enumerate(BLOCK_CENTERS):
            sid = f"nolabel_{i:02d}"
            ids.append(sid)
            h, w = 8, 8
            rng = np.random.default_rng(1000 + i)
            feats = rng.normal(0.0, 1.0, size=(13, h, w)).astype(np.float32)
            feats[0] = 100.0 + 5.0 * rng.random((h, w)).astype(np.float32)
            feats[1] = 5.0 + 10.0 * rng.random((h, w)).astype(np.float32)
            npy = io.BytesIO()
            np.save(npy, feats)
            zf.writestr(f"train/{sid}/feature_stack.npy", npy.getvalue())
            zf.writestr(f"train/{sid}/label.tif", _label_tif_bytes(lat, lon))
            zf.writestr(
                f"train/{sid}/metadata.json",
                json.dumps(
                    {
                        "centroid_lat": lat,
                        "centroid_lon": lon,
                        "synthetic": True,
                        "sample_id": sid,
                    }
                ),
            )

        sid_v = "nolabel_val"
        rng = np.random.default_rng(9999)
        feats = rng.normal(0.0, 1.0, size=(13, 8, 8)).astype(np.float32)
        feats[0] = 100.0 + 5.0 * rng.random((8, 8)).astype(np.float32)
        feats[1] = 5.0 + 10.0 * rng.random((8, 8)).astype(np.float32)
        npy = io.BytesIO()
        np.save(npy, feats)
        zf.writestr(f"validation/{sid_v}/feature_stack.npy", npy.getvalue())
        zf.writestr(f"validation/{sid_v}/label.tif", _label_tif_bytes(33.5, -112.5))
        zf.writestr(
            f"validation/{sid_v}/metadata.json",
            json.dumps(
                {
                    "centroid_lat": 33.5,
                    "centroid_lon": -112.5,
                    "synthetic": True,
                    "sample_id": sid_v,
                }
            ),
        )

        manifest = {
            "dataset_name": "SYNTHETIC_no_labels",
            "version": "0.0.1-SYNTHETIC",
            "created_at": "2026-01-01T00:00:00+00:00",
            "channels": list(CHANNEL_NAMES),
            "channel_names": list(CHANNEL_NAMES),
            "label_classes": ["subsidence", "landslide", "sinkhole"],
            "resolution": 30.0,
            "crs": "EPSG:4326",
            "normalization": {},
            "train_count": len(ids),
            "validation_count": 1,
            "test_count": 0,
            "splits": {"train": ids, "validation": [sid_v], "test": []},
            "synthetic": True,
        }
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("statistics.json", json.dumps({"channel_stats": {}}))
    return buf.getvalue()


def test_jobs_route_refuses_training_without_labels(tmp_path, monkeypatch):
    monkeypatch.setenv("SSRI_RELEASE_SHELL", "true")
    monkeypatch.setenv("SSRI_RELEASE_SHELL_MIN_TILES", "1")
    monkeypatch.setenv("SSRI_RELEASE_SHELL_MIN_BLOCKS", "1")
    monkeypatch.setenv("SSRI_RELEASE_SHELL_MIN_HELD_OUT", "1")
    monkeypatch.setenv("SSRI_RELEASE_SHELL_BUFFER_KM", "0")

    client = TestClient(create_app(build_api_config(tmp_path)))
    created = client.post(
        "/api/v1/training/datasets",
        json={"name": "no-labels", "notes": "SYNTHETIC unlabelled"},
    )
    assert created.status_code in {200, 201}, created.text
    ds_id = created.json()["dataset"]["dataset_id"]

    raw = _build_unlabelled_zip()
    up = client.post(
        f"/api/v1/release-shell/datasets/{ds_id}/upload",
        files={"file": ("nolabels.zip", raw, "application/zip")},
    )
    assert up.status_code == 200, up.text

    val = client.post(f"/api/v1/release-shell/datasets/{ds_id}/validate")
    assert val.status_code == 200, val.text
    report = val.json()["validation"]
    labels = next(c for c in report["checks"] if c["name"] == "labels_present")
    assert labels["status"] == "FAIL"
    assert report["can_train"] is False

    refused = client.post(
        "/api/v1/release-shell/jobs",
        json={"dataset_id": ds_id, "epochs": 1, "seeds": [42, 43, 44]},
    )
    assert refused.status_code == 400, refused.text
    body = refused.json()
    err = body.get("error") or body
    assert err.get("code") == "VALIDATION_FAILED"
    assert "label" in str(err.get("message", "")).lower()
