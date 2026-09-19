"""FastAPI dependency injection and execution adapters."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast, Protocol

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ssri_model.auth.audit import log_authentication_event
from ssri_model.auth.authorization import has_permission
from ssri_model.auth.config import AuthConfig
from ssri_model.auth.credentials import KeyStore
from ssri_model.auth.dependencies import (
    authenticate_api_key,
    development_principal,
    extract_bearer_token,
)
from ssri_model.auth.exceptions import AuthenticationError, AuthorizationError
from ssri_model.auth.models import AuthenticatedPrincipal, Permission

from ssri_model.inference import InferenceResult, run_inference
from ssri_model.orchestration import BatchRunner, load_jobs_file
from ssri_model.orchestration.manifest import batch_manifest_path, load_batch_manifest
from ssri_model.orchestration.status import get_batch_status, get_job_status
from ssri_model.service.config import ServiceConfig
from ssri_model.service.provenance import ProvenanceRecord, build_provenance_record
from ssri_model.service.requests import BatchInferenceRequest, InferenceRequest
from ssri_model.service.responses import BatchInferenceResponse, InferenceResponse
from ssri_model.service.schemas import BatchExecutionStatus, InferenceExecutionStatus
from ssri_model.service.validation import (
    ensure_output_under_root,
    reject_path_traversal,
    resolve_under_output_root,
    sanitize_request_id,
    validate_batch_request,
    validate_inference_request,
)

from ssri_model.auth.key_management import KeyStoreManager
from ssri_model.infrastructure.factory import InfrastructureResources, build_infrastructure
from ssri_model.jobs.executor import JobExecutor
from ssri_model.jobs.service import JobService
from ssri_model.ratelimit import RateLimiter

from ssri_model.api.config import APIConfig

logger = logging.getLogger(__name__)

PROVENANCE_FILENAME = "provenance.json"
METADATA_FILENAME = "inference_metadata.json"
InferenceCallable = Callable[..., InferenceResult]
_bearer_scheme = HTTPBearer(auto_error=False)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AppState:
    """Application state container for dependency injection."""

    api_config: APIConfig
    inference_executor: InferenceExecutor
    batch_executor: BatchExecutor
    auth_config: AuthConfig
    key_store: KeyStore
    key_manager: KeyStoreManager
    job_service: JobService
    job_executor: JobExecutor
    inference_rate_limiter: RateLimiter
    batch_rate_limiter: RateLimiter
    status_rate_limiter: RateLimiter
    infrastructure: InfrastructureResources | None = None


class InferenceExecutor(Protocol):
    def execute(
        self,
        request: InferenceRequest,
        *,
        scientific_validation_status: str,
        principal: AuthenticatedPrincipal | None = None,
    ) -> tuple[InferenceResponse, ProvenanceRecord]: ...


class BatchExecutor(Protocol):
    def execute(
        self,
        request: BatchInferenceRequest,
        *,
        scientific_validation_status: str,
    ) -> BatchInferenceResponse: ...


class DefaultInferenceExecutor:
    """Execute inference through Stage 3.0 validation and Stage 2.7 runner."""

    def __init__(
        self,
        service_config: ServiceConfig,
        *,
        inference_runner: InferenceCallable | None = None,
    ) -> None:
        self._service_config = service_config
        self._run_inference = inference_runner or run_inference

    def execute(
        self,
        request: InferenceRequest,
        *,
        scientific_validation_status: str,
        principal: AuthenticatedPrincipal | None = None,
    ) -> tuple[InferenceResponse, ProvenanceRecord]:
        output_dir = validate_inference_request(
            request,
            self._service_config,
            scientific_validation_status=scientific_validation_status,
        )
        tile_size = request.tile_size or self._service_config.default_inference_tile_size
        overlap = (
            request.overlap
            if request.overlap is not None
            else self._service_config.default_inference_overlap
        )
        batch_size = request.batch_size or self._service_config.default_batch_size

        inference_config = request.to_inference_config(
            output_dir=output_dir,
            tile_size=tile_size,
            overlap=overlap,
            batch_size=batch_size,
        )
        inference_configuration = {
            "tile_size": tile_size,
            "overlap": overlap,
            "batch_size": batch_size,
            "output_format": request.output_format.value,
        }

        started_at = utc_now_iso()
        try:
            result = self._run_inference(inference_config)
            completed_at = utc_now_iso()
            provenance = build_provenance_record(
                request,
                service_name=self._service_config.service_name,
                service_version=self._service_config.service_version,
                inference_configuration=inference_configuration,
                scientific_validation_status=scientific_validation_status,
                auth_key_id=principal.key_id if principal else None,
                auth_role=principal.role.value if principal else None,
                auth_method=principal.authentication_method if principal else None,
            )
            self._persist_metadata(output_dir, provenance, result)
            response = InferenceResponse(
                request_id=request.request_id,
                status=InferenceExecutionStatus.COMPLETED,
                prediction_path=str(result.prediction_path),
                confidence_path=str(result.confidence_path),
                probability_path=str(result.probabilities_path),
                metadata_path=str(result.metadata_path),
                scientific_validation_status=scientific_validation_status,
                started_at=started_at,
                completed_at=completed_at,
            )
            return response, provenance
        except Exception:
            logger.exception("Inference failed for request %s", request.request_id)
            raise

    @staticmethod
    def _persist_metadata(
        output_dir: Path,
        provenance: ProvenanceRecord,
        result: InferenceResult,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / PROVENANCE_FILENAME).write_text(
            json.dumps(provenance.to_dict(), indent=2),
            encoding="utf-8",
        )
        metadata_payload = {
            "request_id": provenance.request_id,
            "status": InferenceExecutionStatus.COMPLETED.value,
            "scientific_validation_status": provenance.scientific_validation_status,
            "artifacts": {
                "prediction": str(result.prediction_path),
                "confidence": str(result.confidence_path),
                "probabilities": str(result.probabilities_path),
                "metadata": str(result.metadata_path),
            },
        }
        (output_dir / METADATA_FILENAME).write_text(
            json.dumps(metadata_payload, indent=2),
            encoding="utf-8",
        )


class DefaultBatchExecutor:
    """Execute batch inference through Stage 3.0 validation and Stage 2.8 runner."""

    def __init__(
        self,
        service_config: ServiceConfig,
        *,
        max_batch_jobs: int = 100,
        inference_runner: InferenceCallable | None = None,
    ) -> None:
        self._service_config = service_config
        self._max_batch_jobs = max_batch_jobs
        self._inference_runner = inference_runner

    def execute(
        self,
        request: BatchInferenceRequest,
        *,
        scientific_validation_status: str,
    ) -> BatchInferenceResponse:
        validated_root = validate_batch_request(
            request,
            self._service_config,
            scientific_validation_status=scientific_validation_status,
        )
        jobs_file = load_jobs_file(request.jobs_file)
        if len(jobs_file.jobs) > self._max_batch_jobs:
            from ssri_model.service.exceptions import InvalidServiceRequestError

            raise InvalidServiceRequestError(
                f"Batch exceeds max_batch_jobs limit ({self._max_batch_jobs})"
            )

        from ssri_model.orchestration.config import BatchConfig

        batch_config = BatchConfig(
            output_root=str(validated_root),
            resume=request.resume,
            device="auto",
        )
        runner = BatchRunner(
            batch_config,
            inference_runner=self._inference_runner,
        )
        started_at = utc_now_iso()
        result = runner.run(list(jobs_file.jobs), batch_id=jobs_file.batch_id)
        completed_at = utc_now_iso()

        status = BatchExecutionStatus(result.status)
        return BatchInferenceResponse(
            request_id=request.request_id,
            batch_id=result.batch_id,
            status=status,
            total_jobs=result.total_jobs,
            completed_jobs=result.completed_jobs,
            failed_jobs=result.failed_jobs,
            skipped_jobs=result.skipped_jobs,
            manifest_path=result.manifest_path,
            scientific_validation_status=scientific_validation_status,
            started_at=started_at,
            completed_at=completed_at,
        )


def create_app_state(
    api_config: APIConfig,
    *,
    inference_runner: InferenceCallable | None = None,
    batch_inference_runner: InferenceCallable | None = None,
    inference_executor: InferenceExecutor | None = None,
    batch_executor: BatchExecutor | None = None,
    key_store: KeyStore | None = None,
    key_manager: KeyStoreManager | None = None,
    job_service: JobService | None = None,
    job_executor: JobExecutor | None = None,
) -> AppState:
    service_config = api_config.service_config
    auth_config = api_config.auth_config
    infra = build_infrastructure(api_config)
    if job_service is not None:
        infra.job_service = job_service
    if job_executor is not None:
        infra.job_executor = job_executor
    if key_manager is not None:
        resolved_key_manager = key_manager
        resolved_key_store = key_manager.readonly_store
    elif key_store is not None:
        resolved_key_manager = KeyStoreManager.from_store(key_store)
        resolved_key_store = key_store
    elif auth_config.enabled:
        resolved_key_manager = KeyStoreManager.load(auth_config.key_store_path)
        resolved_key_store = resolved_key_manager.readonly_store
    else:
        resolved_key_store = KeyStore.from_records({})
        resolved_key_manager = KeyStoreManager.from_store(resolved_key_store)
    resolved_inference = inference_executor or DefaultInferenceExecutor(
        service_config,
        inference_runner=inference_runner,
    )
    resolved_batch = batch_executor or DefaultBatchExecutor(
        service_config,
        max_batch_jobs=api_config.max_batch_jobs,
        inference_runner=batch_inference_runner or inference_runner,
    )
    return AppState(
        api_config=api_config,
        inference_executor=resolved_inference,
        batch_executor=resolved_batch,
        auth_config=auth_config,
        key_store=resolved_key_store,
        key_manager=resolved_key_manager,
        job_service=infra.job_service,
        job_executor=infra.job_executor,
        inference_rate_limiter=infra.inference_rate_limiter,
        batch_rate_limiter=infra.batch_rate_limiter,
        status_rate_limiter=infra.status_rate_limiter,
        infrastructure=infra,
    )


def get_app_state(request: Request) -> AppState:
    state = getattr(request.app.state, "ssri", None)
    if state is None:
        raise RuntimeError("SSRI application state is not configured")
    return cast(AppState, state)


def get_api_config(request: Request) -> APIConfig:
    return get_app_state(request).api_config


def get_service_config(request: Request) -> ServiceConfig:
    return get_app_state(request).api_config.service_config


def get_inference_executor(request: Request) -> InferenceExecutor:
    return get_app_state(request).inference_executor


def get_batch_executor(request: Request) -> BatchExecutor:
    return get_app_state(request).batch_executor


def get_auth_config(request: Request) -> AuthConfig:
    return get_app_state(request).auth_config


def get_key_store(request: Request) -> KeyStore:
    return get_app_state(request).key_store


def get_key_manager(request: Request) -> KeyStoreManager:
    return get_app_state(request).key_manager


def get_job_service(request: Request) -> JobService:
    return get_app_state(request).job_service


def get_job_executor(request: Request) -> JobExecutor:
    return get_app_state(request).job_executor


def refresh_key_store(state: AppState) -> None:
    state.key_manager.reload()
    state.key_store = state.key_manager.readonly_store


def get_current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthenticatedPrincipal:
    state = get_app_state(request)
    auth_config = state.auth_config
    if auth_config.enabled and state.key_manager.readonly_store.path is not None:
        state.key_manager.reload()
        state.key_store = state.key_manager.readonly_store
    if not auth_config.enabled:
        if auth_config.development_auth_mode:
            return development_principal()
        raise AuthenticationError("Authentication is required.")
    try:
        token = extract_bearer_token(credentials)
        principal = authenticate_api_key(
            auth_config=auth_config,
            key_store=state.key_store,
            token=token,
        )
        log_authentication_event(
            request_id=request.headers.get("X-Request-ID"),
            key_id=principal.key_id,
            role=principal.role.value,
            endpoint=request.url.path,
            method=request.method,
            outcome="success",
        )
        return principal
    except AuthenticationError:
        log_authentication_event(
            request_id=request.headers.get("X-Request-ID"),
            key_id=None,
            role=None,
            endpoint=request.url.path,
            method=request.method,
            outcome="failure",
        )
        raise


def require_permission_dependency(
    permission: Permission,
) -> Callable[..., AuthenticatedPrincipal]:
    def _dependency(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AuthenticatedPrincipal:
        if not has_permission(principal, permission):
            raise AuthorizationError(
                "The authenticated principal does not have permission to perform this operation."
            )
        return principal

    return _dependency


require_run_inference = require_permission_dependency(Permission.RUN_INFERENCE)
require_run_batch = require_permission_dependency(Permission.RUN_BATCH)
require_read_metadata = require_permission_dependency(Permission.READ_METADATA)
require_read_status = require_permission_dependency(Permission.READ_STATUS)
require_manage_auth = require_permission_dependency(Permission.MANAGE_AUTH)


def _enforce_rate_limit(request: Request, principal: AuthenticatedPrincipal, bucket: str) -> None:
    from ssri_model.api.rate_limit import enforce_rate_limit

    state = get_app_state(request)
    if not state.api_config.operational_config.rate_limit_enabled:
        return
    limiter = {
        "inference": state.inference_rate_limiter,
        "batch": state.batch_rate_limiter,
        "status": state.status_rate_limiter,
    }[bucket]
    enforce_rate_limit(limiter, principal.key_id)


def require_run_inference_rate_limited(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> AuthenticatedPrincipal:
    _enforce_rate_limit(request, principal, "inference")
    return principal


def require_run_batch_rate_limited(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(require_run_batch),
) -> AuthenticatedPrincipal:
    _enforce_rate_limit(request, principal, "batch")
    return principal


def require_read_status_rate_limited(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(require_read_status),
) -> AuthenticatedPrincipal:
    _enforce_rate_limit(request, principal, "status")
    return principal


def resolve_batch_manifest_path(
    *,
    service_config: ServiceConfig,
    batch_id: str,
    output_root: str | None = None,
) -> Path:
    safe_batch_id = sanitize_request_id(batch_id)
    if output_root:
        reject_path_traversal(output_root, field_name="output_root")
        root = ensure_output_under_root(output_root, output_root=service_config.output_root)
    else:
        root = resolve_under_output_root(
            service_config.output_root,
            "batches",
            safe_batch_id,
        )
    return batch_manifest_path(root)


def load_inference_metadata(
    *,
    service_config: ServiceConfig,
    request_id: str,
    output_dir: str | None = None,
) -> dict[str, Any]:
    safe_id = sanitize_request_id(request_id)
    if output_dir:
        reject_path_traversal(output_dir, field_name="output_dir")
        base = ensure_output_under_root(output_dir, output_root=service_config.output_root)
    else:
        base = resolve_under_output_root(service_config.output_root, "requests", safe_id)
    metadata_path = base / METADATA_FILENAME
    provenance_path = base / PROVENANCE_FILENAME
    if not metadata_path.is_file() or not provenance_path.is_file():
        from ssri_model.orchestration.exceptions import BatchManifestError

        raise BatchManifestError(f"Inference metadata not found for request_id: {safe_id}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    return {"metadata": metadata, "provenance": provenance}


def fetch_batch_status(
    *,
    service_config: ServiceConfig,
    batch_id: str,
    output_root: str | None = None,
) -> dict[str, Any]:
    manifest_path = resolve_batch_manifest_path(
        service_config=service_config,
        batch_id=batch_id,
        output_root=output_root,
    )
    status_result = get_batch_status(manifest_path)
    manifest = load_batch_manifest(manifest_path)
    return {
        "batch_id": status_result.batch_id,
        "status": status_result.status,
        "total_jobs": status_result.summary.total,
        "completed_jobs": status_result.summary.completed,
        "failed_jobs": status_result.summary.failed,
        "skipped_jobs": status_result.summary.skipped,
        "pending_jobs": status_result.summary.pending,
        "running_jobs": status_result.summary.running,
        "manifest_path": status_result.manifest_path,
        "started_at": manifest.started_at,
        "completed_at": manifest.completed_at,
    }


def fetch_job_status(
    *,
    service_config: ServiceConfig,
    batch_id: str,
    job_id: str,
    output_root: str | None = None,
) -> dict[str, Any]:
    from ssri_model.orchestration.jobs import sanitize_job_id

    safe_batch_id = sanitize_request_id(batch_id)
    safe_job_id = sanitize_job_id(job_id)
    manifest_path = resolve_batch_manifest_path(
        service_config=service_config,
        batch_id=safe_batch_id,
        output_root=output_root,
    )
    manifest = load_batch_manifest(manifest_path)
    job_status = get_job_status(manifest, safe_job_id)
    record = next(item for item in manifest.jobs if item.job_id == safe_job_id)
    return {
        "batch_id": safe_batch_id,
        "job_id": job_status.job_id,
        "status": job_status.status,
        "output_dir": job_status.output_dir,
        "error_type": job_status.error_type,
        "error_message": job_status.error_message,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
    }
