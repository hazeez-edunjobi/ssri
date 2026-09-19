"""Resume support for SSRI batch orchestration."""

from __future__ import annotations

import json
from pathlib import Path

from ssri_model.inference.metadata import INFERENCE_JSON_NAME
from ssri_model.orchestration.manifest import BatchManifest, JobRecord, JobStatus

REQUIRED_ARTIFACTS = (
    "prediction.tif",
    "confidence.tif",
    "probabilities.tif",
    INFERENCE_JSON_NAME,
)


def artifact_paths(output_dir: Path) -> dict[str, Path]:
    return {name: output_dir / name for name in REQUIRED_ARTIFACTS}


def verify_job_artifacts(output_dir: Path) -> tuple[bool, str | None]:
    """Verify that all required job artifacts exist and are minimally valid."""
    if not output_dir.is_dir():
        return False, f"Output directory missing: {output_dir}"

    for artifact_name in REQUIRED_ARTIFACTS:
        artifact_path = output_dir / artifact_name
        if not artifact_path.is_file():
            return False, f"Missing artifact: {artifact_name}"
        if artifact_path.stat().st_size <= 0:
            return False, f"Empty artifact: {artifact_name}"

    inference_path = output_dir / INFERENCE_JSON_NAME
    try:
        payload = json.loads(inference_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"Invalid inference metadata: {exc}"

    if not isinstance(payload, dict):
        return False, "Inference metadata must be a JSON object"

    return True, None


def resolve_job_status_on_resume(record: JobRecord, output_dir: Path) -> JobStatus:
    """Determine whether a manifest job should run, skip, or remain pending."""
    if record.status in ("completed", "skipped"):
        valid, _ = verify_job_artifacts(output_dir)
        if valid:
            return "skipped"
        return "pending"

    if record.status == "failed":
        return "pending"

    if record.status == "running":
        valid, _ = verify_job_artifacts(output_dir)
        if valid:
            return "skipped"
        return "pending"

    return record.status


def should_skip_job(record: JobRecord, output_dir: Path, *, resume: bool) -> bool:
    """Return True when a job should be skipped during resume."""
    if not resume:
        return False
    return resolve_job_status_on_resume(record, output_dir) == "skipped"


def apply_resume_state(manifest: BatchManifest, output_root: Path) -> BatchManifest:
    """Update manifest job statuses based on artifact verification."""
    jobs_root = output_root / "jobs"
    for record in manifest.jobs:
        output_dir = Path(record.output_dir) if record.output_dir else jobs_root / record.job_id
        record.status = resolve_job_status_on_resume(record, output_dir)
    return manifest


def load_resume_manifest(output_root: Path) -> BatchManifest:
    from ssri_model.orchestration.manifest import batch_manifest_path, load_batch_manifest

    manifest_path = batch_manifest_path(output_root)
    manifest = load_batch_manifest(manifest_path)
    return apply_resume_state(manifest, output_root)
