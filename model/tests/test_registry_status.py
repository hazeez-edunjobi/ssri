"""Tests for public model-registry readiness summaries."""

from __future__ import annotations

import json
from pathlib import Path

from ssri_model.api.registry_status import active_model_registry_status
from ssri_model.manual_training.storage import TrainingStorage
from tests.inference_helpers import save_inference_checkpoint


def test_active_model_registry_status_empty(tmp_path: Path) -> None:
    status = active_model_registry_status(tmp_path / "service-outputs")
    assert status["active_model_id"] is None
    assert status["checkpoint_available"] is False
    assert "checkpoint_path" not in status


def test_get_active_model_id_recovers_active_json_from_object_storage(
    tmp_path: Path, monkeypatch
) -> None:
    """Render disk wipe: active.json must rematerialize from R2 before /ready."""
    from ssri_model.manual_training.registry import ModelRegistry
    from ssri_model.storage import LocalObjectStorage
    from ssri_model.storage.durable import mirror_registry_metadata

    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BACKEND", "r2")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BUCKET", "ssri")
    monkeypatch.setenv(
        "SSRI_OBJECT_STORAGE_ENDPOINT", "https://example.r2.cloudflarestorage.com"
    )
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_ACCESS_KEY", "ak")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_SECRET_KEY", "sk")

    store = LocalObjectStorage(root=tmp_path / "objects")
    models_dir = tmp_path / "models"
    models_dir.mkdir(parents=True)
    (models_dir / "active.json").write_text(
        json.dumps({"model_id": "ssri-model-1c8de63cd3"}), encoding="utf-8"
    )
    (models_dir / "registry.json").write_text(
        json.dumps({"models": []}), encoding="utf-8"
    )
    mirror_registry_metadata(models_dir, storage=store)

    # Simulate Render ephemeral wipe.
    (models_dir / "active.json").unlink()
    (models_dir / "registry.json").unlink()

    # Patch durable helper to use our LocalObjectStorage stand-in.
    import ssri_model.storage.durable as durable

    monkeypatch.setattr(
        durable,
        "build_object_storage_from_env",
        lambda: store,
    )

    registry = ModelRegistry(TrainingStorage(str(tmp_path)))
    # Point registry at wiped models_dir
    registry.storage.models_dir = models_dir  # type: ignore[attr-defined]
    registry._index_path = models_dir / "registry.json"
    registry._active_path = models_dir / "active.json"

    assert registry.get_active_model_id() == "ssri-model-1c8de63cd3"
    assert (models_dir / "active.json").is_file()


def test_active_model_registry_status_promoted(tmp_path: Path) -> None:
    output_root = tmp_path / "service-outputs"
    storage = TrainingStorage(str(output_root))
    model_id = "mdl-1"
    dest = storage.models_dir / model_id
    dest.mkdir(parents=True)
    ckpt = dest / "best.pt"
    save_inference_checkpoint(ckpt)
    (storage.models_dir / "registry.json").write_text(
        json.dumps(
            {
                "models": [
                    {
                        "model_id": model_id,
                        "name": "Fixture",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "dataset_id": "ds",
                        "dataset_name": "registry-fixture",
                        "checkpoint_path": str(ckpt.resolve()),
                        "experiment_dir": str(dest.resolve()),
                        "job_id": None,
                        "training_metrics": {},
                        "evaluation_status": "training_metrics_only",
                        "scientific_validation_status": "NOT_VALIDATED",
                        "active": False,
                        "notes": "",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (storage.models_dir / "active.json").write_text(
        json.dumps(
            {
                "model_id": model_id,
                "checkpoint_path": str(ckpt.resolve()),
                "activated_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    status = active_model_registry_status(output_root)
    assert status["active_model_id"] == model_id
    assert status["checkpoint_available"] is True
    assert status["scientific_validation_status"] == "NOT_VALIDATED"
    assert "checkpoint_path" not in status
    assert str(ckpt) not in json.dumps(status)
