"""In-memory platform store used by tests and local runs without Supabase."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ssri_model.platform.models import (
    Activity,
    Dataset,
    DatasetVersion,
    PlatformModel,
    Profile,
    TrainingRun,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


class PlatformError(Exception):
    def __init__(self, message: str, *, code: str = "PLATFORM_ERROR", status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


class MemoryPlatformStore:
    """Process-local stand-in for the Supabase tables. Not shared across workers."""

    def __init__(self) -> None:
        self.profiles: dict[str, Profile] = {}
        self.datasets: dict[str, Dataset] = {}
        self.versions: dict[str, DatasetVersion] = {}
        self.runs: dict[str, TrainingRun] = {}
        self.models: dict[str, PlatformModel] = {}
        self.activities: dict[str, Activity] = {}

    def upsert_profile(self, *, user_id: str, email: str, display_name: str, role: str = "user") -> Profile:
        existing = self.profiles.get(user_id)
        now = _now()
        if existing is None:
            profile = Profile(
                id=user_id,
                email=email,
                display_name=display_name or email.split("@")[0],
                role=role if role in {"user", "admin"} else "user",
                created_at=now,
                updated_at=now,
            )
        else:
            profile = Profile(
                id=existing.id,
                email=email or existing.email,
                display_name=display_name or existing.display_name,
                role=existing.role,
                created_at=existing.created_at,
                updated_at=now,
            )
        self.profiles[user_id] = profile
        return profile

    def get_profile(self, user_id: str) -> Profile | None:
        return self.profiles.get(user_id)

    def list_profiles(self, *, limit: int, offset: int, search: str = "") -> tuple[list[Profile], int]:
        rows = list(self.profiles.values())
        if search:
            needle = search.lower()
            rows = [row for row in rows if needle in row.email.lower() or needle in row.display_name.lower()]
        rows.sort(key=lambda row: row.created_at, reverse=True)
        return rows[offset : offset + limit], len(rows)

    def create_dataset(self, *, user_id: str, name: str, description: str) -> Dataset:
        now = _now()
        dataset = Dataset(
            id=_new_id(),
            user_id=user_id,
            name=name.strip(),
            description=description.strip(),
            created_at=now,
            updated_at=now,
        )
        self.datasets[dataset.id] = dataset
        self.add_activity(
            user_id=user_id,
            action="dataset_created",
            resource_type="dataset",
            resource_id=dataset.id,
            metadata={"name": dataset.name},
        )
        return dataset

    def get_dataset(self, dataset_id: str) -> Dataset | None:
        dataset = self.datasets.get(dataset_id)
        if dataset is None:
            return None
        versions = self.versions_for(dataset_id)
        if versions:
            latest = versions[0]
            dataset.latest_version = latest.version
            dataset.validation_status = latest.validation_status
        return dataset

    def list_datasets(
        self, *, user_id: str | None, limit: int, offset: int, search: str = ""
    ) -> tuple[list[Dataset], int]:
        rows = list(self.datasets.values())
        if user_id is not None:
            rows = [row for row in rows if row.user_id == user_id]
        if search:
            needle = search.lower()
            rows = [row for row in rows if needle in row.name.lower()]
        rows.sort(key=lambda row: row.created_at, reverse=True)
        page = []
        for row in rows[offset : offset + limit]:
            loaded = self.get_dataset(row.id)
            if loaded is not None:
                page.append(loaded)
        return page, len(rows)

    def delete_dataset(self, dataset_id: str) -> None:
        self.datasets.pop(dataset_id, None)
        for version_id, version in list(self.versions.items()):
            if version.dataset_id == dataset_id:
                self.versions.pop(version_id, None)

    def versions_for(self, dataset_id: str) -> list[DatasetVersion]:
        rows = [row for row in self.versions.values() if row.dataset_id == dataset_id]
        rows.sort(key=lambda row: row.version, reverse=True)
        return rows

    def next_version_number(self, dataset_id: str) -> int:
        versions = self.versions_for(dataset_id)
        if not versions:
            return 1
        return versions[0].version + 1

    def add_version(self, version: DatasetVersion) -> DatasetVersion:
        self.versions[version.id] = version
        dataset = self.datasets.get(version.dataset_id)
        if dataset is not None:
            dataset.updated_at = _now()
            dataset.latest_version = version.version
            dataset.validation_status = version.validation_status
        return version

    def get_version(self, version_id: str) -> DatasetVersion | None:
        return self.versions.get(version_id)

    def save_version(self, version: DatasetVersion) -> None:
        self.versions[version.id] = version

    def find_run_by_idempotency(self, *, user_id: str, key: str) -> TrainingRun | None:
        for run in self.runs.values():
            if run.user_id == user_id and run.idempotency_key == key:
                return run
        return None

    def add_run(self, run: TrainingRun) -> TrainingRun:
        self.runs[run.id] = run
        return run

    def get_run(self, run_id: str) -> TrainingRun | None:
        return self.runs.get(run_id)

    def save_run(self, run: TrainingRun) -> None:
        self.runs[run.id] = run

    def list_runs(
        self,
        *,
        user_id: str | None,
        limit: int,
        offset: int,
        status: str = "",
        search: str = "",
    ) -> tuple[list[TrainingRun], int]:
        rows = list(self.runs.values())
        if user_id is not None:
            rows = [row for row in rows if row.user_id == user_id]
        if status:
            rows = [row for row in rows if row.status == status]
        if search:
            needle = search.lower()
            rows = [row for row in rows if needle in row.name.lower() or needle in row.id.lower()]
        rows.sort(key=lambda row: row.created_at, reverse=True)
        return rows[offset : offset + limit], len(rows)

    def add_model(self, model: PlatformModel) -> PlatformModel:
        self.models[model.id] = model
        run = self.runs.get(model.training_run_id)
        if run is not None:
            run.model_id = model.id
        return model

    def get_model(self, model_id: str) -> PlatformModel | None:
        return self.models.get(model_id)

    def list_models(
        self, *, user_id: str | None, limit: int, offset: int
    ) -> tuple[list[PlatformModel], int]:
        rows = list(self.models.values())
        if user_id is not None:
            rows = [row for row in rows if row.user_id == user_id]
        rows.sort(key=lambda row: row.created_at, reverse=True)
        return rows[offset : offset + limit], len(rows)

    def next_model_version(self, user_id: str) -> int:
        owned = [model.version for model in self.models.values() if model.user_id == user_id]
        return (max(owned) + 1) if owned else 1

    def add_activity(
        self,
        *,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> Activity:
        activity = Activity(
            id=_new_id(),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=dict(metadata or {}),
            created_at=_now(),
        )
        self.activities[activity.id] = activity
        return activity

    def list_activities(
        self,
        *,
        user_id: str | None,
        limit: int,
        offset: int,
        action: str = "",
    ) -> tuple[list[Activity], int]:
        rows = list(self.activities.values())
        if user_id is not None:
            rows = [row for row in rows if row.user_id == user_id]
        if action:
            rows = [row for row in rows if row.action == action]
        rows.sort(key=lambda row: row.created_at, reverse=True)
        return rows[offset : offset + limit], len(rows)

    def counts_for_user(self, user_id: str) -> dict[str, int]:
        return {
            "datasets": sum(1 for row in self.datasets.values() if row.user_id == user_id),
            "training_runs": sum(1 for row in self.runs.values() if row.user_id == user_id),
            "models": sum(1 for row in self.models.values() if row.user_id == user_id),
        }

    def platform_counts(self) -> dict[str, int]:
        return {
            "users": len(self.profiles),
            "datasets": len(self.datasets),
            "training_runs": len(self.runs),
            "models": len(self.models),
            "queued_runs": sum(1 for row in self.runs.values() if row.status == "QUEUED"),
            "running_runs": sum(
                1
                for row in self.runs.values()
                if row.status in {"PREPARING", "VALIDATING", "TRAINING", "EVALUATING"}
            ),
            "failed_runs": sum(1 for row in self.runs.values() if row.status == "FAILED"),
        }


PlatformStore = MemoryPlatformStore
