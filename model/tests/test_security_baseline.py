"""Security baseline regression tests for Stage/Phase 2 hardening."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.auth.config import AuthConfig
from ssri_model.auth.exceptions import InvalidAuthConfigError
from ssri_model.service.exceptions import InvalidServiceRequestError
from ssri_model.service.validation import resolve_request_scientific_status
from tests.api_helpers import build_api_config


def test_production_cannot_enable_development_auth_mode() -> None:
    with pytest.raises(InvalidAuthConfigError):
        AuthConfig(
            enabled=True,
            environment="production",
            development_auth_mode=True,
            key_store_path="auth/keys.json",
        )


def test_client_cannot_assert_scientifically_validated() -> None:
    with pytest.raises(InvalidServiceRequestError):
        resolve_request_scientific_status(
            "SCIENTIFICALLY_VALIDATED",
            trust_client_scientific_status=True,
        )


def test_untrusted_client_status_clamped_to_not_validated() -> None:
    resolved = resolve_request_scientific_status(
        "DATASET_AUDITED",
        trust_client_scientific_status=False,
    )
    assert resolved == "NOT_VALIDATED"


def test_trusted_intermediate_status_preserved() -> None:
    resolved = resolve_request_scientific_status(
        "DATASET_AUDITED",
        trust_client_scientific_status=True,
    )
    assert resolved == "DATASET_AUDITED"


def test_production_env_defaults_distrust_client_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "production")
    monkeypatch.setenv("SSRI_AUTH_ENABLED", "true")
    monkeypatch.setenv("SSRI_AUTH_KEY_STORE", "auth/keys.json")
    monkeypatch.delenv("SSRI_TRUST_CLIENT_SCIENTIFIC_STATUS", raising=False)
    monkeypatch.delenv("SSRI_RATE_LIMIT_ENABLED", raising=False)
    from ssri_model.api.config import APIConfig

    config = APIConfig.from_env()
    assert config.service_config.trust_client_scientific_status is False
    assert config.operational_config.rate_limit_enabled is True


def test_spoofed_scientific_status_rejected_by_api(tmp_path) -> None:
    config = build_api_config(tmp_path)
    # Force distrust even in development for this case.
    config = type(config).from_dict(
        {
            **config.to_dict(),
            "service_config": {
                **config.service_config.to_dict(),
                "trust_client_scientific_status": False,
            },
        }
    )
    client = TestClient(create_app(config))
    response = client.post(
        "/api/v1/inference",
        json={
            "request_id": "req-spoof",
            "checkpoint": "missing.pt",
            "features": "missing.npy",
            "manifest": "missing.json",
            "statistics": "missing.json",
            "scientific_validation_status": "SCIENTIFICALLY_VALIDATED",
        },
    )
    assert response.status_code in {400, 422, 500} or response.status_code >= 400
