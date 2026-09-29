"""Platform API tests. They do not require a live Supabase project."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.platform.store import MemoryPlatformStore
from tests.api_helpers import build_api_config
from tests.test_manual_training import _write_valid_dataset, _zip_dir


USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"
ADMIN = "33333333-3333-4333-8333-333333333333"


def _client(tmp_path):
    app = create_app(build_api_config(tmp_path))
    app.state.platform_store = MemoryPlatformStore()
    app.state.platform_tokens = {
        "user-a": (USER_A, "a@example.com", "user"),
        "user-b": (USER_B, "b@example.com", "user"),
        "admin": (ADMIN, "admin@example.com", "admin"),
    }
    return TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_platform_requires_session(tmp_path) -> None:
    client = _client(tmp_path)
    response = client.get("/api/v1/platform/me")
    assert response.status_code == 401


def test_dataset_ownership_and_invalid_upload(tmp_path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/platform/datasets",
        headers=_auth("user-a"),
        json={"name": "Lagos tiles", "description": "Stage 2.5 sample"},
    )
    assert created.status_code == 201
    dataset_id = created.json()["dataset"]["id"]

    rejected = client.post(
        f"/api/v1/platform/datasets/{dataset_id}/versions",
        headers=_auth("user-a"),
        files={"file": ("notes.txt", b"not a zip", "text/plain")},
    )
    assert rejected.status_code == 400
    assert "zip" in rejected.json()["error"]["message"].lower()

    csv = client.post(
        f"/api/v1/platform/datasets/{dataset_id}/versions",
        headers=_auth("user-a"),
        files={"file": ("training.csv", b"lat,lon\n6.5,3.3\n", "text/csv")},
        data={"crs": "EPSG:32631"},
    )
    assert csv.status_code == 400
    assert "unrecognized column: lat" in csv.json()["error"]["message"]

    hidden = client.get(f"/api/v1/platform/datasets/{dataset_id}", headers=_auth("user-b"))
    assert hidden.status_code == 404

    listing = client.get("/api/v1/platform/datasets", headers=_auth("user-b"))
    assert listing.json()["total"] == 0


def test_training_run_is_async_and_not_scientifically_validated(tmp_path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/platform/datasets",
        headers=_auth("user-a"),
        json={"name": "Train set"},
    )
    dataset_id = created.json()["dataset"]["id"]
    payload = _zip_dir(_write_valid_dataset(tmp_path / "ds"))
    uploaded = client.post(
        f"/api/v1/platform/datasets/{dataset_id}/versions",
        headers=_auth("user-a"),
        files={"file": ("dataset.zip", payload, "application/zip")},
    )
    assert uploaded.status_code == 200
    version = uploaded.json()["version"]
    assert version["validation_status"] == "passed"
    assert version["content_sha256"]
    assert version["storage_path"] == f"{USER_A}/{dataset_id}/{version['id']}/dataset.zip"
    assert version["preview"]["extracted_root"]

    second = client.post(
        f"/api/v1/platform/datasets/{dataset_id}/versions",
        headers=_auth("user-a"),
        files={"file": ("dataset.zip", payload, "application/zip")},
    )
    assert second.json()["version"]["version"] == 2

    started = client.post(
        "/api/v1/platform/training/runs",
        headers={**_auth("user-a"), "Idempotency-Key": "run-once"},
        json={"dataset_id": dataset_id, "name": "First run"},
    )
    assert started.status_code == 202
    run_id = started.json()["training_run"]["id"]
    assert started.json()["training_run"]["scientific_validation_status"] == "NOT_VALIDATED"

    duplicate = client.post(
        "/api/v1/platform/training/runs",
        headers={**_auth("user-a"), "Idempotency-Key": "run-once"},
        json={"dataset_id": dataset_id, "name": "First run"},
    )
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["training_run"]["id"] == run_id

    import time

    final = None
    for _ in range(80):
        status = client.get(f"/api/v1/platform/training/runs/{run_id}", headers=_auth("user-a"))
        final = status.json()["training_run"]
        if final["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
            break
        time.sleep(0.5)
    assert final is not None
    assert final["status"] == "COMPLETED", final
    assert final["scientific_validation_status"] == "NOT_VALIDATED"

    other = client.get(f"/api/v1/platform/training/runs/{run_id}", headers=_auth("user-b"))
    assert other.status_code == 404

    models = client.get("/api/v1/platform/models", headers=_auth("user-a"))
    assert models.json()["total"] == 1
    assert models.json()["models"][0]["scientific_validation_status"] == "NOT_VALIDATED"
    assert models.json()["models"][0]["feature_channels"] == 13

    activity = client.get("/api/v1/platform/activity", headers=_auth("user-a"))
    actions = {item["action"] for item in activity.json()["activities"]}
    assert "training_completed" in actions
    assert "model_created" in actions


def test_admin_portal_is_role_gated(tmp_path) -> None:
    client = _client(tmp_path)
    denied = client.get("/api/v1/platform/admin/overview", headers=_auth("user-a"))
    assert denied.status_code == 403
    allowed = client.get("/api/v1/platform/admin/users", headers=_auth("admin"))
    assert allowed.status_code == 200
    assert allowed.json()["total"] >= 1


def test_failed_validation_blocks_training(tmp_path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/platform/datasets",
        headers=_auth("user-a"),
        json={"name": "Broken"},
    )
    dataset_id = created.json()["dataset"]["id"]
    uploaded = client.post(
        f"/api/v1/platform/datasets/{dataset_id}/versions",
        headers=_auth("user-a"),
        files={"file": ("dataset.zip", b"not-a-zip", "application/zip")},
    )
    assert uploaded.status_code == 400
    blocked = client.post(
        "/api/v1/platform/training/runs",
        headers=_auth("user-a"),
        json={"dataset_id": dataset_id, "name": "Should not run"},
    )
    assert blocked.status_code == 400
