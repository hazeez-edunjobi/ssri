"""Supabase PostgREST store. Uses the service-role key on the server only."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from ssri_model.platform.auth import supabase_service_role_key, supabase_url
from ssri_model.platform.models import (
    Activity,
    Dataset,
    DatasetVersion,
    PlatformModel,
    Profile,
    TrainingRun,
)
from ssri_model.platform.store import PlatformError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabasePlatformStore:
    def __init__(self) -> None:
        url = supabase_url()
        key = supabase_service_role_key()
        if not url or not key:
            raise PlatformError(
                "Supabase persistence is not configured on this server.",
                code="PLATFORM_NOT_CONFIGURED",
                status=503,
            )
        self._base = f"{url}/rest/v1"
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, table: str, *, params: dict | None = None, json: Any = None, prefer: str | None = None) -> Any:
        headers = dict(self._headers)
        if prefer:
            headers["Prefer"] = prefer
        try:
            response = httpx.request(
                method,
                f"{self._base}/{table}",
                headers=headers,
                params=params,
                json=json,
                timeout=20.0,
            )
        except httpx.HTTPError as exc:
            raise PlatformError(
                "Could not reach platform storage.",
                code="PLATFORM_UNAVAILABLE",
                status=503,
            ) from exc
        if response.status_code >= 400:
            message = "Platform storage rejected the request."
            try:
                payload = response.json()
                if payload.get("code") == "PGRST205":
                    message = (
                        "The Supabase project is reachable, but the Version 4 tables are not installed. "
                        "Run supabase/migrations/20260929000000_platform_v4.sql in the Supabase SQL editor."
                    )
            except Exception:
                payload = None
            raise PlatformError(message, code="PLATFORM_STORAGE", status=502)
        if not response.content:
            return []
        return response.json()

    def upsert_profile(self, *, user_id: str, email: str, display_name: str, role: str = "user") -> Profile:
        existing = self.get_profile(user_id)
        if existing is None:
            rows = self._request(
                "POST",
                "profiles",
                json={
                    "id": user_id,
                    "email": email,
                    "display_name": display_name,
                    "role": "user",
                },
                prefer="return=representation,resolution=merge-duplicates",
            )
            return Profile(**_profile(rows[0]))
        return existing

    def get_profile(self, user_id: str) -> Profile | None:
        rows = self._request("GET", "profiles", params={"id": f"eq.{user_id}", "select": "*"})
        if not rows:
            return None
        return Profile(**_profile(rows[0]))

    def list_profiles(self, *, limit: int, offset: int, search: str = "") -> tuple[list[Profile], int]:
        params: dict[str, str] = {
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset),
        }
        if search:
            params["or"] = f"(email.ilike.*{search}*,display_name.ilike.*{search}*)"
        rows = self._request("GET", "profiles", params=params)
        profiles = [Profile(**_profile(row)) for row in rows]
        return profiles, offset + len(profiles)

    def create_dataset(self, *, user_id: str, name: str, description: str) -> Dataset:
        rows = self._request(
            "POST",
            "datasets",
            json={"user_id": user_id, "name": name.strip(), "description": description.strip()},
            prefer="return=representation",
        )
        dataset = Dataset(**_dataset(rows[0]))
        self.add_activity(
            user_id=user_id,
            action="dataset_created",
            resource_type="dataset",
            resource_id=dataset.id,
            metadata={"name": dataset.name},
        )
        return dataset

    def get_dataset(self, dataset_id: str) -> Dataset | None:
        rows = self._request("GET", "datasets", params={"id": f"eq.{dataset_id}", "select": "*"})
        if not rows:
            return None
        dataset = Dataset(**_dataset(rows[0]))
        versions = self.versions_for(dataset_id)
        if versions:
            dataset.latest_version = versions[0].version
            dataset.validation_status = versions[0].validation_status
        return dataset

    def list_datasets(self, *, user_id: str | None, limit: int, offset: int, search: str = "") -> tuple[list[Dataset], int]:
        params: dict[str, str] = {
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset),
        }
        if user_id:
            params["user_id"] = f"eq.{user_id}"
        if search:
            params["name"] = f"ilike.*{search}*"
        rows = self._request("GET", "datasets", params=params)
        loaded = []
        for row in rows:
            item = self.get_dataset(row["id"])
            if item:
                loaded.append(item)
        return loaded, offset + len(loaded)

    def delete_dataset(self, dataset_id: str) -> None:
        self._request("DELETE", "datasets", params={"id": f"eq.{dataset_id}"})

    def versions_for(self, dataset_id: str) -> list[DatasetVersion]:
        rows = self._request(
            "GET",
            "dataset_versions",
            params={"dataset_id": f"eq.{dataset_id}", "select": "*", "order": "version.desc"},
        )
        return [DatasetVersion(**_version(row)) for row in rows]

    def next_version_number(self, dataset_id: str) -> int:
        versions = self.versions_for(dataset_id)
        return (versions[0].version + 1) if versions else 1

    def upload_dataset_object(self, *, path: str, content: bytes) -> None:
        """Store the original upload in the private datasets bucket."""
        url = supabase_url()
        key = supabase_service_role_key()
        object_url = f"{url}/storage/v1/object/datasets/{path}"
        try:
            response = httpx.post(
                object_url,
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/zip",
                    "x-upsert": "true",
                },
                content=content,
                timeout=120.0,
            )
        except httpx.HTTPError as exc:
            raise PlatformError(
                "Could not store the dataset file.",
                code="STORAGE_UNAVAILABLE",
                status=503,
            ) from exc
        if response.status_code >= 400:
            raise PlatformError(
                "The dataset file could not be stored.",
                code="STORAGE_REJECTED",
                status=502,
            )

    def add_version(self, version: DatasetVersion) -> DatasetVersion:
        self._request("POST", "dataset_versions", json=_version_row(version), prefer="return=minimal")
        return version

    def get_version(self, version_id: str) -> DatasetVersion | None:
        rows = self._request("GET", "dataset_versions", params={"id": f"eq.{version_id}", "select": "*"})
        if not rows:
            return None
        return DatasetVersion(**_version(rows[0]))

    def save_version(self, version: DatasetVersion) -> None:
        self._request(
            "PATCH",
            "dataset_versions",
            params={"id": f"eq.{version.id}"},
            json=_version_row(version),
            prefer="return=minimal",
        )

    def find_run_by_idempotency(self, *, user_id: str, key: str) -> TrainingRun | None:
        rows = self._request(
            "GET",
            "training_runs",
            params={"user_id": f"eq.{user_id}", "idempotency_key": f"eq.{key}", "select": "*"},
        )
        if not rows:
            return None
        return TrainingRun(**_run(rows[0]))

    def add_run(self, run: TrainingRun) -> TrainingRun:
        self._request("POST", "training_runs", json=_run_row(run), prefer="return=minimal")
        return run

    def get_run(self, run_id: str) -> TrainingRun | None:
        rows = self._request("GET", "training_runs", params={"id": f"eq.{run_id}", "select": "*"})
        if not rows:
            return None
        run = TrainingRun(**_run(rows[0]))
        models = self._request(
            "GET",
            "models",
            params={"training_run_id": f"eq.{run_id}", "select": "id"},
        )
        if models:
            run.model_id = models[0]["id"]
        return run

    def save_run(self, run: TrainingRun) -> None:
        self._request(
            "PATCH",
            "training_runs",
            params={"id": f"eq.{run.id}"},
            json=_run_row(run),
            prefer="return=minimal",
        )

    def list_runs(self, *, user_id: str | None, limit: int, offset: int, status: str = "", search: str = "") -> tuple[list[TrainingRun], int]:
        params: dict[str, str] = {
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset),
        }
        if user_id:
            params["user_id"] = f"eq.{user_id}"
        if status:
            params["status"] = f"eq.{status}"
        if search:
            params["name"] = f"ilike.*{search}*"
        rows = self._request("GET", "training_runs", params=params)
        return [TrainingRun(**_run(row)) for row in rows], offset + len(rows)

    def add_model(self, model: PlatformModel) -> PlatformModel:
        self._request("POST", "models", json=_model_row(model), prefer="return=minimal")
        return model

    def get_model(self, model_id: str) -> PlatformModel | None:
        rows = self._request("GET", "models", params={"id": f"eq.{model_id}", "select": "*"})
        if not rows:
            return None
        return PlatformModel(**_model(rows[0]))

    def list_models(self, *, user_id: str | None, limit: int, offset: int) -> tuple[list[PlatformModel], int]:
        params: dict[str, str] = {
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset),
        }
        if user_id:
            params["user_id"] = f"eq.{user_id}"
        rows = self._request("GET", "models", params=params)
        return [PlatformModel(**_model(row)) for row in rows], offset + len(rows)

    def next_model_version(self, user_id: str) -> int:
        rows = self._request(
            "GET",
            "models",
            params={"user_id": f"eq.{user_id}", "select": "version", "order": "version.desc", "limit": "1"},
        )
        if not rows:
            return 1
        return int(rows[0]["version"]) + 1

    def add_activity(self, *, user_id: str, action: str, resource_type: str, resource_id: str | None, metadata: dict[str, Any] | None = None) -> Activity:
        activity = Activity(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=dict(metadata or {}),
            created_at=_now(),
        )
        self._request(
            "POST",
            "activities",
            json={
                "id": activity.id,
                "user_id": activity.user_id,
                "action": activity.action,
                "resource_type": activity.resource_type,
                "resource_id": activity.resource_id,
                "metadata": activity.metadata,
            },
            prefer="return=minimal",
        )
        return activity

    def list_activities(self, *, user_id: str | None, limit: int, offset: int, action: str = "") -> tuple[list[Activity], int]:
        params: dict[str, str] = {
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset),
        }
        if user_id:
            params["user_id"] = f"eq.{user_id}"
        if action:
            params["action"] = f"eq.{action}"
        rows = self._request("GET", "activities", params=params)
        return [Activity(**_activity(row)) for row in rows], offset + len(rows)

    def counts_for_user(self, user_id: str) -> dict[str, int]:
        return {
            "datasets": len(self._request("GET", "datasets", params={"user_id": f"eq.{user_id}", "select": "id"})),
            "training_runs": len(self._request("GET", "training_runs", params={"user_id": f"eq.{user_id}", "select": "id"})),
            "models": len(self._request("GET", "models", params={"user_id": f"eq.{user_id}", "select": "id"})),
        }

    def platform_counts(self) -> dict[str, int]:
        def count(table: str, extra: dict | None = None) -> int:
            params = {"select": "id"}
            if extra:
                params.update(extra)
            return len(self._request("GET", table, params=params))

        return {
            "users": count("profiles"),
            "datasets": count("datasets"),
            "training_runs": count("training_runs"),
            "models": count("models"),
            "queued_runs": count("training_runs", {"status": "eq.QUEUED"}),
            "running_runs": count("training_runs", {"status": "in.(PREPARING,VALIDATING,TRAINING,EVALUATING)"}),
            "failed_runs": count("training_runs", {"status": "eq.FAILED"}),
        }


def supabase_store_from_env() -> SupabasePlatformStore | None:
    if supabase_url() and supabase_service_role_key():
        return SupabasePlatformStore()
    return None


def _profile(row: dict) -> dict:
    return {
        "id": row["id"],
        "email": row.get("email") or "",
        "display_name": row.get("display_name") or "",
        "role": row.get("role") or "user",
        "created_at": row.get("created_at") or "",
        "updated_at": row.get("updated_at") or "",
    }


def _dataset(row: dict) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "description": row.get("description") or "",
        "created_at": row.get("created_at") or "",
        "updated_at": row.get("updated_at") or "",
    }


def _version(row: dict) -> dict:
    return {
        "id": row["id"],
        "dataset_id": row["dataset_id"],
        "version": int(row["version"]),
        "storage_path": row.get("storage_path") or "",
        "file_name": row.get("file_name") or "",
        "file_size": int(row.get("file_size") or 0),
        "content_sha256": row.get("content_sha256"),
        "crs": row.get("crs"),
        "width": row.get("width"),
        "height": row.get("height"),
        "channel_count": row.get("channel_count"),
        "resolution_m": row.get("resolution_m"),
        "validation_status": row.get("validation_status") or "pending",
        "validation_errors": list(row.get("validation_errors") or []),
        "preview": dict(row.get("preview") or {}),
        "created_at": row.get("created_at") or "",
    }


def _version_row(version: DatasetVersion) -> dict:
    payload = _version(version.to_dict())
    return payload


def _run(row: dict) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "dataset_id": row["dataset_id"],
        "dataset_version_id": row["dataset_version_id"],
        "name": row["name"],
        "description": row.get("description") or "",
        "status": row.get("status") or "QUEUED",
        "job_id": row.get("job_id"),
        "error_message": row.get("error_message"),
        "metrics": dict(row.get("metrics") or {}),
        "scientific_validation_status": row.get("scientific_validation_status") or "NOT_VALIDATED",
        "idempotency_key": row.get("idempotency_key"),
        "seed": int(row.get("seed") or 42),
        "created_at": row.get("created_at") or "",
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at"),
        "model_id": None,
    }


def _run_row(run: TrainingRun) -> dict:
    payload = run.to_dict()
    payload.pop("model_id", None)
    return payload


def _model(row: dict) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "training_run_id": row["training_run_id"],
        "dataset_id": row["dataset_id"],
        "dataset_version_id": row["dataset_version_id"],
        "version": int(row["version"]),
        "name": row["name"],
        "checkpoint_path": row.get("checkpoint_path") or "",
        "metrics": dict(row.get("metrics") or {}),
        "feature_channels": int(row.get("feature_channels") or 13),
        "scientific_validation_status": row.get("scientific_validation_status") or "NOT_VALIDATED",
        "created_at": row.get("created_at") or "",
    }


def _model_row(model: PlatformModel) -> dict:
    return model.to_dict()


def _activity(row: dict) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "action": row["action"],
        "resource_type": row["resource_type"],
        "resource_id": row.get("resource_id"),
        "metadata": dict(row.get("metadata") or {}),
        "created_at": row.get("created_at") or "",
    }
