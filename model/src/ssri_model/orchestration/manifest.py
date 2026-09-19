"""Batch manifest persistence with atomic writes."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ssri_model.orchestration.config import JobSpec
from ssri_model.orchestration.exceptions import BatchManifestError

BATCH_MANIFEST_NAME = "batch_manifest.json"
BATCH_MANIFEST_TMP_SUFFIX = ".tmp"

JobStatus = Literal["pending", "running", "completed", "failed", "skipped"]
BatchStatus = Literal["pending", "running", "completed", "completed_with_errors", "failed"]

SCIENTIFIC_VALIDATION_STATUS = "NOT_VALIDATED"


@dataclass
class JobRecord:
    """One job entry in a batch manifest."""

    job_id: str
    status: JobStatus = "pending"
    checkpoint: str = ""
    features: str = ""
    manifest: str = ""
    statistics: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    output_dir: str = ""
    prediction: str | None = None
    confidence: str | None = None
    probabilities: str | None = None
    inference_metadata: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    error: str | None = None
    duration_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "job_id": self.job_id,
            "status": self.status,
            "checkpoint": self.checkpoint,
            "features": self.features,
            "manifest": self.manifest,
            "statistics": self.statistics,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "output_dir": self.output_dir,
            "prediction": self.prediction,
            "confidence": self.confidence,
            "probabilities": self.probabilities,
            "inference_metadata": self.inference_metadata,
            "error": self.error,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "scientific_validation_status": SCIENTIFIC_VALIDATION_STATUS,
        }
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> JobRecord:
        return cls(
            job_id=str(payload["job_id"]),
            status=payload.get("status", "pending"),
            checkpoint=str(payload.get("checkpoint", "")),
            features=str(payload.get("features", "")),
            manifest=str(payload.get("manifest", "")),
            statistics=str(payload.get("statistics", "")),
            started_at=payload.get("started_at"),
            completed_at=payload.get("completed_at"),
            output_dir=str(payload.get("output_dir", "")),
            prediction=payload.get("prediction"),
            confidence=payload.get("confidence"),
            probabilities=payload.get("probabilities"),
            inference_metadata=payload.get("inference_metadata"),
            error_type=payload.get("error_type"),
            error_message=payload.get("error_message"),
            error=payload.get("error"),
            duration_seconds=payload.get("duration_seconds"),
            metadata=dict(payload.get("metadata", {})),
        )

    def to_job_spec(self) -> JobSpec:
        if not all([self.checkpoint, self.features, self.manifest, self.statistics]):
            raise BatchManifestError(
                f"Job {self.job_id!r} is missing input paths required for resume"
            )
        return JobSpec(
            job_id=self.job_id,
            checkpoint=self.checkpoint,
            features=self.features,
            manifest=self.manifest,
            statistics=self.statistics,
            output_dir=self.output_dir,
            metadata=self.metadata or None,
        )


@dataclass
class BatchManifest:
    """Machine-readable batch execution manifest."""

    batch_id: str
    created_at: str
    status: BatchStatus = "pending"
    jobs: list[JobRecord] = field(default_factory=list)
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    scientific_validation_status: str = SCIENTIFIC_VALIDATION_STATUS
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "created_at": self.created_at,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "scientific_validation_status": self.scientific_validation_status,
            "jobs": [job.to_dict() for job in self.jobs],
            **({"metadata": self.metadata} if self.metadata else {}),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BatchManifest:
        jobs_payload = payload.get("jobs")
        if not isinstance(jobs_payload, list):
            raise BatchManifestError("Batch manifest must contain a jobs array")
        return cls(
            batch_id=str(payload["batch_id"]),
            created_at=str(payload.get("created_at", utc_now_iso())),
            status=payload.get("status", "pending"),
            jobs=[JobRecord.from_dict(entry) for entry in jobs_payload],
            started_at=payload.get("started_at"),
            completed_at=payload.get("completed_at"),
            duration_seconds=payload.get("duration_seconds"),
            scientific_validation_status=str(
                payload.get("scientific_validation_status", SCIENTIFIC_VALIDATION_STATUS)
            ),
            metadata=dict(payload.get("metadata", {})),
        )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def batch_manifest_path(output_root: Path) -> Path:
    return output_root / BATCH_MANIFEST_NAME


def initialize_manifest_from_specs(
    *,
    batch_id: str,
    job_specs: list[tuple[JobSpec, Path]],
    metadata: dict[str, Any] | None = None,
) -> BatchManifest:
    records = [
        JobRecord(
            job_id=spec.job_id,
            output_dir=str(output_path),
            checkpoint=str(spec.checkpoint_path),
            features=str(spec.features_path),
            manifest=str(spec.manifest_path),
            statistics=str(spec.statistics_path),
            metadata=dict(spec.metadata or {}),
        )
        for spec, output_path in job_specs
    ]
    return BatchManifest(
        batch_id=batch_id,
        created_at=utc_now_iso(),
        status="pending",
        jobs=records,
        metadata=metadata or {},
    )


def load_batch_manifest(path: Path | str) -> BatchManifest:
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise BatchManifestError(f"Batch manifest not found: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchManifestError(f"Unable to read batch manifest: {manifest_path}") from exc
    if not isinstance(payload, dict):
        raise BatchManifestError("Batch manifest must contain a JSON object")
    return BatchManifest.from_dict(payload)


def save_batch_manifest(path: Path | str, manifest: BatchManifest) -> Path:
    """Atomically persist a batch manifest."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_name(destination.name + BATCH_MANIFEST_TMP_SUFFIX)
    tmp_path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    os.replace(tmp_path, destination)
    return destination


def find_job_record(manifest: BatchManifest, job_id: str) -> JobRecord:
    for record in manifest.jobs:
        if record.job_id == job_id:
            return record
    raise BatchManifestError(f"Job not found in manifest: {job_id}")
