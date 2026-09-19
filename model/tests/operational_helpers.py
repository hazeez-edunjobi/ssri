"""Shared helpers for Stage 3.3 operational API tests."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from ssri_model.api.config import APIConfig
from ssri_model.api.operational_config import OperationalConfig
from ssri_model.auth.models import APIKeyRecord
from tests.auth_helpers import (
    build_authenticated_api_config,
    create_authenticated_client,
)


def build_operational_api_config(
    tmp_path: Path,
    *,
    enabled: bool = True,
    rate_limit_enabled: bool = False,
    async_enabled: bool = True,
    inference_requests_per_window: int = 60,
    batch_requests_per_window: int = 30,
    status_requests_per_window: int = 120,
    worker_count: int = 2,
    max_queue_size: int = 100,
) -> tuple[APIConfig, dict[str, tuple[str, APIKeyRecord] | Path]]:
    config, keys = build_authenticated_api_config(tmp_path, enabled=enabled)
    operational = OperationalConfig(
        async_enabled=async_enabled,
        worker_count=worker_count,
        max_queue_size=max_queue_size,
        rate_limit_enabled=rate_limit_enabled,
        inference_requests_per_window=inference_requests_per_window,
        batch_requests_per_window=batch_requests_per_window,
        status_requests_per_window=status_requests_per_window,
    )
    updated = APIConfig(
        service_config=config.service_config,
        auth_config=config.auth_config,
        operational_config=operational,
    )
    return updated, keys


def create_operational_client(
    tmp_path: Path,
    *,
    api_config: APIConfig | None = None,
) -> TestClient:
    if api_config is None:
        api_config, _ = build_operational_api_config(tmp_path)
    return create_authenticated_client(tmp_path, api_config=api_config)


def wait_for_job_status(
    client: TestClient,
    job_id: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 5.0,
    expected: set[str] | None = None,
) -> dict[str, object]:
    terminal = expected or {"completed", "failed", "cancelled"}
    deadline = time.time() + timeout
    last: dict[str, object] = {}
    while time.time() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}", headers=headers or {})
        if response.status_code == 200:
            last = response.json()
            if last.get("status") in terminal:
                return last
        time.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not reach {terminal}; last={last}")


def read_key_store_plaintext(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def key_store_contains_secret(store_path: Path, secret: str) -> bool:
    return secret in read_key_store_plaintext(store_path)
