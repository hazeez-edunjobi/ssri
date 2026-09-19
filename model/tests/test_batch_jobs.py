"""Tests for SSRI batch job execution."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ssri_model.orchestration import (
    BATCH_MANIFEST_NAME,
    BatchConfig,
    BatchExistsError,
    BatchRunner,
    load_batch_manifest,
)
from ssri_model.orchestration.cli import EXIT_COMPLETED_WITH_ERRORS, EXIT_INVALID_CONFIG, EXIT_SUCCESS, main
from ssri_model.orchestration.manifest import save_batch_manifest
from ssri_model.orchestration.status import get_batch_status
from tests.orchestration_helpers import (
    failing_run_inference,
    mock_run_inference,
    write_job_dataset,
    write_jobs_file,
)


class TestBatchRunner:
    def test_single_successful_job(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_root = tmp_path / "outputs"
        config = BatchConfig(output_root=str(output_root), device="cpu")
        runner = BatchRunner(config, inference_runner=mock_run_inference)
        result = runner.run([job], batch_id="batch-001")

        assert result.status == "completed"
        assert result.completed_jobs == 1
        assert result.failed_jobs == 0
        assert (output_root / "jobs" / "aoi-001" / "prediction.tif").exists()
        assert (output_root / BATCH_MANIFEST_NAME).exists()

    def test_multiple_successful_jobs(self, tmp_path: Path) -> None:
        jobs = [
            write_job_dataset(tmp_path, "aoi-001"),
            write_job_dataset(tmp_path / "two", "aoi-002"),
        ]
        output_root = tmp_path / "outputs"
        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu"),
            inference_runner=mock_run_inference,
        )
        result = runner.run(jobs, batch_id="batch-multi")
        assert result.total_jobs == 2
        assert result.completed_jobs == 2
        assert result.failed_jobs == 0

    def test_one_failed_job_with_continuation(self, tmp_path: Path) -> None:
        jobs = [
            write_job_dataset(tmp_path, "aoi-001"),
            write_job_dataset(tmp_path / "two", "aoi-002"),
        ]
        output_root = tmp_path / "outputs"

        def selective_inference(config):
            if "aoi-001" in config.output_dir:
                raise RuntimeError("boom")
            return mock_run_inference(config)

        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu", continue_on_error=True),
            inference_runner=selective_inference,
        )
        result = runner.run(jobs, batch_id="batch-errors")
        assert result.status == "completed_with_errors"
        assert result.failed_jobs == 1
        assert result.completed_jobs == 1

    def test_fail_fast(self, tmp_path: Path) -> None:
        jobs = [
            write_job_dataset(tmp_path, "aoi-001"),
            write_job_dataset(tmp_path / "two", "aoi-002"),
            write_job_dataset(tmp_path / "three", "aoi-003"),
        ]
        output_root = tmp_path / "outputs"

        call_count = {"value": 0}

        def counting_inference(config):
            call_count["value"] += 1
            if call_count["value"] == 1:
                raise RuntimeError("first failure")
            return mock_run_inference(config)

        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu", fail_fast=True),
            inference_runner=counting_inference,
        )
        result = runner.run(jobs, batch_id="batch-fail-fast")
        assert result.failed_jobs == 1
        assert result.skipped_jobs >= 1

    def test_status_transitions(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_root = tmp_path / "outputs"
        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu"),
            inference_runner=mock_run_inference,
        )
        runner.run([job], batch_id="batch-status")
        manifest = load_batch_manifest(output_root / BATCH_MANIFEST_NAME)
        assert manifest.status == "completed"
        assert manifest.jobs[0].status == "completed"
        assert manifest.jobs[0].prediction is not None

    def test_summary_counts(self, tmp_path: Path) -> None:
        jobs = [
            write_job_dataset(tmp_path, "aoi-001"),
            write_job_dataset(tmp_path / "two", "aoi-002"),
        ]
        output_root = tmp_path / "outputs"
        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu"),
            inference_runner=mock_run_inference,
        )
        runner.run(jobs, batch_id="batch-summary")
        status = get_batch_status(output_root / BATCH_MANIFEST_NAME)
        assert status.summary.total == 2
        assert status.summary.completed == 2

    def test_overwrite_protection(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_root = tmp_path / "outputs"
        output_root.mkdir(parents=True)
        (output_root / BATCH_MANIFEST_NAME).write_text("{}", encoding="utf-8")
        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu"),
            inference_runner=mock_run_inference,
        )
        with pytest.raises(BatchExistsError):
            runner.run([job], batch_id="batch-existing")

    def test_job_output_isolation(self, tmp_path: Path) -> None:
        jobs = [
            write_job_dataset(tmp_path, "aoi-001"),
            write_job_dataset(tmp_path / "two", "aoi-002"),
        ]
        output_root = tmp_path / "outputs"
        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu"),
            inference_runner=mock_run_inference,
        )
        runner.run(jobs, batch_id="batch-isolation")
        first = output_root / "jobs" / "aoi-001" / "prediction.tif"
        second = output_root / "jobs" / "aoi-002" / "prediction.tif"
        assert first.exists()
        assert second.exists()
        assert first != second

    def test_manifest_atomic_write(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_root = tmp_path / "outputs"
        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu"),
            inference_runner=mock_run_inference,
        )
        runner.run([job], batch_id="batch-atomic")
        manifest_path = output_root / BATCH_MANIFEST_NAME
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert payload["batch_id"] == "batch-atomic"
        assert manifest_path.with_name(manifest_path.name + ".tmp").exists() is False

    def test_failed_job_records_error(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_root = tmp_path / "outputs"
        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu"),
            inference_runner=failing_run_inference,
        )
        result = runner.run([job], batch_id="batch-failed")
        assert result.failed_jobs == 1
        manifest = load_batch_manifest(output_root / BATCH_MANIFEST_NAME)
        assert manifest.jobs[0].error_type == "RuntimeError"
        assert "simulated inference failure" in (manifest.jobs[0].error_message or "")


class TestBatchCLI:
    def test_cli_run_success(self, tmp_path: Path) -> None:
        jobs = [
            write_job_dataset(tmp_path, "aoi-001"),
            write_job_dataset(tmp_path / "two", "aoi-002"),
        ]
        jobs_path = write_jobs_file(tmp_path / "jobs.json", jobs, batch_id="cli-batch")
        output_root = tmp_path / "outputs"
        with patch("ssri_model.orchestration.cli.BatchRunner") as mock_runner_cls:
            mock_runner_cls.return_value.run.return_value.status = "completed"
            code = main(["run", "--jobs", str(jobs_path), "--output-root", str(output_root)])
        assert code == EXIT_SUCCESS

    def test_cli_status(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_root = tmp_path / "outputs"
        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu"),
            inference_runner=mock_run_inference,
        )
        runner.run([job], batch_id="cli-status")
        code = main(["status", "--manifest", str(output_root / BATCH_MANIFEST_NAME)])
        assert code == EXIT_SUCCESS

    def test_cli_invalid_jobs_file(self, tmp_path: Path) -> None:
        bad_jobs = tmp_path / "jobs.json"
        bad_jobs.write_text("{}", encoding="utf-8")
        code = main(["run", "--jobs", str(bad_jobs), "--output-root", str(tmp_path / "out")])
        assert code == EXIT_INVALID_CONFIG

    def test_cli_completed_with_errors_exit_code(self, tmp_path: Path) -> None:
        output_root = tmp_path / "outputs"
        output_root.mkdir()
        from ssri_model.orchestration.manifest import initialize_manifest_from_specs

        job = write_job_dataset(tmp_path, "aoi-001")
        manifest = initialize_manifest_from_specs(
            batch_id="err-batch",
            job_specs=[(job, output_root / "jobs" / "aoi-001")],
        )
        manifest.status = "completed_with_errors"
        save_batch_manifest(output_root / BATCH_MANIFEST_NAME, manifest)
        code = main(["status", "--manifest", str(output_root / BATCH_MANIFEST_NAME)])
        assert code == EXIT_COMPLETED_WITH_ERRORS
