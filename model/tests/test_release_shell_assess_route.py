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
        "crs": "EPSG:4326",
        "block_size_deg": 5.0,
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
        tmp_path / "service-outputs" / "shell.pt",
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


def test_assess_route_no_checkpoint_returns_no_trained_model(tmp_path, monkeypatch):
    monkeypatch.setenv("SSRI_RELEASE_SHELL", "true")
    client = TestClient(create_app(build_api_config(tmp_path)))
    features = tmp_path / "features.npy"
    np.save(features, np.random.randn(CHANNEL_COUNT, 8, 8).astype(np.float32))
    response = client.post(
        "/api/v1/assess",
        json={"features": str(features), "point": {"latitude": 37.0, "longitude": -120.0}},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "no_trained_model"
    assert body["scientific_validation_status"] == "NOT_VALIDATED"
    assert "Upload" in body["message"]


def test_assess_route_schema_mismatch_is_rejected_with_plain_language(tmp_path, monkeypatch):
    client, ckpt, _ = _client_and_assets(
        tmp_path, monkeypatch, meta=_shell_meta(gate=STATUS_EVALUATED)
    )
    mismatched = tmp_path / "features_v2.npy"
    np.save(mismatched, np.random.randn(16, 8, 8).astype(np.float32))
    response = _assess(client, ckpt, str(mismatched), lat=37.0, lon=-120.0)
    assert response.status_code in {400, 422}, response.text
    message = json.dumps(response.json())
    assert "channel" in message.lower()
    assert "Traceback" not in message


def _write_evaluation(tmp_path) -> None:
    per_seed = {}
    for seed in ("42", "43", "44"):
        per_seed[seed] = {
            "split_policy": "whole_5deg_blocks_with_buffer",
            "hazards": {
                "landslide": {
                    "gate_status": STATUS_EVALUATED,
                    "roc_auc": 0.71,
                    "baselines": {
                        "model_auc_ci95": [0.62, 0.80],
                        "delta_auc_vs_slope": 0.11,
                        "delta_auc_ci95": [0.03, 0.19],
                        "slope_only_auc": 0.60,
                    },
                    "per_block": {"35_-120": {"n": 40, "n_pos": 12, "roc_auc": 0.74}},
                    "frac_held_out_blocks_auc_gt_0_5": 0.8,
                }
            },
        }
    report = {
        "status": "completed",
        "scientific_validation_status": "NOT_VALIDATED",
        "seeds": [42, 43, 44],
        "per_seed": per_seed,
        "hazards": {"landslide": {"gate_status": STATUS_EVALUATED}},
        "score_framing": "relative susceptibility rankings",
    }
    (tmp_path / "release_shell_evaluation.json").write_text(
        json.dumps(report), encoding="utf-8"
    )


def test_assess_response_carries_checkpoint_id_and_evaluation_summary(tmp_path, monkeypatch):
    client, ckpt, features = _client_and_assets(
        tmp_path, monkeypatch, meta=_shell_meta(gate=STATUS_EVALUATED)
    )
    _write_evaluation(tmp_path)
    body = _assess(client, ckpt, features, lat=37.0, lon=-120.0).json()

    assert body["checkpoint_id"] == "shell"
    summary = body["evaluation_summary"]
    assert summary is not None
    assert summary["seeds"] == [42, 43, 44]
    assert summary["scientific_validation_status"] == "NOT_VALIDATED"
    lands = summary["hazards"]["landslide"]
    assert lands["roc_auc"] == 0.71
    assert lands["roc_auc_ci95"] == [0.62, 0.80]
    assert lands["delta_auc_vs_slope"] == 0.11
    assert lands["per_block"]["35_-120"]["n_pos"] == 12
    assert set(lands["seed_aucs"]) == {"42", "43", "44"}
    # Training CRS + block size surface as notes for the report.
    assert "assess_crs=EPSG:4326" in body["notes"]
    assert any(n.startswith("block_size_deg=") for n in body["notes"])


def test_assess_evaluation_summary_absent_when_no_report(tmp_path, monkeypatch):
    client, ckpt, features = _client_and_assets(
        tmp_path, monkeypatch, meta=_shell_meta(gate=STATUS_EVALUATED)
    )
    body = _assess(client, ckpt, features, lat=37.0, lon=-120.0).json()
    assert body["evaluation_summary"] is None
