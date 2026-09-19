"""Tests for SSRI batch resume behavior."""

from __future__ import annotations

from pathlib import Path

from ssri_model.orchestration import BATCH_MANIFEST_NAME, BatchConfig, BatchRunner, load_batch_manifest
from ssri_model.orchestration.cli import EXIT_SUCCESS, main
from ssri_model.orchestration.manifest import save_batch_manifest
from ssri_model.orchestration.resume import apply_resume_state, verify_job_artifacts
from ssri_model.orchestration.status import summarize_batch
from tests.orchestration_helpers import (
    mock_run_inference,
    write_fake_inference_artifacts,
    write_job_dataset,
)


class TestResume:
    def test_completed_job_skipped(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_root = tmp_path / "outputs"
        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu"),
            inference_runner=mock_run_inference,
        )
        runner.run([job], batch_id="resume-batch")

        call_count = {"value": 0}

        def counting_inference(config):
            call_count["value"] += 1
            return mock_run_inference(config)

        resume_runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu", resume=True),
            inference_runner=counting_inference,
        )
        result = resume_runner.run([job], batch_id="resume-batch")
        assert result.skipped_jobs == 1
        assert result.completed_jobs == 0
        assert call_count["value"] == 0

    def test_failed_job_rerun(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_root = tmp_path / "outputs"
        manifest_path = output_root / BATCH_MANIFEST_NAME

        first_runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu"),
            inference_runner=lambda _: (_ for _ in ()).throw(RuntimeError("fail")),
        )
        first_runner.run([job], batch_id="resume-failed")
        manifest = load_batch_manifest(manifest_path)
        assert manifest.jobs[0].status == "failed"

        resume_runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu", resume=True),
            inference_runner=mock_run_inference,
        )
        result = resume_runner.run([job], batch_id="resume-failed")
        assert result.completed_jobs == 1
        manifest = load_batch_manifest(manifest_path)
        assert manifest.jobs[0].status == "completed"

    def test_pending_job_executed(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_root = tmp_path / "outputs"
        from ssri_model.orchestration.manifest import initialize_manifest_from_specs

        manifest = initialize_manifest_from_specs(
            batch_id="pending-batch",
            job_specs=[(job, output_root / "jobs" / "aoi-001")],
        )
        save_batch_manifest(output_root / BATCH_MANIFEST_NAME, manifest)

        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu", resume=True),
            inference_runner=mock_run_inference,
        )
        result = runner.run([job], batch_id="pending-batch")
        assert result.completed_jobs == 1

    def test_completed_job_with_missing_artifacts_rerun(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_root = tmp_path / "outputs"
        job_output = output_root / "jobs" / "aoi-001"
        write_fake_inference_artifacts(job_output)

        from ssri_model.orchestration.manifest import initialize_manifest_from_specs

        manifest = initialize_manifest_from_specs(
            batch_id="missing-artifacts",
            job_specs=[(job, job_output)],
        )
        manifest.jobs[0].status = "completed"
        save_batch_manifest(output_root / BATCH_MANIFEST_NAME, manifest)
        (job_output / "prediction.tif").unlink()

        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu", resume=True),
            inference_runner=mock_run_inference,
        )
        result = runner.run([job], batch_id="missing-artifacts")
        assert result.completed_jobs == 1

    def test_corrupted_artifact_rerun(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_root = tmp_path / "outputs"
        job_output = output_root / "jobs" / "aoi-001"
        write_fake_inference_artifacts(job_output)
        (job_output / "inference.json").write_text("{not-json", encoding="utf-8")

        from ssri_model.orchestration.manifest import initialize_manifest_from_specs

        manifest = initialize_manifest_from_specs(
            batch_id="corrupt-artifacts",
            job_specs=[(job, job_output)],
        )
        manifest.jobs[0].status = "completed"
        save_batch_manifest(output_root / BATCH_MANIFEST_NAME, manifest)

        valid, reason = verify_job_artifacts(job_output)
        assert valid is False
        assert reason is not None

        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu", resume=True),
            inference_runner=mock_run_inference,
        )
        result = runner.run([job], batch_id="corrupt-artifacts")
        assert result.completed_jobs == 1

    def test_idempotent_second_run(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_root = tmp_path / "outputs"
        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu"),
            inference_runner=mock_run_inference,
        )
        runner.run([job], batch_id="idempotent")

        resume_runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu", resume=True),
            inference_runner=mock_run_inference,
        )
        result = resume_runner.run([job], batch_id="idempotent")
        summary = summarize_batch(load_batch_manifest(output_root / BATCH_MANIFEST_NAME))
        assert result.skipped_jobs == 1
        assert result.completed_jobs == 0
        assert summary.skipped == 1

    def test_cli_resume(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_root = tmp_path / "outputs"
        runner = BatchRunner(
            BatchConfig(output_root=str(output_root), device="cpu"),
            inference_runner=mock_run_inference,
        )
        runner.run([job], batch_id="cli-resume")
        code = main(["resume", "--manifest", str(output_root / BATCH_MANIFEST_NAME)])
        assert code == EXIT_SUCCESS

    def test_apply_resume_state_marks_skipped(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_root = tmp_path / "outputs"
        job_output = output_root / "jobs" / "aoi-001"
        write_fake_inference_artifacts(job_output)
        from ssri_model.orchestration.manifest import initialize_manifest_from_specs

        manifest = initialize_manifest_from_specs(
            batch_id="apply-resume",
            job_specs=[(job, job_output)],
        )
        manifest.jobs[0].status = "completed"
        updated = apply_resume_state(manifest, output_root)
        assert updated.jobs[0].status == "skipped"
