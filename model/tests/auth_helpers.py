"""Shared helpers for SSRI authentication tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.api.config import APIConfig
from ssri_model.auth.config import AuthConfig
from ssri_model.auth.credentials import KeyStore, generate_api_key
from ssri_model.auth.models import APIKeyRecord, Role
from ssri_model.service.config import ServiceConfig
from tests.orchestration_helpers import mock_run_inference


def write_key_store(path: Path, records: list[APIKeyRecord]) -> Path:
    KeyStore.write(path, records)
    return path


def provision_keys(tmp_path: Path) -> dict[str, tuple[str, APIKeyRecord]]:
    viewer = generate_api_key(role=Role.VIEWER, description="viewer test key")
    operator = generate_api_key(role=Role.OPERATOR, description="operator test key")
    admin = generate_api_key(role=Role.ADMIN, description="admin test key")
    store_path = tmp_path / "auth" / "keys.json"
    write_key_store(store_path, [viewer.record, operator.record, admin.record])
    return {
        "viewer": (viewer.plaintext_key, viewer.record),
        "operator": (operator.plaintext_key, operator.record),
        "admin": (admin.plaintext_key, admin.record),
        "store_path": store_path,
    }


def build_authenticated_api_config(
    tmp_path: Path,
    *,
    enabled: bool = True,
    environment: str = "development",
) -> tuple[APIConfig, dict[str, tuple[str, APIKeyRecord] | Path]]:
    keys = provision_keys(tmp_path)
    store_path = keys["store_path"]
    assert isinstance(store_path, Path)
    service_config = ServiceConfig(
        output_root=str(tmp_path / "service-outputs"),
        environment=environment,
        scientific_validation_required=False,
        allow_unvalidated_predictions=True,
    )
    auth_config = AuthConfig(
        enabled=enabled,
        environment=environment,
        key_store_path=str(store_path),
        development_auth_mode=True,
    )
    config = APIConfig(service_config=service_config, auth_config=auth_config)
    return config, keys


def create_authenticated_client(
    tmp_path: Path,
    *,
    api_config: APIConfig | None = None,
    key_store: KeyStore | None = None,
) -> TestClient:
    if api_config is None:
        api_config, _ = build_authenticated_api_config(tmp_path)
    app = create_app(
        api_config,
        inference_runner=mock_run_inference,
        batch_inference_runner=mock_run_inference,
        key_store=key_store,
    )
    return TestClient(app)


def auth_header(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}
