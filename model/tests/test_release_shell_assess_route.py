"""POSITIVE-path assess contract through the real /api/v1/assess route."""

from __future__ import annotations

import json

import numpy as np
from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.architecture import SSRIModelConfig
from ssri_model.ml.constants import CHANNEL_COUNT
from ssri_model.release_shell.gates import STATUS_EVALUATED, STATUS_NO_SKILL
from ssri_model.release_shell.meta import write_sidecar
from tests.api_helpers import build_api_config
from tests.inference_helpers import save_inference_checkpoint


def _shell_meta(*, gate: str = STATUS_EVALUATED, disabled: bool = False) -> dict:
    return {
        "data_hash": "DEADBEEF",
        "training_region": {
            "blocks": ["35_-120"],
            "extent": {
                "lat_min": 35.0,
                "lat_max": 40.0,
                "lon_min": -122.0,
                "lon_max": -118.0,
            },
        },
        "hazards": {
            "landslide": {
                "disabled_at_validation": disabled,
                "has_positive_labels": not disabled,
                "gate_status": gate,
                "status": "DISABLED" if disabled else "ENABLED",
                "reason": "insufficient labelled data" if disabled else None,
            },
            "subsidence": {
                "disabled_at_validation": True,
                "has_positive_labels": False,
                "gate_status": "insufficient labelled data",
                "status": "DISABLED",
                "reason": "insufficient labelled data",
            },
            "sinkhole": {
                "disabled_at_validation": False,
                "has_positive_labels": False,
                "gate_status": STATUS_NO_SKILL,
            },
        },
    }


def _client_and_assets(tmp_path, monkeypatch, *, meta: dict):
    monkeypatch.setenv("SSRI_RELEASE_SHELL", "true")
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "development")
    monkeypatch.delenv("SSRI_DOMAIN_CENTROID_PATH", raising=False)
    ckpt = save_inference_checkpoint(
        tmp_path / "shell.pt",
        model_config=SSRIModelConfig(base_channels=8, num_encoder_stages=2, dropout=0.0),
        dataset_identity={"name": "research-shell", "version": "0.0.1"},
    )
    write_sidecar(ckpt, meta)
    features = tmp_path / "features.npy"
    np.save(features, np.random.randn(CHANNEL_COUNT, 8, 8).astype(np.float32))
    client = TestClient(create_app(build_api_config(tmp_path)))
    return client, str(ckpt), str(features)


def _assess(client, checkpoint, features, *, lat: float, lon: float):
    return client.post(
        "/api/v1/assess",
        json={
            "checkpoint": checkpoint,
            "features": features,
            "mc_samples": 2,
            "hazards": ["landslide", "subsidence", "sinkhole"],
            "point": {"latitude": lat, "longitude": lon},
        },
    )


def _by_hazard(body: dict) -> dict:
    return {p["hazard_type"]: p for p in body["hazard_profiles"]}


def test_assess_route_passing_gate_in_region_returns_score(tmp_path, monkeypatch):
    client, ckpt, features = _client_and_assets(
        tmp_path, monkeypatch, meta=_shell_meta(gate=STATUS_EVALUATED)
    )
    response = _assess(client, ckpt, features, lat=37.0, lon=-120.0)
    assert response.status_code == 200, response.text
    body = response.json()
    profiles = _by_hazard(body)
    assert profiles["landslide"]["status"] == "available"
    assert profiles["landslide"]["score"] is not None
    assert profiles["landslide"]["gate_status"] == STATUS_EVALUATED


def test_assess_route_failing_gate_returns_not_available(tmp_path, monkeypatch):
    client, ckpt, features = _client_and_assets(
        tmp_path, monkeypatch, meta=_shell_meta(gate=STATUS_NO_SKILL)
    )
    response = _assess(client, ckpt, features, lat=37.0, lon=-120.0)
    assert response.status_code == 200, response.text
    profiles = _by_hazard(response.json())
    assert profiles["landslide"]["status"] == "not_available"
    assert profiles["landslide"]["score"] is None


def test_assess_route_disabled_head_returns_not_available(tmp_path, monkeypatch):
    client, ckpt, features = _client_and_assets(
        tmp_path, monkeypatch, meta=_shell_meta(disabled=True)
    )
    response = _assess(client, ckpt, features, lat=37.0, lon=-120.0)
    assert response.status_code == 200, response.text
    profiles = _by_hazard(response.json())
    assert profiles["landslide"]["status"] == "not_available"
    assert profiles["landslide"]["score"] is None


def test_assess_route_outside_region_returns_outside_training_region(
    tmp_path, monkeypatch
):
    client, ckpt, features = _client_and_assets(
        tmp_path, monkeypatch, meta=_shell_meta(gate=STATUS_EVALUATED)
    )
    response = _assess(client, ckpt, features, lat=10.0, lon=10.0)
    assert response.status_code == 200, response.text
    profiles = _by_hazard(response.json())
    assert profiles["landslide"]["status"] == "outside_training_region"
    assert profiles["landslide"]["score"] is None
