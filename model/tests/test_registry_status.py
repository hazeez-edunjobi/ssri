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
