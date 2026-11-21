"""Assessment checkpoint resolution via active registry / model_id."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.api.routes.assess import (
    _NO_PRODUCTION_CHECKPOINT_MESSAGE,
    resolve_assessment_checkpoint,
)
from ssri_model.auth.dependencies import development_principal
from ssri_model.manual_training.registry import ModelRegistry
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.ml.constants import CHANNEL_COUNT
from tests.api_helpers import build_api_config
from tests.inference_helpers import save_inference_checkpoint

_DEV = development_principal()


def _register_and_activate(tmp_path: Path, *, model_id: str = "model-a") -> Path:
    output_root = tmp_path / "service-outputs"
    storage = TrainingStorage(str(output_root))
    registry = ModelRegistry(storage)
    dest_dir = storage.models_dir / model_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    ckpt = dest_dir / "best.pt"
    save_inference_checkpoint(ckpt)
    index = {
        "models": [
            {
                "model_id": model_id,
                "name": "Promoted Stage 2.5",
                "created_at": "2026-01-01T00:00:00+00:00",
                "dataset_id": "ds-1",
                "dataset_name": "registry-fixture",
                "checkpoint_path": str(ckpt.resolve()),
                "experiment_dir": str(dest_dir.resolve()),
                "job_id": None,
                "training_metrics": {},
                "evaluation_status": "training_metrics_only",
                "scientific_validation_status": "NOT_VALIDATED",
                "active": False,
                "notes": "",
            }
        ]
    }
    (storage.models_dir / "registry.json").write_text(
        json.dumps(index, indent=2), encoding="utf-8"
    )
    registry.activate(model_id)
    return ckpt


def test_resolve_uses_active_registry(tmp_path: Path) -> None:
    ckpt = _register_and_activate(tmp_path)
    resolved, source = resolve_assessment_checkpoint(
        checkpoint=None,
        model_id=None,
        output_root=tmp_path / "service-outputs",
        principal=_DEV,
    )
    assert source == "active_registry"
    assert Path(resolved).resolve() == ckpt.resolve()


def test_resolve_uses_model_id_without_client_path(tmp_path: Path) -> None:
    # Register two models; activate A; select B via model_id (operator).
    ckpt_a = _register_and_activate(tmp_path, model_id="model-a")
    storage = TrainingStorage(str(tmp_path / "service-outputs"))
    registry = ModelRegistry(storage)
    dest_dir = storage.models_dir / "model-b"
    dest_dir.mkdir(parents=True, exist_ok=True)
    ckpt_b = dest_dir / "best.pt"
    save_inference_checkpoint(ckpt_b)
    index = json.loads((storage.models_dir / "registry.json").read_text(encoding="utf-8"))
    index["models"].append(
        {
            "model_id": "model-b",
            "name": "Historic",
            "created_at": "2026-01-01T00:00:00+00:00",
            "dataset_id": "ds-2",
            "dataset_name": "registry-fixture",
            "checkpoint_path": str(ckpt_b.resolve()),
            "experiment_dir": str(dest_dir.resolve()),
            "job_id": None,
            "training_metrics": {},
            "evaluation_status": "training_metrics_only",
            "scientific_validation_status": "NOT_VALIDATED",
            "active": False,
            "notes": "",
        }
    )
    (storage.models_dir / "registry.json").write_text(
        json.dumps(index, indent=2), encoding="utf-8"
    )
    assert registry.get_active_model_id() == "model-a"
    assert Path(ckpt_a).is_file()
    resolved, source = resolve_assessment_checkpoint(
        checkpoint=None,
        model_id="model-b",
        output_root=tmp_path / "service-outputs",
        principal=_DEV,
    )
    assert source == "model_id"
    assert Path(resolved).resolve() == ckpt_b.resolve()


def test_resolve_missing_active_is_actionable(tmp_path: Path) -> None:
    output_root = tmp_path / "service-outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    with pytest.raises(Exception) as excinfo:
        resolve_assessment_checkpoint(
            checkpoint=None,
            model_id=None,
            output_root=output_root,
            principal=_DEV,
        )
    assert "No valid production checkpoint" in str(excinfo.value)


def test_resolve_invalid_model_id(tmp_path: Path) -> None:
    _register_and_activate(tmp_path)
    with pytest.raises(Exception) as excinfo:
        resolve_assessment_checkpoint(
            checkpoint=None,
            model_id="missing-model",
            output_root=tmp_path / "service-outputs",
            principal=_DEV,
        )
    assert "not found" in str(excinfo.value).lower()


def test_resolve_unavailable_active_checkpoint(tmp_path: Path) -> None:
    ckpt = _register_and_activate(tmp_path)
    ckpt.unlink()
    with pytest.raises(Exception) as excinfo:
        resolve_assessment_checkpoint(
            checkpoint=None,
            model_id=None,
            output_root=tmp_path / "service-outputs",
            principal=_DEV,
        )
    assert "unavailable" in str(excinfo.value).lower()


def test_assess_uses_active_registry_without_client_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SSRI_RELEASE_SHELL", raising=False)
    ckpt = _register_and_activate(tmp_path)
    features = tmp_path / "features.npy"
    np.save(features, np.zeros((CHANNEL_COUNT, 8, 8), dtype=np.float32))
    client = TestClient(create_app(build_api_config(tmp_path)))

    response = client.post(
        "/api/v1/assess",
        json={"features": str(features)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert any(
        note == "checkpoint_source=active_registry" for note in body.get("notes", [])
    )
    assert len(body["hazard_profiles"]) == 3
    names = {p["hazard_type"] for p in body["hazard_profiles"]}
    assert names == {"subsidence", "landslide", "sinkhole"}
    assert Path(ckpt).is_file()


def test_assess_missing_checkpoint_message_when_no_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SSRI_RELEASE_SHELL", raising=False)
    client = TestClient(create_app(build_api_config(tmp_path)))
    response = client.post(
        "/api/v1/assess",
        json={"point": {"latitude": 6.52, "longitude": 3.38}},
    )
    assert response.status_code == 400
    detail = str(response.json())
    assert "No valid production checkpoint" in detail
    assert _NO_PRODUCTION_CHECKPOINT_MESSAGE.split(".")[0] in detail


def test_assess_invalid_client_checkpoint_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SSRI_RELEASE_SHELL", raising=False)
    features = tmp_path / "features.npy"
    np.save(features, np.zeros((CHANNEL_COUNT, 8, 8), dtype=np.float32))
    client = TestClient(create_app(build_api_config(tmp_path)))
    response = client.post(
        "/api/v1/assess",
        json={
            "features": str(features),
            "checkpoint": str(tmp_path / "does-not-exist.pt"),
        },
    )
    assert response.status_code == 400
    detail = str(response.json()).lower()
    assert "not found" in detail or "outside the allowed storage root" in detail


def test_assess_rejects_16ch_stack_on_13ch_active_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SSRI_RELEASE_SHELL", raising=False)
    _register_and_activate(tmp_path)
    features = tmp_path / "features16.npy"
    np.save(features, np.zeros((16, 8, 8), dtype=np.float32))
    client = TestClient(create_app(build_api_config(tmp_path)))
    response = client.post(
        "/api/v1/assess",
        json={"features": str(features)},
    )
    assert response.status_code == 400
    detail = str(response.json()).lower()
    assert "16" in detail and "13" in detail
    assert "channel" in detail


def test_active_model_endpoint_reports_availability(tmp_path: Path) -> None:
    _register_and_activate(tmp_path)
    client = TestClient(create_app(build_api_config(tmp_path)))
    response = client.get("/api/v1/training/models/active")
    assert response.status_code == 200
    body = response.json()
    assert body["checkpoint_available"] is True
    assert body["model_id"] == "model-a"
    assert body["active"]["scientific_validation_status"] == "NOT_VALIDATED"


def test_client_path_still_preferred_over_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SSRI_RELEASE_SHELL", raising=False)
    _register_and_activate(tmp_path)
    # Operator override paths must remain under the service output root.
    other = tmp_path / "service-outputs" / "operator-override" / "other.pt"
    other.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        tmp_path / "service-outputs" / "training" / "models" / "model-a" / "best.pt",
        other,
    )
    features = tmp_path / "features.npy"
    np.save(features, np.zeros((CHANNEL_COUNT, 8, 8), dtype=np.float32))
    client = TestClient(create_app(build_api_config(tmp_path)))
    response = client.post(
        "/api/v1/assess",
        json={"features": str(features), "checkpoint": str(other)},
    )
    assert response.status_code == 200, response.text
    assert any(
        note == "checkpoint_source=client_path" for note in response.json().get("notes", [])
    )
