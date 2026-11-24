"""Filesystem assessment history list/detail."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def _write_assessment(root: Path, assessment_id: str, *, lat: float, lon: float) -> None:
    assess_dir = root / "assessments" / assessment_id
    assess_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "assessment_id": assessment_id,
        "model_version": "ssri-model",
        "checkpoint_id": None,
        "hazard_profiles": [
            {
                "hazard_type": "subsidence",
                "point_estimate": 0.582,
                "confidence_tier": "Low",
            }
        ],
        "location_provenance": {
            "aoi_source": "point",
            "submitted": {"latitude": lat, "longitude": lon, "crs": "EPSG:4326"},
        },
        "notes": ["status remains NOT_VALIDATED"],
        "spatial_output_url": None,
        "domain_similarity_calibrated": False,
    }
    (assess_dir / "assess_response.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_assess_history_list_and_detail(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "development")
    monkeypatch.setenv("SSRI_AUTH_ENABLED", "false")
    monkeypatch.setenv("SSRI_AUTH_DEVELOPMENT_MODE", "true")
    monkeypatch.setenv("SSRI_API_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.setenv("SSRI_EXECUTION_MODE", "local")
    monkeypatch.setenv("SSRI_DEMO_MODE", "false")

    _write_assessment(tmp_path, "assess-historytest01", lat=7.25, lon=3.25)
    _write_assessment(tmp_path, "assess-historytest02", lat=6.5, lon=3.4)

    from ssri_model.api.app import create_app

    client = TestClient(create_app())

    listed = client.get("/api/v1/assess/history?limit=10&offset=0")
    assert listed.status_code == 200
    body = listed.json()
    assert body["count"] >= 2
    assert body["total"] >= 2
    ids = {item["assessment_id"] for item in body["assessments"]}
    assert "assess-historytest01" in ids
    sample = next(
        item
        for item in body["assessments"]
        if item["assessment_id"] == "assess-historytest01"
    )
    assert sample["latitude"] == 7.25
    assert sample["longitude"] == 3.25
    assert sample["hazards"][0]["confidence_tier"] == "Low"

    detail = client.get("/api/v1/assess/history/assess-historytest01")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["summary"]["latitude"] == 7.25
    assert detail_body["assessment"]["hazard_profiles"][0]["point_estimate"] == 0.582

    missing = client.get("/api/v1/assess/history/assess-doesnotexist")
    assert missing.status_code in {400, 404, 422}


def test_lease_recovery_defaults_on_for_staging(monkeypatch) -> None:
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "staging")
    monkeypatch.delenv("SSRI_LEASE_RECOVERY_ENABLED", raising=False)
    monkeypatch.setenv("SSRI_EXECUTION_MODE", "local")
    from ssri_model.infrastructure.config import InfrastructureConfig

    cfg = InfrastructureConfig.from_env()
    assert cfg.lease_recovery_enabled is True


def test_lease_recovery_defaults_off_for_development(monkeypatch) -> None:
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "development")
    monkeypatch.delenv("SSRI_LEASE_RECOVERY_ENABLED", raising=False)
    monkeypatch.setenv("SSRI_EXECUTION_MODE", "local")
    from ssri_model.infrastructure.config import InfrastructureConfig

    cfg = InfrastructureConfig.from_env()
    assert cfg.lease_recovery_enabled is False
