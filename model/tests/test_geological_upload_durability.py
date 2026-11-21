"""Geological upload durability / auth / original download remediation tests."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ssri_model.geological.durable import (
    build_geological_storage,
    write_bytes_atomic,
)
from ssri_model.geological.service import GeologicalService
from ssri_model.geological.storage import GeologicalStorage
from ssri_model.service.exceptions import InvalidServiceConfigError
from ssri_model.storage import LocalObjectStorage
from tests.auth_helpers import auth_header, build_authenticated_api_config, create_authenticated_client

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "geological"


def test_write_bytes_atomic_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "layer.csv"
    payload = b"X,Y,Z\n1,2,3\n"
    write_bytes_atomic(path, payload)
    assert path.read_bytes() == payload
    assert not (path.parent / f".{path.name}.tmp").exists()


def test_local_object_storage_get_bytes(tmp_path: Path) -> None:
    store = LocalObjectStorage(root=tmp_path / "objects")
    key = store.put_bytes("geological/demo.csv", b"a,b,c\n", content_type="text/csv")
    assert store.get_bytes(key) == b"a,b,c\n"
    with pytest.raises(FileNotFoundError):
        store.get_bytes("missing/key.csv")


def test_build_geological_storage_refuses_incomplete_r2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SSRI_GEOLOGICAL_STORAGE_BACKEND", "r2")
    with pytest.raises(InvalidServiceConfigError) as exc:
        build_geological_storage(tmp_path)
    assert "not supported yet" in str(exc.value)
    monkeypatch.setenv("SSRI_GEOLOGICAL_STORAGE_BACKEND", "filesystem")
    storage = build_geological_storage(tmp_path)
    assert isinstance(storage, GeologicalStorage)


def test_upload_sha256_and_original_download_round_trip(tmp_path: Path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    headers = auth_header(operator_key)
    raw = (FIXTURES / "regular.csv").read_bytes()
    expected_sha = hashlib.sha256(raw).hexdigest()

    created = client.post(
        "/api/v1/geological/datasets",
        json={"display_name": "SSRI_UPLOAD_VERIFICATION_TEST", "asset_kind": "point_grid_csv"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    geo_id = created.json()["dataset"]["geo_id"]

    uploaded = client.post(
        f"/api/v1/geological/datasets/{geo_id}/upload",
        headers=headers,
        files={"file": ("regular.csv", raw, "text/csv")},
    )
    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    assert body["dataset"]["content_sha256"] == expected_sha
    assert body["dataset"]["has_original"] is True
    assert body["dataset"]["validation_status"] == "inspected"

    downloaded = client.get(
        f"/api/v1/geological/datasets/{geo_id}/original",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.content == raw
    assert hashlib.sha256(downloaded.content).hexdigest() == expected_sha

    declared = client.post(
        f"/api/v1/geological/datasets/{geo_id}/declare",
        headers=headers,
        json={
            "measurement_type": "overburden_thickness",
            "crs": "EPSG:32631",
            "units": "m",
            "x_column": "X",
            "y_column": "Y",
            "z_column": "Z",
        },
    )
    assert declared.status_code == 200, declared.text
    validated = client.post(
        f"/api/v1/geological/datasets/{geo_id}/validate",
        headers=headers,
    )
    assert validated.status_code == 200, validated.text
    assert validated.json()["dataset"]["validation_status"] == "validated"
    assert validated.json()["dataset"]["scientific_validation_status"] == "NOT_VALIDATED"


def test_user_cannot_mutate_geological_catalogue(tmp_path: Path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    user_key, _ = keys["user"]
    operator_key, _ = keys["operator"]

    denied = client.post(
        "/api/v1/geological/datasets",
        json={"display_name": "user-blocked"},
        headers=auth_header(user_key),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    created = client.post(
        "/api/v1/geological/datasets",
        json={"display_name": "ops-owned"},
        headers=auth_header(operator_key),
    )
    assert created.status_code == 201
    geo_id = created.json()["dataset"]["geo_id"]
    raw = (FIXTURES / "regular.csv").read_bytes()
    assert (
        client.post(
            f"/api/v1/geological/datasets/{geo_id}/upload",
            headers=auth_header(user_key),
            files={"file": ("regular.csv", raw, "text/csv")},
        ).status_code
        == 403
    )
    # Operator uploads so list/get remain available; user may read.
    assert (
        client.post(
            f"/api/v1/geological/datasets/{geo_id}/upload",
            headers=auth_header(operator_key),
            files={"file": ("regular.csv", raw, "text/csv")},
        ).status_code
        == 200
    )
    listed = client.get("/api/v1/geological/datasets", headers=auth_header(user_key))
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    assert (
        client.get(
            f"/api/v1/geological/datasets/{geo_id}/original",
            headers=auth_header(user_key),
        ).status_code
        == 403
    )


def test_unauthenticated_geological_upload_is_401(tmp_path: Path) -> None:
    config, _ = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    response = client.post(
        "/api/v1/geological/datasets",
        json={"display_name": "anon"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_concurrent_create_unique_geo_ids(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)

    def _create(index: int):
        return svc.create(display_name=f"concurrent-{index}").geo_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(_create, range(16)))
    assert len(ids) == len(set(ids))
    assert all(storage.dataset_dir(geo_id).exists() for geo_id in ids)


def test_storage_failure_missing_source_raises(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="empty")
    with pytest.raises(Exception) as exc:
        svc.validate(rec.geo_id)
    assert getattr(exc.value, "code", "") == "UPLOAD_REQUIRED"
