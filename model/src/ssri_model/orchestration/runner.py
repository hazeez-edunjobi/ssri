"""Batch inference runner for SSRI orchestration."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ssri_model.inference import InferenceResult, run_inference
from ssri_model.orchestration.config import BatchConfig, JobSpec
from ssri_model.orchestration.exceptions import (
    BatchExistsError,
    BatchManifestError,
    OrchestrationError,
)
from ssri_model.orchestration.jobs import (
    sanitize_job_id,
    validate_job_inference_setup,
    validate_job_specs,
)
from ssri_model.orchestration.manifest import (
    BatchManifest,
    JobRecord,
    batch_manifest_path,
    initialize_manifest_from_specs,
    load_batch_manifest,
    save_batch_manifest,
    utc_now_iso,
)
from ssri_model.orchestration.resume import should_skip_job
from ssri_model.orchestration.status import BatchSummary, summarize_batch

logger = logging.getLogger(__name__)

InferenceCallable = Callable[..., InferenceResult]


@dataclass
class JobResult:
    """Result from executing one batch job."""

    job_id: str
    status: str
    output_dir: str
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    prediction: str | None = None
    confidence: str | None = None
    probabilities: str | None = None
    inference_metadata: str | None = None
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "output_dir": self.output_dir,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "prediction": self.prediction,
            "confidence": self.confidence,
            "probabilities": self.probabilities,
            "inference_metadata": self.inference_metadata,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "scientific_validation_status": "NOT_VALIDATED",
        }


@dataclass
class BatchResult:
    """Structured result from a batch inference run."""

    batch_id: str
    status: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    skipped_jobs: int
    duration_seconds: float
    job_results: list[JobResult] = field(default_factory=list)
    manifest_path: str = ""
    summary: BatchSummary | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "status": self.status,
            "total_jobs": self.total_jobs,
            "completed_jobs": self.completed_jobs,
            "failed_jobs": self.failed_jobs,
            "skipped_jobs": self.skipped_jobs,
            "duration_seconds": self.duration_seconds,
            "manifest_path": self.manifest_path,
            "summary": self.summary.to_dict() if self.summary else None,
            "job_results": [result.to_dict() for result in self.job_results],
            "scientific_validation_status": "NOT_VALIDATED",
        }


class BatchRunner:
    """Execute multiple SSRI inference jobs with manifest tracking."""

    def __init__(
        self,
        config: BatchConfig,
        *,
        inference_runner: InferenceCallable | None = None,
    ) -> None:
        self.config = config
        self._run_inference = inference_runner or run_inference

    def run(
        self,
        jobs: list[JobSpec],
        *,
        batch_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> BatchResult:
        if not jobs:
            raise OrchestrationError("Batch must contain at least one job")

        output_root = self.config.output_root_path
        output_root.mkdir(parents=True, exist_ok=True)
        manifest_file = batch_manifest_path(output_root)

        resolved_batch_id = batch_id or self.config.batch_id or f"batch-{int(time.time())}"
        output_dirs = validate_job_specs(jobs, output_root=output_root)

        for job in jobs:
            safe_id = sanitize_job_id(job.job_id)
            validate_job_inference_setup(
                job,
                output_dir=output_dirs[safe_id],
                device=self.config.device,
            )

        manifest = self._prepare_manifest(
            manifest_file=manifest_file,
            batch_id=resolved_batch_id,
            jobs=jobs,
            output_dirs=output_dirs,
            metadata=metadata,
        )

        logger.info("[BATCH] Starting batch %s (%d jobs)", resolved_batch_id, len(jobs))
        manifest.status = "running"
        manifest.started_at = utc_now_iso()
        save_batch_manifest(manifest_file, manifest)

        batch_started = time.perf_counter()
        job_results: list[JobResult] = []
        fail_fast_triggered = False

        for job in jobs:
            safe_id = sanitize_job_id(job.job_id)
            output_dir = output_dirs[safe_id]
            record = self._find_record(manifest, safe_id)

            if fail_fast_triggered:
                record.status = "skipped"
                record.error = "Skipped due to fail_fast"
                job_results.append(
                    JobResult(
                        job_id=safe_id,
                        status="skipped",
                        output_dir=str(output_dir),
                        error_message=record.error,
                    )
                )
                save_batch_manifest(manifest_file, manifest)
                continue

            if should_skip_job(record, output_dir, resume=self.config.resume):
                logger.info("[JOB] %s → SKIPPED (already completed)", safe_id)
                record.status = "skipped"
                job_results.append(
                    JobResult(
                        job_id=safe_id,
                        status="skipped",
                        output_dir=str(output_dir),
                    )
                )
                save_batch_manifest(manifest_file, manifest)
                continue

            started_at = utc_now_iso()
            record.status = "running"
            record.started_at = started_at
            record.completed_at = None
            record.error = None
            record.error_type = None
            record.error_message = None
            save_batch_manifest(manifest_file, manifest)
            logger.info("[JOB] %s → RUNNING", safe_id)

            job_started = time.perf_counter()
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                inference_config = job.to_inference_config(
                    output_dir=output_dir,
                    device=self.config.device,
                )
                result = self._run_inference(inference_config)
                duration = time.perf_counter() - job_started
                completed_at = utc_now_iso()

                record.status = "completed"
                record.completed_at = completed_at
                record.duration_seconds = duration
                record.prediction = str(result.prediction_path)
                record.confidence = str(result.confidence_path)
                record.probabilities = str(result.probabilities_path)
                record.inference_metadata = str(result.metadata_path)

                job_result = JobResult(
                    job_id=safe_id,
                    status="completed",
                    output_dir=str(output_dir),
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_seconds=duration,
                    prediction=record.prediction,
                    confidence=record.confidence,
                    probabilities=record.probabilities,
                    inference_metadata=record.inference_metadata,
                )
                job_results.append(job_result)
                logger.info("[JOB] %s → COMPLETED (%.1fs)", safe_id, duration)
            except Exception as exc:
                duration = time.perf_counter() - job_started
                completed_at = utc_now_iso()
                error_type = type(exc).__name__
                error_message = str(exc)

                record.status = "failed"
                record.completed_at = completed_at
                record.duration_seconds = duration
                record.error_type = error_type
                record.error_message = error_message
                record.error = error_message

                job_results.append(
                    JobResult(
                        job_id=safe_id,
                        status="failed",
                        output_dir=str(output_dir),
                        started_at=started_at,
                        completed_at=completed_at,
                        duration_seconds=duration,
                        error_type=error_type,
                        error_message=error_message,
                    )
                )
                logger.error("[JOB] %s → FAILED\n           %s: %s", safe_id, error_type, error_message)

                save_batch_manifest(manifest_file, manifest)
                if self.config.fail_fast:
                    fail_fast_triggered = True
                if not self.config.continue_on_error:
                    manifest.status = "failed"
                    manifest.completed_at = utc_now_iso()
                    manifest.duration_seconds = time.perf_counter() - batch_started
                    save_batch_manifest(manifest_file, manifest)
                    return self._build_result(manifest, manifest_file, job_results, batch_started)

            save_batch_manifest(manifest_file, manifest)

        manifest.completed_at = utc_now_iso()
        manifest.duration_seconds = time.perf_counter() - batch_started
        summary = summarize_batch(manifest)
        if summary.failed > 0:
            manifest.status = "completed_with_errors"
        else:
            manifest.status = "completed"
        save_batch_manifest(manifest_file, manifest)

        logger.info(
            "[BATCH] %s completed=%d failed=%d skipped=%d",
            manifest.status.upper(),
            summary.completed,
            summary.failed,
            summary.skipped,
        )
        return self._build_result(manifest, manifest_file, job_results, batch_started)

    def _prepare_manifest(
        self,
        *,
        manifest_file: Path,
        batch_id: str,
        jobs: list[JobSpec],
        output_dirs: dict[str, Path],
        metadata: dict[str, Any] | None,
    ) -> BatchManifest:
        if manifest_file.exists():
            if self.config.overwrite:
                return initialize_manifest_from_specs(
                    batch_id=batch_id,
                    job_specs=[(job, output_dirs[sanitize_job_id(job.job_id)]) for job in jobs],
                    metadata=metadata,
                )
            if self.config.resume:
                manifest = load_batch_manifest(manifest_file)
                if manifest.batch_id != batch_id:
                    raise BatchManifestError(
                        f"Existing manifest batch_id {manifest.batch_id!r} "
                        f"does not match requested {batch_id!r}"
                    )
                from ssri_model.orchestration.resume import apply_resume_state

                return apply_resume_state(manifest, self.config.output_root_path)
            raise BatchExistsError(
                f"Batch output already exists at {manifest_file.parent}. "
                "Use resume=True or overwrite=True to continue."
            )

        return initialize_manifest_from_specs(
            batch_id=batch_id,
            job_specs=[(job, output_dirs[sanitize_job_id(job.job_id)]) for job in jobs],
            metadata=metadata,
        )

    @staticmethod
    def _find_record(manifest: BatchManifest, job_id: str) -> JobRecord:
        for record in manifest.jobs:
            if record.job_id == job_id:
                return record
        raise BatchManifestError(f"Job not found in manifest: {job_id}")

    @staticmethod
    def _build_result(
        manifest: BatchManifest,
        manifest_file: Path,
        job_results: list[JobResult],
        batch_started: float,
    ) -> BatchResult:
        summary = summarize_batch(manifest)
        return BatchResult(
            batch_id=manifest.batch_id,
            status=manifest.status,
            total_jobs=summary.total,
            completed_jobs=summary.completed,
            failed_jobs=summary.failed,
            skipped_jobs=summary.skipped,
            duration_seconds=time.perf_counter() - batch_started,
            job_results=job_results,
            manifest_path=str(manifest_file),
            summary=summary,
        )
