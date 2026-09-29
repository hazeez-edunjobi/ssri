"""Platform records. Scientific status is never set to SCIENTIFICALLY_VALIDATED here."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Profile:
    id: str
    email: str
    display_name: str
    role: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Dataset:
    id: str
    user_id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    latest_version: int | None = None
    validation_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DatasetVersion:
    id: str
    dataset_id: str
    version: int
    storage_path: str
    file_name: str
    file_size: int
    content_sha256: str | None
    crs: str | None
    width: int | None
    height: int | None
    channel_count: int | None
    resolution_m: float | None
    validation_status: str
    validation_errors: list[str] = field(default_factory=list)
    preview: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrainingRun:
    id: str
    user_id: str
    dataset_id: str
    dataset_version_id: str
    name: str
    description: str
    status: str
    job_id: str | None
    error_message: str | None
    metrics: dict[str, Any]
    scientific_validation_status: str
    idempotency_key: str | None
    seed: int
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    model_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlatformModel:
    id: str
    user_id: str
    training_run_id: str
    dataset_id: str
    dataset_version_id: str
    version: int
    name: str
    checkpoint_path: str
    metrics: dict[str, Any]
    feature_channels: int
    scientific_validation_status: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Activity:
    id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: str | None
    metadata: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
