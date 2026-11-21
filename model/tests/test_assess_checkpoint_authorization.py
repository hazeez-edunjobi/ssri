"""Checkpoint path / model_id / active-endpoint authorization hardening."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ssri_model.api.routes.assess import (
    resolve_assessment_checkpoint,
)
from ssri_model.auth.exceptions import AuthorizationError
from ssri_model.auth.authorization import permissions_for_role
from ssri_model.auth.models import AuthenticatedPrincipal, Role
from ssri_model.manual_training.registry import ModelRegistry
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.ml.constants import CHANNEL_COUNT
from tests.auth_helpers import auth_header, build_authenticated_api_config, create_authenticated_client
from tests.inference_helpers import save_inference_checkpoint


def _principal(role: Role) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        key_id=f"test-{role.value}",
        role=role,
        permissions=permissions_for_role(role),
        authentication_method="test",
        authenticated_at="2026-01-01T00:00:00+00:00",
    )


def _register_models(tmp_path: Path, *, activate: str = "model-a") -> Path:
    output_root = tmp_path / "service-outputs"
    storage = TrainingStorage(str(output_root))
    registry = ModelRegistry(storage)
    models = []
    for model_id, name in (("model-a", "Active"), ("model-b", "Historic")):
        dest_dir = storage.models_dir / model_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        ckpt = dest_dir / "best.pt"
        save_inference_checkpoint(ckpt)
        models.append(
            {
                "model_id": model_id,
                "name": name,
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
        )
    (storage.models_dir / "registry.json").write_text(
        json.dumps({"models": models}, indent=2), encoding="utf-8"
    )
    registry.activate(activate)
    return output_root


def test_user_cannot_supply_checkpoint_path(tmp_path: Path) -> None:
    output_root = _register_models(tmp_path)
    ckpt = output_root / "training" / "models" / "model-a" / "best.pt"
    with pytest.raises(AuthorizationError):
        resolve_assessment_checkpoint(
            checkpoint=str(ckpt),
            model_id=None,
            output_root=output_root,
            principal=_principal(Role.USER),
        )


def test_user_cannot_select_non_active_model_id(tmp_path: Path) -> None:
    output_root = _register_models(tmp_path)
    with pytest.raises(AuthorizationError):
        resolve_assessment_checkpoint(
            checkpoint=None,
            model_id="model-b",
            output_root=output_root,
            principal=_principal(Role.USER),
        )


def test_user_may_name_active_model_id(tmp_path: Path) -> None:
    output_root = _register_models(tmp_path)
    resolved, source = resolve_assessment_checkpoint(
        checkpoint=None,
        model_id="model-a",
        output_root=output_root,
        principal=_principal(Role.USER),
    )
    assert source == "active_registry"
    assert Path(resolved).name == "best.pt"


def test_operator_may_select_non_active_model_id(tmp_path: Path) -> None:
    output_root = _register_models(tmp_path)
    resolved, source = resolve_assessment_checkpoint(
        checkpoint=None,
        model_id="model-b",
        output_root=output_root,
        principal=_principal(Role.OPERATOR),
    )
    assert source == "model_id"
    assert "model-b" in resolved.replace("\\", "/")


def test_operator_path_outside_output_root_rejected(tmp_path: Path) -> None:
    output_root = _register_models(tmp_path)
    escape = tmp_path / "outside.pt"
    save_inference_checkpoint(escape)
    with pytest.raises(Exception) as excinfo:
        resolve_assessment_checkpoint(
            checkpoint=str(escape),
            model_id=None,
            output_root=output_root,
            principal=_principal(Role.OPERATOR),
        )
    assert "outside the allowed storage root" in str(excinfo.value).lower()


def test_assess_api_user_denied_checkpoint_override(tmp_path: Path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    _register_models(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    user_key, _ = keys["user"]
    assert isinstance(user_key, str)
    features = tmp_path / "features.npy"
    np.save(features, np.zeros((CHANNEL_COUNT, 8, 8), dtype=np.float32))
    ckpt = tmp_path / "service-outputs" / "training" / "models" / "model-a" / "best.pt"
    response = client.post(
        "/api/v1/assess",
        json={"features": str(features), "checkpoint": str(ckpt)},
        headers=auth_header(user_key),
    )
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
    assert "operator authorization" in body["error"]["message"].lower()
    assert "service-outputs" not in body["error"]["message"]
    assert str(ckpt) not in body["error"]["message"]


def test_assess_api_user_denied_non_active_model_id(tmp_path: Path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    _register_models(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    user_key, _ = keys["user"]
    assert isinstance(user_key, str)
    features = tmp_path / "features.npy"
    np.save(features, np.zeros((CHANNEL_COUNT, 8, 8), dtype=np.float32))
    response = client.post(
        "/api/v1/assess",
        json={"features": str(features), "model_id": "model-b"},
        headers=auth_header(user_key),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_assess_api_user_uses_active_without_path(tmp_path: Path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    _register_models(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    user_key, _ = keys["user"]
    assert isinstance(user_key, str)
    features = tmp_path / "features.npy"
    np.save(features, np.zeros((CHANNEL_COUNT, 8, 8), dtype=np.float32))
    response = client.post(
        "/api/v1/assess",
        json={"features": str(features)},
        headers=auth_header(user_key),
    )
    assert response.status_code == 200, response.text
    assert any(
        note == "checkpoint_source=active_registry"
        for note in response.json().get("notes", [])
    )


def test_assess_api_signed_out_still_rejected(tmp_path: Path) -> None:
    config, _ = build_authenticated_api_config(tmp_path, enabled=True)
    client = create_authenticated_client(tmp_path, api_config=config)
    response = client.post(
        "/api/v1/assess",
        json={"point": {"latitude": 6.5, "longitude": 3.4}},
    )
    assert response.status_code == 401


def test_assess_api_viewer_forbidden(tmp_path: Path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    viewer_key, _ = keys["viewer"]
    assert isinstance(viewer_key, str)
    response = client.post(
        "/api/v1/assess",
        json={"point": {"latitude": 6.5, "longitude": 3.4}},
        headers=auth_header(viewer_key),
    )
    assert response.status_code == 403


def test_assess_api_operator_may_use_path_under_output_root(tmp_path: Path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    _register_models(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    assert isinstance(operator_key, str)
    features = tmp_path / "features.npy"
    np.save(features, np.zeros((CHANNEL_COUNT, 8, 8), dtype=np.float32))
    ckpt = tmp_path / "service-outputs" / "training" / "models" / "model-a" / "best.pt"
    response = client.post(
        "/api/v1/assess",
        json={"features": str(features), "checkpoint": str(ckpt)},
        headers=auth_header(operator_key),
    )
    assert response.status_code == 200, response.text
    assert any(
        note == "checkpoint_source=client_path"
        for note in response.json().get("notes", [])
    )


def test_assess_api_admin_may_select_historic_model(tmp_path: Path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    _register_models(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    admin_key, _ = keys["admin"]
    assert isinstance(admin_key, str)
    features = tmp_path / "features.npy"
    np.save(features, np.zeros((CHANNEL_COUNT, 8, 8), dtype=np.float32))
    response = client.post(
        "/api/v1/assess",
        json={"features": str(features), "model_id": "model-b"},
        headers=auth_header(admin_key),
    )
    assert response.status_code == 200, response.text
    assert any(
        note == "checkpoint_source=model_id" for note in response.json().get("notes", [])
    )


def test_active_endpoint_hides_path_from_user(tmp_path: Path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    _register_models(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    user_key, _ = keys["user"]
    assert isinstance(user_key, str)
    response = client.get(
        "/api/v1/training/models/active",
        headers=auth_header(user_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["checkpoint_available"] is True
    assert body["model_id"] == "model-a"
    assert body["checkpoint_path"] is None
    assert "checkpoint_path" not in (body.get("active") or {})
    assert "experiment_dir" not in (body.get("active") or {})
    assert body["active"]["scientific_validation_status"] == "NOT_VALIDATED"


def test_active_endpoint_reveals_path_to_operator(tmp_path: Path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    _register_models(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    assert isinstance(operator_key, str)
    response = client.get(
        "/api/v1/training/models/active",
        headers=auth_header(operator_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["checkpoint_available"] is True
    assert body["checkpoint_path"]
    assert Path(body["checkpoint_path"]).is_file()
    assert "checkpoint_path" in body["active"]


def test_active_endpoint_signed_out_rejected(tmp_path: Path) -> None:
    config, _ = build_authenticated_api_config(tmp_path, enabled=True)
    client = create_authenticated_client(tmp_path, api_config=config)
    response = client.get("/api/v1/training/models/active")
    assert response.status_code == 401


def test_list_models_hides_paths_from_user(tmp_path: Path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    _register_models(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    user_key, _ = keys["user"]
    assert isinstance(user_key, str)
    response = client.get(
        "/api/v1/training/models",
        headers=auth_header(user_key),
    )
    assert response.status_code == 200
    models = response.json()["models"]
    assert len(models) >= 1
    for model in models:
        assert "checkpoint_path" not in model
        assert "experiment_dir" not in model
        assert "checkpoint_available" in model
        assert model["scientific_validation_status"] == "NOT_VALIDATED"


def test_list_models_reveals_paths_to_operator(tmp_path: Path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    _register_models(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    assert isinstance(operator_key, str)
    response = client.get(
        "/api/v1/training/models",
        headers=auth_header(operator_key),
    )
    assert response.status_code == 200
    models = response.json()["models"]
    assert models
    assert any(model.get("checkpoint_path") for model in models)
    assert any(model.get("experiment_dir") for model in models)


def test_user_session_cannot_override_checkpoint(tmp_path: Path) -> None:
    config, _ = build_authenticated_api_config(tmp_path)
    _register_models(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    client.app.state.platform_tokens = {
        "session-user-ckpt": ("user-1", "user@example.com", "user"),
    }
    features = tmp_path / "features.npy"
    np.save(features, np.zeros((CHANNEL_COUNT, 8, 8), dtype=np.float32))
    ckpt = tmp_path / "service-outputs" / "training" / "models" / "model-a" / "best.pt"
    response = client.post(
        "/api/v1/assess",
        json={"features": str(features), "checkpoint": str(ckpt)},
        headers=auth_header("session-user-ckpt"),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
