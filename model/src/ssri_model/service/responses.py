"""Service response contracts for SSRI inference."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from ssri_model.service.schemas import BatchExecutionStatus, InferenceExecutionStatus


@dataclass(frozen=True)
class InferenceResponse:
    """Typed single-inference response."""

    request_id: str
    status: InferenceExecutionStatus
    prediction_path: str | None = None
    confidence_path: str | None = None
    probability_path: str | None = None
    metadata_path: str | None = None
    model_version: str | None = None
    dataset_name: str | None = None
    dataset_version: str | None = None
    scientific_validation_status: str = "NOT_VALIDATED"
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> InferenceResponse:
        status = payload.get("status", InferenceExecutionStatus.PENDING.value)
        if isinstance(status, InferenceExecutionStatus):
            status_value = status
        else:
            status_value = InferenceExecutionStatus(str(status))
        return cls(
            request_id=str(payload["request_id"]),
            status=status_value,
            prediction_path=payload.get("prediction_path"),
            confidence_path=payload.get("confidence_path"),
            probability_path=payload.get("probability_path"),
            metadata_path=payload.get("metadata_path"),
            model_version=payload.get("model_version"),
            dataset_name=payload.get("dataset_name"),
            dataset_version=payload.get("dataset_version"),
            scientific_validation_status=str(
                payload.get("scientific_validation_status", "NOT_VALIDATED")
            ),
            started_at=payload.get("started_at"),
            completed_at=payload.get("completed_at"),
            error=payload.get("error"),
        )


@dataclass(frozen=True)
class BatchInferenceResponse:
    """Typed batch inference response."""

    request_id: str
    batch_id: str
    status: BatchExecutionStatus
    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    skipped_jobs: int = 0
    manifest_path: str | None = None
    scientific_validation_status: str = "NOT_VALIDATED"
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> BatchInferenceResponse:
        status = payload.get("status", BatchExecutionStatus.PENDING.value)
        if isinstance(status, BatchExecutionStatus):
            status_value = status
        else:
            status_value = BatchExecutionStatus(str(status))
        return cls(
            request_id=str(payload["request_id"]),
            batch_id=str(payload["batch_id"]),
            status=status_value,
            total_jobs=int(payload.get("total_jobs", 0)),
            completed_jobs=int(payload.get("completed_jobs", 0)),
            failed_jobs=int(payload.get("failed_jobs", 0)),
            skipped_jobs=int(payload.get("skipped_jobs", 0)),
            manifest_path=payload.get("manifest_path"),
            scientific_validation_status=str(
                payload.get("scientific_validation_status", "NOT_VALIDATED")
            ),
            started_at=payload.get("started_at"),
            completed_at=payload.get("completed_at"),
            error=payload.get("error"),
        )
