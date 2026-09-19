"""Batch and job status reporting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ssri_model.orchestration.exceptions import BatchManifestError
from ssri_model.orchestration.manifest import BatchManifest, JobStatus, load_batch_manifest

BatchStatusName = Literal[
    "pending",
    "running",
    "completed",
    "completed_with_errors",
    "failed",
]


@dataclass(frozen=True)
class BatchSummary:
    """Aggregate counts for a batch manifest."""

    total: int
    pending: int
    running: int
    completed: int
    failed: int
    skipped: int

    def to_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "pending": self.pending,
            "running": self.running,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
        }


@dataclass(frozen=True)
class JobStatusResult:
    """Status information for one job."""

    job_id: str
    status: JobStatus
    output_dir: str
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "output_dir": self.output_dir,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class BatchStatusResult:
    """Status information for one batch."""

    batch_id: str
    status: BatchStatusName
    summary: BatchSummary
    manifest_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "batch_id": self.batch_id,
            "status": self.status,
            "summary": self.summary.to_dict(),
            "manifest_path": self.manifest_path,
        }


def summarize_batch(manifest: BatchManifest) -> BatchSummary:
    counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0, "skipped": 0}
    for record in manifest.jobs:
        status = record.status
        if status not in counts:
            raise BatchManifestError(f"Unknown job status: {status}")
        counts[status] += 1
    return BatchSummary(
        total=len(manifest.jobs),
        pending=counts["pending"],
        running=counts["running"],
        completed=counts["completed"],
        failed=counts["failed"],
        skipped=counts["skipped"],
    )


def get_job_status(manifest: BatchManifest, job_id: str) -> JobStatusResult:
    for record in manifest.jobs:
        if record.job_id == job_id:
            return JobStatusResult(
                job_id=record.job_id,
                status=record.status,
                output_dir=record.output_dir,
                error_type=record.error_type,
                error_message=record.error_message or record.error,
            )
    raise BatchManifestError(f"Job not found: {job_id}")


def get_batch_status(manifest_path: Path | str) -> BatchStatusResult:
    manifest = load_batch_manifest(manifest_path)
    return BatchStatusResult(
        batch_id=manifest.batch_id,
        status=manifest.status,
        summary=summarize_batch(manifest),
        manifest_path=str(manifest_path),
    )
