"""Assess GeoTIFF URL + conditioning_features response contract."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.architecture import SSRIModelConfig
from ssri_model.ml.constants import CHANNEL_COUNT
from ssri_model.release_shell.channel_schema import CHANNEL_NAMES_V2
from tests.api_helpers import build_api_config
from tests.inference_helpers import save_inference_checkpoint


def test_assess_returns_conditioning_and_geotiff_url(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "development")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_ROOT", str(tmp_path / "objects"))
    ckpt = save_inference_checkpoint(
        tmp_path / "service-outputs" / "best.pt",
        model_config=SSRIModelConfig(base_channels=8, num_encoder_stages=2, dropout=0.0),
        dataset_identity={"name": "assess-cap", "version": "0"},
    )
    feats = tmp_path / "features.npy"
    stack = np.zeros((CHANNEL_COUNT, 8, 8), dtype=np.float32)
    np.save(feats, stack)
    client = TestClient(create_app(build_api_config(tmp_path)))
    response = client.post(
        "/api/v1/assess",
        json={
            "checkpoint": str(ckpt),
            "features": str(feats),
            "point": {"latitude": 6.5244, "longitude": 3.3792},
            "hazards": ["subsidence", "landslide"],
            "produce_geotiff": True,
            "mc_samples": 2,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(p["hazard_type"] for p in body["hazard_profiles"]) == {
        "subsidence",
        "landslide",
    }
    layers = body["conditioning_features"]["layers"]
    assert layers["overburden_thickness"]["status"] == "unavailable"
    assert layers["lineament_density"]["status"] == "unavailable"
    assert body["spatial_output_url"]
    assert body["spatial_output_hazard"] == "subsidence"
    assert body["spatial_output_expires_seconds"] is not None
    assert body["spatial_output_georef_quality"] in {
        "placeholder_origin",
        "acquisition_grid",
    }
    assessment_id = body["assessment_id"]
    spatial = client.get(f"/api/v1/assess/history/{assessment_id}/spatial")
    assert spatial.status_code == 200, spatial.text
    assert "image/tiff" in spatial.headers.get("content-type", "")
    assert len(spatial.content) > 100
    assert spatial.content[:2] in (b"II", b"MM")  # TIFF little/big endian magic
    assert spatial.headers.get("X-SSRI-Assessment-Id") == assessment_id

    missing = client.get("/api/v1/assess/history/assess-doesnotexist000/spatial")
    assert missing.status_code in {400, 404, 422}


def test_assess_v2_stack_exposes_available_overburden(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "development")
    ckpt = save_inference_checkpoint(
        tmp_path / "service-outputs" / "v2.pt",
        model_config=SSRIModelConfig(
            in_channels=16, base_channels=8, num_encoder_stages=2, dropout=0.0
        ),
        dataset_identity={"name": "assess-v2", "version": "0"},
    )
    feats = tmp_path / "features16.npy"
    stack = np.zeros((16, 8, 8), dtype=np.float32)
    stack[13, 4, 4] = 18.0
    stack[14, 4, 4] = 0.25
    stack[15, 4, 4] = 120.0
    np.save(feats, stack)
    client = TestClient(create_app(build_api_config(tmp_path)))
    response = client.post(
        "/api/v1/assess",
        json={
            "checkpoint": str(ckpt),
            "features": str(feats),
            "hazards": ["sinkhole"],
            "mc_samples": 2,
        },
    )
    assert response.status_code == 200, response.text
    layers = response.json()["conditioning_features"]["layers"]
    assert layers["overburden_thickness"]["status"] == "available"
    assert layers["overburden_thickness"]["value"] == 18.0
    assert layers["lineament_density"]["status"] == "available"
    assert layers["lineament_distance"]["status"] == "available"
    # Offline path without point uses centre sampling; names should resolve as v2.
    assert response.json()["conditioning_features"]["channel_names"] == list(CHANNEL_NAMES_V2)
