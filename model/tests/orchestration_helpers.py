"""Shared helpers for SSRI orchestration tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ssri_model.inference import InferenceConfig, InferenceResult
from ssri_model.inference.metadata import INFERENCE_JSON_NAME
from ssri_model.orchestration.config import JobSpec
from ssri_model.orchestration.config import BatchJobsFile
from ssri_model.orchestration.jobs import jobs_file_to_dict
from tests.inference_helpers import build_inference_inputs


def write_job_dataset(root: Path, job_id: str, *, width: int = 16, height: int = 16) -> JobSpec:
    job_root = root / job_id
    feature_path, manifest_path, statistics_path, checkpoint_path, _ = build_inference_inputs(
        job_root,
        width=width,
        height=height,
    )
    return JobSpec(
        job_id=job_id,
        checkpoint=str(checkpoint_path),
        features=str(feature_path),
        manifest=str(manifest_path),
        statistics=str(statistics_path),
    )


def write_jobs_file(path: Path, jobs: list[JobSpec], *, batch_id: str = "test-batch") -> Path:
    batch = BatchJobsFile(batch_id=batch_id, jobs=tuple(jobs))
    path.write_text(json.dumps(jobs_file_to_dict(batch)), encoding="utf-8")
    return path


def write_fake_inference_artifacts(output_dir: Path, *, height: int = 16, width: int = 16) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "prediction.tif").write_bytes(b"prediction")
    (output_dir / "confidence.tif").write_bytes(b"confidence")
    (output_dir / "probabilities.tif").write_bytes(b"probabilities")
    metadata = {
        "scientific_validation_status": "NOT_VALIDATED",
        "outputs": {
            "prediction": str(output_dir / "prediction.tif"),
            "confidence": str(output_dir / "confidence.tif"),
            "probabilities": str(output_dir / "probabilities.tif"),
        },
    }
    (output_dir / INFERENCE_JSON_NAME).write_text(json.dumps(metadata), encoding="utf-8")


def mock_run_inference(config: InferenceConfig) -> InferenceResult:
    output_dir = Path(config.output_dir)
    write_fake_inference_artifacts(output_dir)
    return InferenceResult(
        prediction=np.zeros((16, 16), dtype=np.int64),
        confidence=np.zeros((16, 16), dtype=np.float32),
        probabilities=np.zeros((3, 16, 16), dtype=np.float32),
        mask=np.ones((16, 16), dtype=bool),
        prediction_path=output_dir / "prediction.tif",
        confidence_path=output_dir / "confidence.tif",
        probabilities_path=output_dir / "probabilities.tif",
        metadata_path=output_dir / INFERENCE_JSON_NAME,
        elapsed_seconds=0.1,
    )


def failing_run_inference(_: InferenceConfig) -> InferenceResult:
    raise RuntimeError("simulated inference failure")
