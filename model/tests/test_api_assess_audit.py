"""Assessment audit-trail and fixture-checkpoint policy tests."""

from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.api.checkpoint_identity import (
    enforce_fixture_checkpoint_policy,
    is_fixture_dataset_name,
    sha256_file,
)
from ssri_model.architecture import SSRIModelConfig
from ssri_model.ml.constants import CHANNEL_COUNT
from ssri_model.service.exceptions import InvalidServiceRequestError
from tests.api_helpers import build_api_config
from tests.inference_helpers import save_inference_checkpoint


def test_fixture_dataset_names() -> None:
    assert is_fixture_dataset_name("e2e")
    assert is_fixture_dataset_name("demo")
    assert not is_fixture_dataset_name("lagos-v1")


def test_fixture_refused_in_staging(monkeypatch) -> None:
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "staging")
    monkeypatch.delenv("SSRI_ALLOW_FIXTURE_CHECKPOINTS", raising=False)
    with pytest.raises(InvalidServiceRequestError, match="fixture"):
        enforce_fixture_checkpoint_policy("e2e")


def test_fixture_allowed_in_development(monkeypatch) -> None:
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "development")
    assert enforce_fixture_checkpoint_policy("e2e") is True


def test_assess_persists_response_and_identity(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "development")
    monkeypatch.delenv("SSRI_DOMAIN_CENTROID_PATH", raising=False)
    monkeypatch.delenv("SSRI_ALLOW_FIXTURE_CHECKPOINTS", raising=False)

    ckpt = save_inference_checkpoint(
        tmp_path / "model.pt",
        model_config=SSRIModelConfig(base_channels=8, num_encoder_stages=2, dropout=0.1),
        dataset_identity={"name": "research-v0", "version": "0.1.0"},
    )
    features = tmp_path / "features.npy"
    np.save(features, np.random.randn(CHANNEL_COUNT, 8, 8).astype(np.float32))

    client = TestClient(create_app(build_api_config(tmp_path)))
    response = client.post(
        "/api/v1/assess",
        json={
            "checkpoint": str(ckpt),
            "features": str(features),
            "mc_samples": 4,
            "hazards": ["subsidence", "landslide", "sinkhole"],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["domain_similarity_calibrated"] is False
    assert body["is_fixture_checkpoint"] is False
    assert body["checkpoint_dataset_name"] == "research-v0"
    assert body["checkpoint_dataset_version"] == "0.1.0"
    assert body["checkpoint_sha256"] == sha256_file(ckpt)
    for profile in body["hazard_profiles"]:
        assert profile["domain_similarity_score"] is None

    assess_id = body["assessment_id"]
    matches = list(tmp_path.rglob("assess_response.json"))
    assert matches, "assess_response.json was not persisted"
    saved = json.loads(matches[0].read_text(encoding="utf-8"))
    assert saved["assessment_id"] == assess_id
    assert saved["checkpoint_sha256"] == body["checkpoint_sha256"]


def test_assess_tags_e2e_fixture(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "development")
    monkeypatch.delenv("SSRI_DOMAIN_CENTROID_PATH", raising=False)

    ckpt = save_inference_checkpoint(
        tmp_path / "e2e.pt",
        model_config=SSRIModelConfig(base_channels=8, num_encoder_stages=2, dropout=0.0),
        dataset_identity={"name": "e2e", "version": "0"},
    )
    features = tmp_path / "features.npy"
    np.save(features, np.random.randn(CHANNEL_COUNT, 8, 8).astype(np.float32))

    client = TestClient(create_app(build_api_config(tmp_path)))
    response = client.post(
        "/api/v1/assess",
        json={"checkpoint": str(ckpt), "features": str(features), "mc_samples": 4},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_fixture_checkpoint"] is True
    assert body["checkpoint_dataset_name"] == "e2e"


def test_assess_uncalibrated_forces_low_confidence(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "development")
    monkeypatch.delenv("SSRI_DOMAIN_CENTROID_PATH", raising=False)

    ckpt = save_inference_checkpoint(
        tmp_path / "model.pt",
        dataset_identity={"name": "research-v0", "version": "0.1.0"},
    )
    features = tmp_path / "features.npy"
    np.save(features, np.random.randn(CHANNEL_COUNT, 8, 8).astype(np.float32))

    client = TestClient(create_app(build_api_config(tmp_path)))
    response = client.post(
        "/api/v1/assess",
        json={"checkpoint": str(ckpt), "features": str(features), "mc_samples": 4},
    )
    assert response.status_code == 200
    for profile in response.json()["hazard_profiles"]:
        assert profile["confidence_tier"] == "Low"
