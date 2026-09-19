"""Shared helpers for SSRI API tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.api.config import APIConfig
from ssri_model.api.dependencies import DefaultBatchExecutor, DefaultInferenceExecutor
from ssri_model.service.config import ServiceConfig
from tests.inference_helpers import build_inference_inputs
from tests.orchestration_helpers import mock_run_inference, write_job_dataset, write_jobs_file


def build_api_config(tmp_path: Path, **overrides: object) -> APIConfig:
    output_root = tmp_path / "service-outputs"
    service_config = overrides.pop("service_config", None)
    if service_config is None:
        service_config = ServiceConfig(
            output_root=str(output_root),
            scientific_validation_required=False,
            allow_unvalidated_predictions=True,
        )
    return APIConfig(service_config=service_config, **overrides)


def build_inference_payload(
    *,
    request_id: str,
    feature: Path,
    manifest: Path,
    statistics: Path,
    checkpoint: Path,
    output_dir: str = "",
    scientific_validation_status: str = "NOT_VALIDATED",
    scientific_validation_required: bool = False,
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "checkpoint": str(checkpoint),
        "features": str(feature),
        "manifest": str(manifest),
        "statistics": str(statistics),
        "output_dir": output_dir,
        "output_format": "all",
        "scientific_validation_status": scientific_validation_status,
        "scientific_validation_required": scientific_validation_required,
    }


def create_test_client(
    tmp_path: Path,
    *,
    api_config: APIConfig | None = None,
    inference_runner=mock_run_inference,
    batch_inference_runner=mock_run_inference,
) -> TestClient:
    config = api_config or build_api_config(tmp_path)
    app = create_app(
        config,
        inference_runner=inference_runner,
        batch_inference_runner=batch_inference_runner,
    )
    return TestClient(app)


def build_inference_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "inference-inputs"
    feature, manifest, statistics, checkpoint, _ = build_inference_inputs(root)
    return feature, manifest, statistics, checkpoint


def build_batch_fixture(tmp_path: Path, *, batch_id: str = "api-batch") -> tuple[Path, Path, str]:
    jobs_root = tmp_path / "batch-jobs"
    job = write_job_dataset(jobs_root, "job-a")
    jobs_file = write_jobs_file(jobs_root / "jobs.json", [job], batch_id=batch_id)
    output_root = tmp_path / "service-outputs" / "batches" / batch_id
    return jobs_file, output_root, batch_id


class FailingInferenceExecutor(DefaultInferenceExecutor):
    def execute(self, request, *, scientific_validation_status: str, principal=None):
        raise RuntimeError("simulated internal failure at C:\\secret\\path")


class FailingBatchExecutor(DefaultBatchExecutor):
    def execute(self, request, *, scientific_validation_status: str):
        raise RuntimeError("simulated batch failure at /etc/passwd")
