"""Presentation demo catalogue coherence and isolation tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.api.demo_assessment import (
    ILLUSTRATIVE_DISCLOSURE,
    build_demo_assessment_response,
    list_demo_scenarios,
    select_demo_scenario,
)
from ssri_model.api.routes.assess import AssessResponseBody
from ssri_model.ml.constants import SUPPORTED_LABELS
from tests.api_helpers import build_api_config


def _client(tmp_path: Path, *, demo_mode: bool) -> TestClient:
    return TestClient(create_app(build_api_config(tmp_path, demo_mode=demo_mode)))


def test_catalogue_covers_required_nigerian_locations() -> None:
    scenarios = list_demo_scenarios()
    locations = {s["location_name"] for s in scenarios}
    required = {
        "Lagos",
        "Abeokuta",
        "Ibadan",
        "Port Harcourt",
        "Benin City",
        "Enugu",
        "Calabar",
        "Uyo",
        "Jos",
        "Abuja",
    }
    assert required.issubset(locations)
    assert len(scenarios) >= 20


def test_demo_scores_and_intervals_are_coherent() -> None:
    for entry in list_demo_scenarios():
        payload = build_demo_assessment_response(
            request_id="coherence",
            hazards=list(SUPPORTED_LABELS),
            model_version="ssri-model",
            scenario_key=entry["key"],
        )
        AssessResponseBody.model_validate(payload)
        hazards = {p["hazard_type"] for p in payload["hazard_profiles"]}
        assert set(SUPPORTED_LABELS) == hazards
        for profile in payload["hazard_profiles"]:
            score = profile["susceptibility_score"]
            assert 0.0 <= score <= 1.0
            ci80 = profile["credible_interval_80"]
            ci95 = profile["credible_interval_95"]
            assert ci80[0] <= score <= ci80[1]
            assert ci95[0] <= score <= ci95[1]
            assert ci95[0] <= ci80[0] and ci95[1] >= ci80[1]
            assert profile["confidence_tier"] in {"High", "Moderate", "Low"}


def test_missing_geological_values_are_never_zero() -> None:
    payload = build_demo_assessment_response(
        request_id="geo",
        hazards=list(SUPPORTED_LABELS),
        model_version="ssri-model",
        scenario_key="elevated",
    )
    layers = payload["conditioning_features"]["layers"]
    for name, layer in layers.items():
        if layer["status"] != "available":
            assert layer["value"] is None, name
        else:
            assert isinstance(layer["value"], (int, float)), name
            assert layer["value"] is not None, name
    assert "Assessment Preview" in payload["conditioning_features"]["notes"][0]


def test_demo_results_are_deterministic() -> None:
    first = build_demo_assessment_response(
        request_id="fixed",
        hazards=list(SUPPORTED_LABELS),
        model_version="ssri-model",
        scenario_key="abuja-capital",
    )
    second = build_demo_assessment_response(
        request_id="fixed",
        hazards=list(SUPPORTED_LABELS),
        model_version="ssri-model",
        scenario_key="abuja-capital",
    )
    assert first == second


def test_scenario_key_overrides_coordinates() -> None:
    payload = build_demo_assessment_response(
        request_id="key",
        hazards=list(SUPPORTED_LABELS),
        model_version="ssri-model",
        point={"latitude": 6.5244, "longitude": 3.3792},
        scenario_key="jos-plateau",
    )
    assert any("location_name=Jos" in n for n in payload["notes"])
    assert any("scenario_key=jos-plateau" in n for n in payload["notes"])


def test_demo_catalogue_endpoint_gated(tmp_path: Path) -> None:
    off = _client(tmp_path, demo_mode=False)
    assert off.get("/api/v1/demo/scenarios").status_code == 404
    on = _client(tmp_path, demo_mode=True)
    response = on.get("/api/v1/demo/scenarios")
    assert response.status_code == 200
    body = response.json()
    assert body["demo_mode"] is True
    assert ILLUSTRATIVE_DISCLOSURE in body["disclosure"]
    assert body["count"] == len(body["scenarios"])


def test_demo_assess_does_not_persist_under_output_root(tmp_path: Path) -> None:
    client = _client(tmp_path, demo_mode=True)
    response = client.post(
        "/api/v1/assess",
        json={
            "request_id": "persist-check",
            "demo_scenario_key": "elevated",
            "hazards": ["landslide", "subsidence", "sinkhole"],
        },
    )
    assert response.status_code == 200
    assessment_id = response.json()["assessment_id"]
    persisted = list((tmp_path / "service-outputs").rglob(f"*{assessment_id}*"))
    assert persisted == []


def test_live_mode_ignores_demo_scenario_key_and_requires_checkpoint(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path, demo_mode=False)
    response = client.post(
        "/api/v1/assess",
        json={
            "demo_scenario_key": "elevated",
            "point": {"latitude": 6.52, "longitude": 3.38},
        },
    )
    assert response.status_code == 400
    assert "checkpoint" in str(response.json()).lower()


def test_select_demo_scenario_known_lagos_site() -> None:
    assert select_demo_scenario(6.5244, 3.3792).key == "elevated"
