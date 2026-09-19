"""Tests for manual Stage 2.5 training workflow."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import Affine

from ssri_model.api.app import create_app
from ssri_model.evaluation.evaluator import load_evaluation_model
from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES, FEATURE_NODATA
from ssri_model.ml.normalization import NormalizationConfig
from ssri_model.ml.labels import label_class_names
from ssri_model.manual_training.registry import ModelRegistry
from ssri_model.manual_training.runner import run_manual_training
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.manual_training.validation import validate_training_dataset
from tests.api_helpers import build_api_config


def _write_sample(sample_dir: Path, *, label_value: int = 1) -> None:
    sample_dir.mkdir(parents=True, exist_ok=True)
    height, width = 16, 16
    tensor = np.stack(
        [np.full((height, width), float(i + 1), dtype=np.float64) for i in range(CHANNEL_COUNT)],
        axis=0,
    )
    np.save(sample_dir / "feature_stack.npy", tensor)
    transform = Affine(30.0, 0.0, 500000.0, 0.0, -30.0, 4100000.0)
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:32613",
        "transform": transform,
        "nodata": FEATURE_NODATA,
    }
    with rasterio.open(sample_dir / "label.tif", "w", **profile) as dataset:
        dataset.write(np.full((height, width), float(label_value), dtype=np.float32), 1)
    metadata = {
        "sample_id": sample_dir.name,
        "aoi": {"bbox_wgs84": {"min_lon": -1, "min_lat": 50, "max_lon": 1, "max_lat": 52}},
        "acquisition": {"start_date": "2024-01-01", "end_date": "2024-02-01"},
        "resolution_m": 30.0,
        "crs": "EPSG:32613",
        "sources": {"dem": "COP30"},
        "package_version": "0.1.0",
        "created_at": "2026-09-19T00:00:00+00:00",
    }
    (sample_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (sample_dir / "preview.png").write_bytes(b"\x89PNG\r\n\x1a\n")


def _write_valid_dataset(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    train_ids = ["train-a", "train-b"]
    val_ids = ["val-a"]
    for sample_id in train_ids:
        _write_sample(root / "train" / sample_id, label_value=1)
    for sample_id in val_ids:
        _write_sample(root / "validation" / sample_id, label_value=0)

    manifest = {
        "dataset_name": "manual-test",
        "version": "0.1.0",
        "created_at": "2026-09-19T00:00:00+00:00",
        "channels": list(CHANNEL_NAMES),
        "label_classes": list(label_class_names()),
        "resolution": 30.0,
        "crs": "EPSG:32613",
        "normalization": NormalizationConfig.default().as_dict(),
        "train_count": len(train_ids),
        "validation_count": len(val_ids),
        "test_count": 0,
        "splits": {"train": train_ids, "validation": val_ids, "test": []},
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    channel_stats = {
        name: {
            "min": 0.0,
            "max": 1.0,
            "mean": 0.5,
            "std": 1.0,
            "valid_count": 100,
            "nodata_count": 0,
        }
        for name in CHANNEL_NAMES
    }
    statistics = {
        "sample_count": 3,
        "train_count": 2,
        "validation_count": 1,
        "test_count": 0,
        "channel_names": list(CHANNEL_NAMES),
        "channel_stats": channel_stats,
        "label_present_count": 3,
        "created_at": "2026-09-19T00:00:00+00:00",
    }
    (root / "statistics.json").write_text(json.dumps(statistics), encoding="utf-8")
    return root


def _zip_dir(source: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, arcname=str(path.relative_to(source)))
    return buffer.getvalue()


def test_validate_accepts_valid_dataset(tmp_path: Path) -> None:
    root = _write_valid_dataset(tmp_path / "ds")
    preview = validate_training_dataset(root)
    assert preview.validation_status == "passed"
    assert preview.channel_count == CHANNEL_COUNT
    assert preview.train_count == 2
    assert preview.validation_count == 1


def test_validate_rejects_wrong_channel_count(tmp_path: Path) -> None:
    root = _write_valid_dataset(tmp_path / "ds")
    bad = root / "train" / "train-a" / "feature_stack.npy"
    np.save(bad, np.zeros((11, 16, 16), dtype=np.float64))
    preview = validate_training_dataset(root)
    assert preview.validation_status == "failed"
    assert any("11 channels" in error for error in preview.errors)


def test_validate_rejects_empty_validation_split(tmp_path: Path) -> None:
    root = _write_valid_dataset(tmp_path / "ds")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest["splits"]["validation"] = []
    manifest["validation_count"] = 0
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    preview = validate_training_dataset(root)
    assert preview.validation_status == "failed"
    assert any("Validation split is empty" in error for error in preview.errors)


def test_manual_training_produces_loadable_checkpoint(tmp_path: Path) -> None:
    dataset_root = _write_valid_dataset(tmp_path / "raw-ds")
    storage = TrainingStorage(tmp_path / "outputs")
    record = storage.create_dataset(name="unit-train")
    # Copy dataset into storage data root
    import shutil

    shutil.rmtree(record.root_path)
    shutil.copytree(dataset_root, record.root_path)
    record.root_path = str(Path(record.root_path))
    storage.save_dataset(record)
    registry = ModelRegistry(storage)

    result = run_manual_training(
        storage=storage,
        registry=registry,
        dataset_id=record.dataset_id,
        run_id="run_test",
        epochs=1,
        batch_size=1,
        learning_rate=1e-3,
        seed=0,
        device="cpu",
    )
    checkpoint = Path(result["checkpoint_path"])
    assert checkpoint.exists()
    # Must not overwrite a sibling "global" model file
    assert "models" in str(checkpoint)
    model = load_evaluation_model(checkpoint, device="cpu")
    assert model is not None

    # Promote without destroying other artifacts
    promoted = registry.activate(result["model_id"])
    assert Path(promoted.checkpoint_path).exists()
    assert registry.get_active_checkpoint() == promoted.checkpoint_path


def test_training_api_upload_validate_and_start(tmp_path: Path) -> None:
    dataset_root = _write_valid_dataset(tmp_path / "api-ds")
    zip_bytes = _zip_dir(dataset_root)
    client = TestClient(create_app(build_api_config(tmp_path)))

    created = client.post(
        "/api/v1/training/datasets",
        json={"name": "api-dataset", "description": "test"},
    )
    assert created.status_code == 201
    dataset_id = created.json()["dataset"]["dataset_id"]

    uploaded = client.post(
        f"/api/v1/training/datasets/{dataset_id}/upload",
        files={"file": ("dataset.zip", zip_bytes, "application/zip")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["validation_status"] == "passed"

    reqs = client.get("/api/v1/training/requirements")
    assert reqs.status_code == 200
    assert reqs.json()["channels"] == CHANNEL_COUNT

    started = client.post(
        "/api/v1/training/jobs",
        json={
            "dataset_id": dataset_id,
            "epochs": 1,
            "batch_size": 1,
            "learning_rate": 0.001,
            "seed": 1,
            "device": "cpu",
        },
    )
    assert started.status_code == 202
    job_id = started.json()["job_id"]

    # Local executor runs in background thread — poll briefly
    import time

    final = None
    for _ in range(60):
        status = client.get(f"/api/v1/training/jobs/{job_id}")
        assert status.status_code == 200
        final = status.json()
        if final["status"] in {"completed", "failed"}:
            break
        time.sleep(0.5)

    assert final is not None
    assert final["status"] == "completed", final
    assert final["result"]["checkpoint_path"]
    assert final["scientific_validation_status"] == "NOT_VALIDATED"

    models = client.get("/api/v1/training/models")
    assert models.status_code == 200
    assert len(models.json()["models"]) >= 1
    model_id = models.json()["models"][-1]["model_id"]

    activated = client.post(
        "/api/v1/training/models/activate",
        json={"model_id": model_id},
    )
    assert activated.status_code == 200
    active = client.get("/api/v1/training/models/active")
    assert active.json()["checkpoint_path"]


def test_training_route_registered(tmp_path: Path) -> None:
    app = create_app(build_api_config(tmp_path))
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/v1/training/jobs" in paths
    assert "/api/v1/training/datasets" in paths


def test_reject_path_traversal_zip(tmp_path: Path) -> None:
    from ssri_model.manual_training.exceptions import UnsafePathError
    from ssri_model.manual_training.ingest import ingest_zip_bytes

    storage = TrainingStorage(tmp_path / "out")
    record = storage.create_dataset(name="evil")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escape.txt", "nope")
    with pytest.raises(UnsafePathError):
        ingest_zip_bytes(
            storage,
            record.dataset_id,
            filename="evil.zip",
            content=buffer.getvalue(),
        )
