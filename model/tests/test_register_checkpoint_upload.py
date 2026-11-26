"""Operator checkpoint register/activate without retraining."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import torch
from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.architecture.config import SSRIModelConfig
from ssri_model.architecture.model import SSRIModel
from ssri_model.manual_training.registry import ModelRegistry
from ssri_model.manual_training.storage import TrainingStorage
from tests.api_helpers import build_api_config


def _write_stage25_checkpoint(path: Path) -> str:
    model = SSRIModel(
        SSRIModelConfig(
            in_channels=13,
            num_classes=3,
            base_channels=8,
            num_encoder_stages=2,
        )
    )
    payload = {
        "model_state_dict": model.state_dict(),
        "model_config": {
            "in_channels": 13,
            "num_classes": 3,
            "base_channels": 8,
            "num_encoder_stages": 2,
            "dropout": 0.0,
            "normalization": "group",
            "activation": "relu",
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(autouse=True)
def _local_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSRI_EXECUTION_MODE", "local")
    monkeypatch.delenv("SSRI_DATABASE_URL", raising=False)
    monkeypatch.delenv("SSRI_REDIS_URL", raising=False)
    monkeypatch.delenv("SSRI_CELERY_BROKER_URL", raising=False)


def test_register_checkpoint_upload_and_activate(tmp_path: Path) -> None:
    app = create_app(build_api_config(tmp_path))
    client = TestClient(app)
    ckpt = tmp_path / "best.pt"
    digest = _write_stage25_checkpoint(ckpt)

    response = client.post(
        "/api/v1/training/models/register-checkpoint",
        files={"file": ("best.pt", ckpt.read_bytes(), "application/octet-stream")},
        data={
            "model_id": "ssri-model-testupload01",
            "name": "UPLOAD-TEST",
            "expected_sha256": digest,
            "activate": "true",
            "notes": "test upload",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["activated"] is True
    assert body["model"]["model_id"] == "ssri-model-testupload01"
    assert body["model"]["scientific_validation_status"] == "NOT_VALIDATED"
    assert body["object_storage_sha256"] == digest

    registry = ModelRegistry(TrainingStorage(str(tmp_path / "service-outputs")))
    assert registry.get_active_model_id() == "ssri-model-testupload01"
    active = registry.get_model("ssri-model-testupload01")
    assert Path(active.checkpoint_path).is_file()
    assert active.scientific_validation_status == "NOT_VALIDATED"


def test_register_checkpoint_rejects_digest_mismatch(tmp_path: Path) -> None:
    app = create_app(build_api_config(tmp_path))
    client = TestClient(app)
    ckpt = tmp_path / "best.pt"
    _write_stage25_checkpoint(ckpt)

    response = client.post(
        "/api/v1/training/models/register-checkpoint",
        files={"file": ("best.pt", ckpt.read_bytes(), "application/octet-stream")},
        data={
            "model_id": "ssri-model-badsha",
            "name": "BAD",
            "expected_sha256": "0" * 64,
            "activate": "false",
        },
    )
    assert response.status_code == 400
    assert "SHA-256" in response.json()["error"]["message"]
