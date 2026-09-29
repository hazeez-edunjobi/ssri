"""Product API for accounts, datasets, training runs, models, and admin views.

Identity comes from a verified Supabase access token, or from a test token map.
Ownership is enforced on the server. Client-supplied user ids are ignored.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ssri_model.api.dependencies import get_job_executor, get_job_service, get_service_config
from ssri_model.auth.authorization import permissions_for_role
from ssri_model.auth.models import AuthenticatedPrincipal, Role
from ssri_model.jobs.executor import JobExecutor
from ssri_model.jobs.models import JobStatus, JobType
from ssri_model.jobs.service import JobService
from ssri_model.platform.auth import verify_supabase_access_token
from ssri_model.platform.models import TrainingRun
from ssri_model.platform.service import execute_platform_training, register_dataset_zip
from ssri_model.platform.store import MemoryPlatformStore, PlatformError
from ssri_model.platform.supabase_store import SupabasePlatformStore, supabase_store_from_env
from ssri_model.service.config import ServiceConfig

router = APIRouter(prefix="/platform", tags=["platform"])


class CreateDatasetBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class StartRunBody(BaseModel):
    dataset_id: str
    dataset_version_id: str | None = None
    name: str = Field(default="Training run", min_length=1, max_length=120)
    description: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store(request: Request) -> MemoryPlatformStore | SupabasePlatformStore:
    store = getattr(request.app.state, "platform_store", None)
    if store is not None:
        return store
    live = supabase_store_from_env()
    if live is not None:
        return live
    raise PlatformError(
        "Platform persistence is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, "
        "and apply the Version 4 migration.",
        code="PLATFORM_NOT_CONFIGURED",
        status=503,
    )


def _error(exc: PlatformError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


def _page(limit: int, offset: int) -> tuple[int, int]:
    return max(1, min(limit, 100)), max(0, offset)


class Actor(BaseModel):
    user_id: str
    email: str
    display_name: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def get_actor(
    request: Request,
    authorization: str | None = Header(default=None),
) -> Actor:
    tokens: dict[str, tuple[str, str, str]] = getattr(request.app.state, "platform_tokens", {})
    if not authorization or not authorization.lower().startswith("bearer "):
        raise PlatformError("Sign in to continue.", code="UNAUTHENTICATED", status=401)
    token = authorization.split(" ", 1)[1].strip()
    if token in tokens:
        user_id, email, role = tokens[token]
        store = _store(request)
        profile = store.upsert_profile(
            user_id=user_id,
            email=email,
            display_name=email.split("@")[0],
            role=role,
        )
        return Actor(
            user_id=profile.id,
            email=profile.email,
            display_name=profile.display_name,
            role=profile.role,
        )
    identity = verify_supabase_access_token(token)
    store = _store(request)
    profile = store.get_profile(identity.user_id) or store.upsert_profile(
        user_id=identity.user_id,
        email=identity.email,
        display_name=identity.display_name,
    )
    return Actor(
        user_id=profile.id,
        email=profile.email,
        display_name=profile.display_name,
        role=profile.role,
    )


def _actor_or_error(request: Request, authorization: str | None = Header(default=None)) -> Actor:
    try:
        return get_actor(request, authorization)
    except PlatformError as exc:
        raise _PlatformHTTP(exc) from exc


class _PlatformHTTP(Exception):
    def __init__(self, error: PlatformError) -> None:
        self.error = error


def require_actor(request: Request, authorization: str | None = Header(default=None)) -> Actor:
    try:
        return get_actor(request, authorization)
    except PlatformError as exc:
        # FastAPI exception handler registered below via route wrappers.
        request.state.platform_error = exc
        raise


def _guard(actor_call):
    """Translate PlatformError into JSON inside each route."""


@router.get("/me")
def me(request: Request, authorization: str | None = Header(default=None)) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
    except PlatformError as exc:
        return _error(exc)
    return {
        "profile": store.get_profile(actor.user_id).to_dict(),  # type: ignore[union-attr]
        "counts": store.counts_for_user(actor.user_id),
    }


@router.get("/datasets")
def list_datasets(
    request: Request,
    authorization: str | None = Header(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str = "",
) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
        rows, total = store.list_datasets(
            user_id=None if actor.is_admin else actor.user_id,
            limit=limit,
            offset=offset,
            search=search,
        )
    except PlatformError as exc:
        return _error(exc)
    return {"datasets": [row.to_dict() for row in rows], "total": total, "limit": limit, "offset": offset}


@router.post("/datasets", status_code=201)
def create_dataset(
    body: CreateDatasetBody,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
        dataset = store.create_dataset(
            user_id=actor.user_id, name=body.name, description=body.description
        )
    except PlatformError as exc:
        return _error(exc)
    return {"dataset": dataset.to_dict()}


@router.get("/datasets/{dataset_id}")
def get_dataset(
    dataset_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
        dataset = store.get_dataset(dataset_id)
        if dataset is None or (dataset.user_id != actor.user_id and not actor.is_admin):
            raise PlatformError("Dataset not found.", code="NOT_FOUND", status=404)
        versions = store.versions_for(dataset_id)
    except PlatformError as exc:
        return _error(exc)
    return {
        "dataset": dataset.to_dict(),
        "versions": [version.to_dict() for version in versions],
    }


@router.delete("/datasets/{dataset_id}")
def delete_dataset(
    dataset_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
        dataset = store.get_dataset(dataset_id)
        if dataset is None or dataset.user_id != actor.user_id:
            raise PlatformError("Dataset not found.", code="NOT_FOUND", status=404)
        store.delete_dataset(dataset_id)
        store.add_activity(
            user_id=actor.user_id,
            action="dataset_deleted",
            resource_type="dataset",
            resource_id=dataset_id,
            metadata={"name": dataset.name},
        )
    except PlatformError as exc:
        return _error(exc)
    return {"deleted": True}


@router.post("/datasets/{dataset_id}/versions")
async def upload_version(
    dataset_id: str,
    request: Request,
    file: UploadFile = File(...),
    crs: str = Form(default=""),
    authorization: str | None = Header(default=None),
    service_config: ServiceConfig = Depends(get_service_config),
) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
        content = await file.read()
        version = register_dataset_zip(
            store,
            output_root=service_config.output_root,
            user_id=actor.user_id,
            dataset_id=dataset_id,
            filename=file.filename or "dataset.zip",
            content=content,
            crs=crs,
        )
    except PlatformError as exc:
        return _error(exc)
    return {"version": version.to_dict()}


@router.post("/training/runs", status_code=202)
def start_run(
    body: StartRunBody,
    request: Request,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    service_config: ServiceConfig = Depends(get_service_config),
    job_service: JobService = Depends(get_job_service),
    job_executor: JobExecutor = Depends(get_job_executor),
) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
        if idempotency_key:
            existing = store.find_run_by_idempotency(user_id=actor.user_id, key=idempotency_key)
            if existing is not None:
                return {
                    "training_run": existing.to_dict(),
                    "status": existing.status,
                    "duplicate": True,
                }
        dataset = store.get_dataset(body.dataset_id)
        if dataset is None or dataset.user_id != actor.user_id:
            raise PlatformError("Dataset not found.", code="NOT_FOUND", status=404)
        versions = store.versions_for(dataset.id)
        version = None
        if body.dataset_version_id:
            version = store.get_version(body.dataset_version_id)
            if version is None or version.dataset_id != dataset.id:
                raise PlatformError("Dataset version not found.", code="NOT_FOUND", status=404)
        elif versions:
            version = versions[0]
        if version is None:
            raise PlatformError("Upload a dataset version before training.", code="DATASET_EMPTY", status=400)
        if version.validation_status != "passed":
            raise PlatformError(
                "Training could not start because this dataset version failed validation.",
                code="DATASET_VALIDATION_FAILED",
                status=400,
            )
        run = TrainingRun(
            id=str(uuid.uuid4()),
            user_id=actor.user_id,
            dataset_id=dataset.id,
            dataset_version_id=version.id,
            name=body.name.strip(),
            description=body.description.strip(),
            status="QUEUED",
            job_id=None,
            error_message=None,
            metrics={},
            scientific_validation_status="NOT_VALIDATED",
            idempotency_key=idempotency_key,
            seed=42,
            created_at=_now(),
        )
        store.add_run(run)
        principal = AuthenticatedPrincipal(
            key_id=actor.user_id,
            role=Role.OPERATOR,
            permissions=permissions_for_role(Role.OPERATOR),
            authentication_method="supabase",
            authenticated_at=_now(),
        )
        job = job_service.create_job(
            request_id=f"platform-{run.id}",
            job_type=JobType.TRAINING,
            principal=principal,
            scientific_validation_status="NOT_VALIDATED",
            payload={
                "platform_run_id": run.id,
                "dataset_id": dataset.id,
                "epochs": 5,
                "output_root": service_config.output_root,
            },
            idempotency_key=None,
        )
        run.job_id = job.job_id
        store.save_run(run)
        store.add_activity(
            user_id=actor.user_id,
            action="training_started",
            resource_type="training_run",
            resource_id=run.id,
            metadata={"name": run.name},
        )
        output_root = service_config.output_root
        run_id = run.id

        def _worker() -> None:
            current = store.get_run(run_id)
            if current and current.status == "CANCELLED":
                return
            try:
                execute_platform_training(store, output_root=output_root, run_id=run_id)
                finished = store.get_run(run_id)
                if finished and finished.status == "COMPLETED":
                    job_service.mark_completed(
                        job.job_id,
                        result={
                            "platform_run_id": run_id,
                            "model_id": finished.model_id,
                            "scientific_validation_status": "NOT_VALIDATED",
                        },
                    )
                elif finished and finished.status == "FAILED":
                    job_service.mark_failed(
                        job.job_id,
                        error_code="TRAINING_FAILED",
                        error_message=finished.error_message or "Training failed.",
                    )
            except Exception:
                job_service.mark_failed(
                    job.job_id,
                    error_code="TRAINING_FAILED",
                    error_message="Training failed while preparing or fitting the model.",
                )

        if job.status == JobStatus.QUEUED:
            job_executor.submit(job.job_id, _worker)
    except PlatformError as exc:
        return _error(exc)
    return {
        "training_run": run.to_dict(),
        "status": run.status,
        "message": "Training was queued. Completion does not mean the model is scientifically validated.",
    }


@router.get("/training/runs")
def list_runs(
    request: Request,
    authorization: str | None = Header(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str = "",
    search: str = "",
) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
        rows, total = store.list_runs(
            user_id=None if actor.is_admin else actor.user_id,
            limit=limit,
            offset=offset,
            status=status,
            search=search,
        )
    except PlatformError as exc:
        return _error(exc)
    return {"training_runs": [row.to_dict() for row in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/training/runs/{run_id}")
def get_run(
    run_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
        run = store.get_run(run_id)
        if run is None or (run.user_id != actor.user_id and not actor.is_admin):
            raise PlatformError("Training run not found.", code="NOT_FOUND", status=404)
    except PlatformError as exc:
        return _error(exc)
    return {"training_run": run.to_dict()}


@router.post("/training/runs/{run_id}/cancel")
def cancel_run(
    run_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    job_executor: JobExecutor = Depends(get_job_executor),
) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
        run = store.get_run(run_id)
        if run is None or (run.user_id != actor.user_id and not actor.is_admin):
            raise PlatformError("Training run not found.", code="NOT_FOUND", status=404)
        if run.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            raise PlatformError("This training run can no longer be cancelled.", code="CANNOT_CANCEL", status=409)
        run.status = "CANCELLED"
        run.completed_at = _now()
        store.save_run(run)
        if run.job_id:
            try:
                job_executor.cancel(run.job_id)
            except Exception:
                pass
        store.add_activity(
            user_id=run.user_id,
            action="training_cancelled",
            resource_type="training_run",
            resource_id=run.id,
            metadata={"name": run.name},
        )
    except PlatformError as exc:
        return _error(exc)
    return {"training_run": run.to_dict()}


@router.get("/models")
def list_models(
    request: Request,
    authorization: str | None = Header(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
        rows, total = store.list_models(
            user_id=None if actor.is_admin else actor.user_id,
            limit=limit,
            offset=offset,
        )
    except PlatformError as exc:
        return _error(exc)
    return {"models": [row.to_dict() for row in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/models/{model_id}")
def get_model(
    model_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
        model = store.get_model(model_id)
        if model is None or (model.user_id != actor.user_id and not actor.is_admin):
            raise PlatformError("Model not found.", code="NOT_FOUND", status=404)
    except PlatformError as exc:
        return _error(exc)
    return {"model": model.to_dict()}


@router.get("/activity")
def list_activity(
    request: Request,
    authorization: str | None = Header(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    action: str = "",
) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
        rows, total = store.list_activities(
            user_id=None if actor.is_admin else actor.user_id,
            limit=limit,
            offset=offset,
            action=action,
        )
    except PlatformError as exc:
        return _error(exc)
    return {"activities": [row.to_dict() for row in rows], "total": total, "limit": limit, "offset": offset}


def _require_admin(actor: Actor) -> None:
    if not actor.is_admin:
        raise PlatformError("You do not have access to the admin portal.", code="FORBIDDEN", status=403)


@router.get("/admin/overview")
def admin_overview(request: Request, authorization: str | None = Header(default=None)) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
        _require_admin(actor)
        activity, _total = store.list_activities(user_id=None, limit=8, offset=0)
    except PlatformError as exc:
        return _error(exc)
    return {"counts": store.platform_counts(), "recent_activity": [row.to_dict() for row in activity]}


@router.get("/admin/users")
def admin_users(
    request: Request,
    authorization: str | None = Header(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str = "",
) -> Any:
    try:
        store = _store(request)
        actor = get_actor(request, authorization)
        _require_admin(actor)
        rows, total = store.list_profiles(limit=limit, offset=offset, search=search)
        payload = []
        for profile in rows:
            counts = store.counts_for_user(profile.id)
            payload.append({**profile.to_dict(), **counts})
    except PlatformError as exc:
        return _error(exc)
    return {"users": payload, "total": total, "limit": limit, "offset": offset}
