"""Assess API echoes location provenance for offline feature assessments."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.architecture import SSRIModelConfig
from ssri_model.ml.constants import CHANNEL_COUNT
from tests.api_helpers import build_api_config
from tests.inference_helpers import save_inference_checkpoint


def test_assess_echoes_submitted_coordinates_and_grid_cell(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "development")
    ckpt = save_inference_checkpoint(
        tmp_path / "best.pt",
        model_config=SSRIModelConfig(base_channels=8, num_encoder_stages=2, dropout=0.0),
        dataset_identity={"name": "handover-coord", "version": "0"},
    )
    feats = tmp_path / "features.npy"
    np.save(feats, np.zeros((CHANNEL_COUNT, 8, 8), dtype=np.float32))
    client = TestClient(create_app(build_api_config(tmp_path)))
    lat, lon = 6.5244, 3.3792
    response = client.post(
        "/api/v1/assess",
        json={
            "checkpoint": str(ckpt),
            "features": str(feats),
            "point": {"latitude": lat, "longitude": lon},
            "mc_samples": 2,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    prov = body["location_provenance"]
    assert prov is not None
    assert prov["submitted"]["latitude"] == lat
    assert prov["submitted"]["longitude"] == lon
    assert prov["submitted_crs"] == "EPSG:4326"
    assert prov["model_grid"]["pixel_row"] is not None
    assert prov["model_grid"]["pixel_col"] is not None
    assert any(n.startswith("location_provenance=submitted=") for n in body["notes"])
    assert any(n.startswith("model_grid_pixel=") for n in body["notes"])
    # Offline features note must be present so operators know sampling source.
    assert any("Offline feature tensor" in n for n in prov["notes"])


def test_assess_rejects_invalid_point_before_inference(tmp_path: Path) -> None:
    client = TestClient(create_app(build_api_config(tmp_path)))
    response = client.post(
        "/api/v1/assess",
        json={"point": {"latitude": 120.0, "longitude": 3.0}},
    )
    assert response.status_code == 422
