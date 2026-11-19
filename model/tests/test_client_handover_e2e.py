"""End-to-end client handover: labelled CSV → train → promote → assess + feature-only refuse."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.ml.constants import CHANNEL_NAMES
from ssri_model.platform.store import MemoryPlatformStore
from tests.api_helpers import build_api_config
from tests.test_csv_import import WIDTH, HEIGHT, _grid_csv

USER = "11111111-1111-4111-8111-111111111111"


def _client(tmp_path: Path) -> TestClient:
    app = create_app(build_api_config(tmp_path))
    app.state.platform_store = MemoryPlatformStore()
    app.state.platform_tokens = {"user-a": (USER, "a@example.com", "user")}
    return TestClient(app)


def test_labelled_csv_train_promote_assess_lifecycle(tmp_path: Path) -> None:
    client = _client(tmp_path)
    auth = {"Authorization": "Bearer user-a"}
    created = client.post("/api/v1/platform/datasets", headers=auth, json={"name": "Handover CSV"})
    dataset_id = created.json()["dataset"]["id"]
    content = _grid_csv(channels=list(CHANNEL_NAMES), label="landslide")
    uploaded = client.post(
        f"/api/v1/platform/datasets/{dataset_id}/versions",
        headers=auth,
        files={"file": ("labelled.csv", content, "text/csv")},
        data={"crs": "EPSG:32631"},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["version"]["validation_status"] == "passed"

    started = client.post(
        "/api/v1/platform/training/runs",
        headers={**auth, "Idempotency-Key": "handover-csv-run"},
        json={"dataset_id": dataset_id, "name": "Handover train"},
    )
    assert started.status_code == 202, started.text
    run_id = started.json()["training_run"]["id"]

    final = None
    for _ in range(120):
        status = client.get(f"/api/v1/platform/training/runs/{run_id}", headers=auth)
        final = status.json()["training_run"]
        if final["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
            break
        time.sleep(0.5)
    assert final is not None
    assert final["status"] == "COMPLETED", final

    models = client.get("/api/v1/platform/models", headers=auth).json()["models"]
    assert models
    model_id = models[0]["id"]
    promoted = client.post(f"/api/v1/platform/models/{model_id}/promote", headers=auth)
    assert promoted.status_code == 200, promoted.text
    checkpoint = promoted.json()["checkpoint_path"]
    assert Path(checkpoint).is_file()

    features = tmp_path / "handover_features.npy"
    np.save(features, np.zeros((13, 8, 8), dtype=np.float32))
    lat, lon = 6.5244, 3.3792
    assess = client.post(
        "/api/v1/assess",
        json={
            "checkpoint": checkpoint,
            "features": str(features),
            "point": {"latitude": lat, "longitude": lon},
            "mc_samples": 2,
        },
    )
    assert assess.status_code == 200, assess.text
    body = assess.json()
    assert body["location_provenance"]["submitted"]["latitude"] == lat
    assert body["location_provenance"]["submitted"]["longitude"] == lon
    assert body["hazard_profiles"]
    assert any(
        p.get("susceptibility_score") is not None
        or p.get("score") is not None
        or p.get("point_estimate") is not None
        or p.get("status")
        for p in body["hazard_profiles"]
    )
    assert body.get("is_fixture_checkpoint") is False


def test_feature_only_csv_cannot_train(tmp_path: Path) -> None:
    client = _client(tmp_path)
    auth = {"Authorization": "Bearer user-a"}
    created = client.post("/api/v1/platform/datasets", headers=auth, json={"name": "Feature only"})
    dataset_id = created.json()["dataset"]["id"]
    lines = ["X,Y,Z"]
    for y in range(HEIGHT):
        for x in range(WIDTH):
            lines.append(f"{-115500 + x * 100},{777400 + y * 100},{10}")
    uploaded = client.post(
        f"/api/v1/platform/datasets/{dataset_id}/versions",
        headers=auth,
        files={"file": ("xyz.csv", ("\n".join(lines)).encode(), "text/csv")},
        data={"crs": "EPSG:32631"},
    )
    assert uploaded.status_code == 200, uploaded.text
    version = uploaded.json()["version"]
    assert version["validation_status"] == "failed"
    assert "cannot be used as a supervised training dataset" in version["validation_errors"][0]
    blocked = client.post(
        "/api/v1/platform/training/runs",
        headers=auth,
        json={"dataset_id": dataset_id, "name": "Should fail"},
    )
    assert blocked.status_code == 400
