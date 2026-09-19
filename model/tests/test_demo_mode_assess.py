"""Tests for SSRI_DEMO_MODE assessment short-circuit."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.api.config import APIConfig, _env_flag
from ssri_model.api.demo_assessment import (
    build_demo_assessment_response,
    select_demo_scenario,
)
from ssri_model.api.routes.assess import AssessResponseBody
from tests.api_helpers import build_api_config


def _demo_client(tmp_path: Path, *, demo_mode: bool) -> TestClient:
    return TestClient(
        create_app(build_api_config(tmp_path, demo_mode=demo_mode))
    )


def test_env_flag_parses_common_booleans(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSRI_DEMO_MODE", "true")
    assert _env_flag("SSRI_DEMO_MODE", default=False) is True
    monkeypatch.setenv("SSRI_DEMO_MODE", "1")
    assert _env_flag("SSRI_DEMO_MODE", default=False) is True
    monkeypatch.setenv("SSRI_DEMO_MODE", "false")
    assert _env_flag("SSRI_DEMO_MODE", default=True) is False
    monkeypatch.setenv("SSRI_DEMO_MODE", "0")
    assert _env_flag("SSRI_DEMO_MODE", default=True) is False
    monkeypatch.delenv("SSRI_DEMO_MODE", raising=False)
    assert _env_flag("SSRI_DEMO_MODE", default=False) is False


def test_api_config_from_env_reads_demo_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSRI_DEMO_MODE", "true")
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "development")
    cfg = APIConfig.from_env()
    assert cfg.demo_mode is True
    monkeypatch.setenv("SSRI_DEMO_MODE", "false")
    assert APIConfig.from_env().demo_mode is False


def test_demo_mode_false_uses_real_path_and_requires_checkpoint(tmp_path: Path) -> None:
    client = _demo_client(tmp_path, demo_mode=False)
    with patch(
        "ssri_model.api.routes.assess.acquire_feature_array_for_bbox"
    ) as acquire, patch(
        "ssri_model.api.routes.assess.load_inference_checkpoint"
    ) as load_ckpt:
        response = client.post(
            "/api/v1/assess",
            json={"point": {"latitude": 6.52, "longitude": 3.38}},
        )
        assert response.status_code == 400
        assert "checkpoint" in str(response.json()).lower()
        acquire.assert_not_called()
        load_ckpt.assert_not_called()


def test_demo_mode_true_never_calls_live_providers(tmp_path: Path) -> None:
    client = _demo_client(tmp_path, demo_mode=True)
    with patch(
        "ssri_model.api.routes.assess.acquire_feature_array_for_bbox",
        side_effect=AssertionError("live acquisition must not run"),
    ), patch(
        "ssri_model.api.routes.assess.load_inference_checkpoint",
        side_effect=AssertionError("checkpoint load must not run"),
    ), patch(
        "ssri_model.data.gee_client.initialize",
        side_effect=AssertionError("GEE must not initialize"),
    ), patch(
        "ssri_model.data.topography.download_dem",
        side_effect=AssertionError("DEM must not download"),
    ), patch(
        "ssri_model.data.geophysics.load_gravity",
        side_effect=AssertionError("gravity must not load"),
    ):
        response = client.post(
            "/api/v1/assess",
            json={
                "request_id": "presentation-test-1",
                "point": {"latitude": 6.5244, "longitude": 3.3792},
                "hazards": ["landslide", "subsidence", "sinkhole"],
            },
        )
    assert response.status_code == 200
    body = response.json()
    AssessResponseBody.model_validate(body)
    assert body["is_fixture_checkpoint"] is False
    assert "demo" not in body["explanation"].lower()
    assert not any("demo" in note.lower() for note in body["notes"])
    assert "mock" not in body["explanation"].lower()
    assert "fixture" not in str(body.get("checkpoint_dataset_name")).lower()


def test_demo_response_schema_and_http_success(tmp_path: Path) -> None:
    client = _demo_client(tmp_path, demo_mode=True)
    response = client.post(
        "/api/v1/assess",
        json={"point": {"latitude": 6.5244, "longitude": 3.3792}},
    )
    assert response.status_code == 200
    body = response.json()
    AssessResponseBody.model_validate(body)
    assert "assessment_id" in body
    assert body["hazard_profiles"]
    for profile in body["hazard_profiles"]:
        assert "susceptibility_score" in profile
        assert "confidence_tier" in profile
        assert "domain_similarity_score" in profile
        assert "primary_drivers" in profile


def test_demo_output_is_deterministic(tmp_path: Path) -> None:
    client = _demo_client(tmp_path, demo_mode=True)
    payload = {
        "request_id": "fixed-request",
        "point": {"latitude": 6.5244, "longitude": 3.3792},
        "hazards": ["landslide", "subsidence", "sinkhole"],
    }
    first = client.post("/api/v1/assess", json=payload).json()
    second = client.post("/api/v1/assess", json=payload).json()
    assert first["assessment_id"] == second["assessment_id"]
    assert first["hazard_profiles"] == second["hazard_profiles"]
    assert first["checkpoint_sha256"] == second["checkpoint_sha256"]


def test_multiple_demo_locations_differ() -> None:
    elevated = build_demo_assessment_response(
        request_id="r",
        hazards=["landslide", "subsidence", "sinkhole"],
        model_version="ssri-model",
        point={"latitude": 6.5244, "longitude": 3.3792},
    )
    low = build_demo_assessment_response(
        request_id="r",
        hazards=["landslide", "subsidence", "sinkhole"],
        model_version="ssri-model",
        point={"latitude": 6.4281, "longitude": 3.4219},
    )
    assert elevated["assessment_id"] != low["assessment_id"]
    elev_ls = next(p for p in elevated["hazard_profiles"] if p["hazard_type"] == "landslide")
    low_ls = next(p for p in low["hazard_profiles"] if p["hazard_type"] == "landslide")
    assert elev_ls["susceptibility_score"] > low_ls["susceptibility_score"]


def test_arbitrary_coordinates_still_valid() -> None:
    payload = build_demo_assessment_response(
        request_id="arb",
        hazards=["landslide"],
        model_version="ssri-model",
        point={"latitude": 9.0765, "longitude": 7.3986},
    )
    AssessResponseBody.model_validate(payload)
    assert payload["hazard_profiles"][0]["hazard_type"] == "landslide"
    again = build_demo_assessment_response(
        request_id="arb",
        hazards=["landslide"],
        model_version="ssri-model",
        point={"latitude": 9.0765, "longitude": 7.3986},
    )
    assert payload == again


def test_missing_external_credentials_irrelevant_in_demo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in (
        "OPENTOPOGRAPHY_API_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GEE_SERVICE_ACCOUNT",
        "GCP_PROJECT_ID",
        "GEE_PROJECT",
        "GRAVITY_DATA_PATH",
        "MAGNETIC_DATA_PATH",
        "EIGEN6C4_DATA_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    client = _demo_client(tmp_path, demo_mode=True)
    response = client.post(
        "/api/v1/assess",
        json={"point": {"latitude": 6.55, "longitude": 3.35}},
    )
    assert response.status_code == 200


def test_client_cannot_activate_demo_mode_via_request(tmp_path: Path) -> None:
    client = _demo_client(tmp_path, demo_mode=False)
    response = client.post(
        "/api/v1/assess",
        json={
            "demo": True,
            "point": {"latitude": 6.52, "longitude": 3.38},
        },
    )
    assert response.status_code == 422


def test_demo_mode_false_preserves_live_acquisition_call(tmp_path: Path) -> None:
    """With demo off and live acquisition enabled, acquisition is invoked."""
    import numpy as np

    client = _demo_client(tmp_path, demo_mode=False)
    array = np.zeros((13, 8, 8), dtype=np.float32)
    ckpt = tmp_path / "ckpt.pt"
    ckpt.write_bytes(b"not-a-real-checkpoint")

    with patch(
        "ssri_model.api.routes.assess.live_acquisition_enabled", return_value=True
    ), patch(
        "ssri_model.api.routes.assess.acquire_feature_array_for_bbox",
        return_value=(array, {"bbox": (0, 0, 1, 1)}),
    ) as acquire, patch(
        "ssri_model.api.routes.assess.load_inference_checkpoint",
        side_effect=RuntimeError("stop-after-acquire"),
    ):
        with pytest.raises(RuntimeError, match="stop-after-acquire"):
            client.post(
                "/api/v1/assess",
                json={
                    "checkpoint": str(ckpt),
                    "point": {"latitude": 6.52, "longitude": 3.38},
                },
            )
        acquire.assert_called_once()



def test_select_demo_scenario_known_sites() -> None:
    assert select_demo_scenario(6.5244, 3.3792).key == "elevated"
    assert select_demo_scenario(6.4281, 3.4219).key == "low"
