"""HTTP surface for subsidence scientific validation harness."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "development")
    monkeypatch.setenv("SSRI_AUTH_ENABLED", "false")
    monkeypatch.setenv("SSRI_AUTH_DEVELOPMENT_MODE", "true")
    monkeypatch.setenv("SSRI_API_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.setenv("SSRI_EXECUTION_MODE", "local")
    monkeypatch.setenv("SSRI_DEMO_MODE", "false")
    from ssri_model.api.app import create_app

    return TestClient(create_app())


def test_get_validation_unavailable_without_ground_truth(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.get("/api/v1/subsidence/validation")
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "unavailable"
    assert body["scientific_validation_status"] == "NOT_VALIDATED"
    assert body["ground_truth_available"] is False
    assert body["report"]["metrics_computed"] is False
    assert body["report"]["readiness"] == "BLOCKED_BY_MISSING_DATA"
    # Missing metrics must not appear as fabricated zeros
    assert body["report"].get("metrics") in (None, {})
    assert "roc_auc" not in body["report"]


def test_get_validation_parses_inventory_without_scores(
    tmp_path: Path, monkeypatch
) -> None:
    inventory = {
        "schema": "ssri.subsidence_ground_truth.v1",
        "records": [
            {
                "longitude": 3.1 + i * 0.01,
                "latitude": 7.1 + i * 0.01,
                "label": i % 2,
                "source": "agency_inventory",
                "observed_date": "2020-01-01",
            }
            for i in range(10)
        ],
    }
    path = tmp_path / "validation" / "subsidence_inventory.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(inventory), encoding="utf-8")

    client = _client(tmp_path, monkeypatch)
    response = client.get(
        "/api/v1/subsidence/validation",
        params={"ground_truth_path": "validation/subsidence_inventory.json"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ground_truth_available"] is True
    assert body["outcome"] == "insufficient"
    assert body["scientific_validation_status"] == "NOT_VALIDATED"
    assert body["report"]["metrics_computed"] is False
    assert body["report"]["inventory_quality"]["n_total"] == 10
    assert body["report"]["inventory_quality"]["underpowered"] is True


def test_get_validation_rejects_path_traversal(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.get(
        "/api/v1/subsidence/validation",
        params={"ground_truth_path": "../etc/passwd"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["outcome"] == "failed"
    assert body["scientific_validation_status"] == "NOT_VALIDATED"


def test_post_validation_success_still_not_validated(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    records = []
    scores = []
    for i in range(40):
        label = 1 if i < 20 else 0
        records.append(
            {
                "longitude": 3.0 + (i % 10) * 0.6,
                "latitude": 7.0 + (i // 10) * 0.6,
                "label": label,
                "source": "peer_reviewed_inventory",
                "observed_date": "2021-06-01",
            }
        )
        scores.append(0.9 if label == 1 else 0.1)

    response = client.post(
        "/api/v1/subsidence/validation",
        json={"records": records, "scores": scores, "checkpoint_id": "test-ckpt"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] in {"success", "insufficient"}
    assert body["scientific_validation_status"] == "NOT_VALIDATED"
    assert body["report"]["metrics"]["metrics_computed"] is True
    assert body["report"]["metrics"]["roc_auc"] > 0.9
    # Must not claim scientific validation
    assert body["report"]["scientific_validation_status"] == "NOT_VALIDATED"


def test_post_validation_length_mismatch_failed(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.post(
        "/api/v1/subsidence/validation",
        json={
            "records": [
                {
                    "longitude": 3.0,
                    "latitude": 7.0,
                    "label": 1,
                    "source": "agency",
                    "observed_date": "2020-01-01",
                }
            ],
            "scores": [0.1, 0.2],
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["outcome"] == "failed"
    assert body["scientific_validation_status"] == "NOT_VALIDATED"


def test_post_validation_empty_records_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.post("/api/v1/subsidence/validation", json={"records": [], "scores": []})
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "unavailable"
    assert body["ground_truth_available"] is False
    assert body["scientific_validation_status"] == "NOT_VALIDATED"
