"""Job validation and jobs.json loading."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ssri_model.inference import validate_inference_setup
from ssri_model.inference.checkpoint import load_inference_checkpoint
from ssri_model.orchestration.config import BatchJobsFile, JobSpec
from ssri_model.orchestration.exceptions import (
    CheckpointCompatibilityError,
    DuplicateJobIdError,
    InvalidJobSpecError,
    JobValidationError,
    PathTraversalError,
)
from ssri_model.training.device import resolve_device

_SAFE_JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def sanitize_job_id(job_id: str) -> str:
    """Return a filesystem-safe job identifier."""
    normalized = job_id.strip()
    if not normalized:
        raise InvalidJobSpecError("job_id must be non-empty")
    if ".." in normalized or "/" in normalized or "\\" in normalized:
        raise PathTraversalError(f"job_id contains unsafe path characters: {job_id!r}")
    if not _SAFE_JOB_ID_PATTERN.match(normalized):
        raise PathTraversalError(f"job_id is not a safe filesystem identifier: {job_id!r}")
    return normalized


def job_output_dir(output_root: Path, job_id: str) -> Path:
    """Return the isolated output directory for a job."""
    safe_id = sanitize_job_id(job_id)
    return output_root / "jobs" / safe_id


def validate_job_spec(job: JobSpec, *, output_root: Path | None = None) -> Path:
    """Validate one job specification and return its output directory."""
    safe_id = sanitize_job_id(job.job_id)

    if not job.checkpoint_path.is_file():
        raise JobValidationError(f"Checkpoint not found or not a file: {job.checkpoint}")
    if not job.features_path.is_file():
        raise JobValidationError(f"Feature stack not found or not a file: {job.features}")
    if not job.manifest_path.is_file():
        raise JobValidationError(f"Manifest not found or not a file: {job.manifest}")
    if not job.statistics_path.is_file():
        raise JobValidationError(f"Statistics not found or not a file: {job.statistics}")

    if job.output_dir:
        output_path = Path(job.output_dir).resolve()
        if output_root is not None:
            jobs_root = (output_root / "jobs").resolve()
            try:
                output_path.relative_to(jobs_root)
            except ValueError as exc:
                raise JobValidationError(
                    f"Job output_dir must be under {jobs_root}, received {output_path}"
                ) from exc
        return output_path

    if output_root is None:
        raise JobValidationError("output_root is required when job output_dir is not set")
    return job_output_dir(output_root, safe_id)


def validate_job_specs(jobs: list[JobSpec], *, output_root: Path) -> dict[str, Path]:
    """Validate all jobs and ensure job IDs are unique."""
    if not jobs:
        raise JobValidationError("Batch must contain at least one job")

    seen: set[str] = set()
    output_dirs: dict[str, Path] = {}
    for job in jobs:
        safe_id = sanitize_job_id(job.job_id)
        if safe_id in seen:
            raise DuplicateJobIdError(f"Duplicate job_id: {safe_id}")
        seen.add(safe_id)
        output_dirs[safe_id] = validate_job_spec(job, output_root=output_root)

    resolved_dirs = list(output_dirs.values())
    if len(resolved_dirs) != len(set(resolved_dirs)):
        raise DuplicateJobIdError("Multiple jobs resolve to the same output directory")

    return output_dirs


def validate_job_inference_setup(
    job: JobSpec,
    *,
    output_dir: Path,
    device: str = "cpu",
) -> None:
    """Validate job inputs against Stage 2.7 inference contracts."""
    inference_config = job.to_inference_config(output_dir=output_dir, device=device)  # type: ignore[arg-type]
    try:
        torch_device = resolve_device(device)  # type: ignore[arg-type]
        model, checkpoint_payload = load_inference_checkpoint(
            inference_config.checkpoint,
            device=torch_device,
        )
        validate_inference_setup(
            inference_config,
            model=model,
            checkpoint_payload=checkpoint_payload,
        )
    except Exception as exc:
        raise CheckpointCompatibilityError(str(exc)) from exc


def load_jobs_file(path: Path | str) -> BatchJobsFile:
    """Load and parse a jobs.json batch definition."""
    jobs_path = Path(path)
    if not jobs_path.is_file():
        raise JobValidationError(f"Jobs file not found: {jobs_path}")

    try:
        payload = json.loads(jobs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JobValidationError(f"Unable to read jobs file: {jobs_path}") from exc

    if not isinstance(payload, dict):
        raise JobValidationError("Jobs file must contain a JSON object")

    batch_id = payload.get("batch_id")
    if not batch_id or not str(batch_id).strip():
        raise JobValidationError("Jobs file must define a non-empty batch_id")

    raw_jobs = payload.get("jobs")
    if not isinstance(raw_jobs, list) or not raw_jobs:
        raise JobValidationError("Jobs file must contain a non-empty jobs array")

    jobs: list[JobSpec] = []
    for index, entry in enumerate(raw_jobs):
        if not isinstance(entry, dict):
            raise JobValidationError(f"Job entry at index {index} must be an object")
        try:
            jobs.append(
                JobSpec(
                    job_id=str(entry["job_id"]),
                    checkpoint=str(entry["checkpoint"]),
                    features=str(entry["features"]),
                    manifest=str(entry["manifest"]),
                    statistics=str(entry["statistics"]),
                    output_dir=str(entry.get("output_dir", "")),
                    inference_config=entry.get("inference_config"),
                    description=entry.get("description"),
                    metadata=entry.get("metadata"),
                )
            )
        except KeyError as exc:
            raise JobValidationError(
                f"Job entry at index {index} is missing required field: {exc}"
            ) from exc

    metadata = payload.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise JobValidationError("Jobs file metadata must be an object when provided")

    return BatchJobsFile(
        batch_id=str(batch_id),
        jobs=tuple(jobs),
        metadata=metadata or {},
    )


def jobs_file_to_dict(batch: BatchJobsFile) -> dict[str, Any]:
    """Serialize a BatchJobsFile to a JSON-compatible dict."""
    return {
        "batch_id": batch.batch_id,
        "jobs": [
            {
                "job_id": job.job_id,
                "checkpoint": job.checkpoint,
                "features": job.features,
                "manifest": job.manifest,
                "statistics": job.statistics,
                **({"output_dir": job.output_dir} if job.output_dir else {}),
                **({"description": job.description} if job.description else {}),
                **({"metadata": dict(job.metadata)} if job.metadata else {}),
                **(
                    {"inference_config": dict(job.inference_config)}
                    if job.inference_config
                    else {}
                ),
            }
            for job in batch.jobs
        ],
        **({"metadata": dict(batch.metadata)} if batch.metadata else {}),
    }
