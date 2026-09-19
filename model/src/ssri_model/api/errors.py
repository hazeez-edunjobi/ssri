"""Consistent API error handling for SSRI FastAPI."""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ssri_model.auth.exceptions import AuthenticationError, AuthorizationError, InvalidAuthConfigError
from ssri_model.inference.exceptions import InferenceError
from ssri_model.orchestration.exceptions import (
    BatchExistsError,
    BatchManifestError,
    OrchestrationError,
)
from ssri_model.service.exceptions import (
    InvalidServiceConfigError,
    InvalidServiceRequestError,
    OutputFormatError,
    PathSafetyError,
    ScientificGateError,
    ServiceError,
)
from ssri_model.api.rate_limit import RateLimitExceeded
from ssri_model.jobs.exceptions import (
    AsyncDisabledError,
    IdempotencyConflictError,
    JobAccessDeniedError,
    JobAlreadyCompletedError,
    JobCannotCancelError,
    JobNotFoundError,
    JobQueueFullError,
)

logger = logging.getLogger(__name__)

_PATH_PATTERN = re.compile(r"(?:[A-Za-z]:\\|/)[^\s\"']+")


class ErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_INFERENCE_REQUEST = "INVALID_INFERENCE_REQUEST"
    INVALID_BATCH_REQUEST = "INVALID_BATCH_REQUEST"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    PATH_SAFETY_VIOLATION = "PATH_SAFETY_VIOLATION"
    SCIENTIFIC_GATE_REJECTED = "SCIENTIFIC_GATE_REJECTED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONFLICT = "CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SERVICE_NOT_READY = "SERVICE_NOT_READY"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_ACCESS_DENIED = "JOB_ACCESS_DENIED"
    JOB_ALREADY_COMPLETED = "JOB_ALREADY_COMPLETED"
    JOB_CANNOT_CANCEL = "JOB_CANNOT_CANCEL"
    ASYNC_DISABLED = "ASYNC_DISABLED"
    JOB_QUEUE_FULL = "JOB_QUEUE_FULL"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"


class APIErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class APIErrorResponse(BaseModel):
    error: APIErrorDetail


def sanitize_error_message(message: str) -> str:
    """Remove filesystem paths and other sensitive details from client messages."""
    sanitized = _PATH_PATTERN.sub("<path>", message)
    if len(sanitized) > 500:
        return sanitized[:497] + "..."
    return sanitized


def api_error_response(
    *,
    status_code: int,
    code: ErrorCode,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload = APIErrorResponse(
        error=APIErrorDetail(
            code=code,
            message=sanitize_error_message(message),
            details=details or {},
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthenticationError)
    async def _authentication_handler(_: Request, exc: AuthenticationError) -> JSONResponse:
        message = str(exc)
        code = (
            ErrorCode.AUTHENTICATION_REQUIRED
            if "required" in message.lower()
            else ErrorCode.INVALID_CREDENTIALS
        )
        response = api_error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=code,
            message=message,
        )
        response.headers["WWW-Authenticate"] = "Bearer"
        return response

    @app.exception_handler(AuthorizationError)
    async def _authorization_handler(_: Request, exc: AuthorizationError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message=str(exc),
        )

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        response = api_error_response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message="Rate limit exceeded.",
            details={"retry_after_seconds": int(exc.retry_after_seconds) + 1},
        )
        response.headers["Retry-After"] = str(int(exc.retry_after_seconds) + 1)
        return response

    @app.exception_handler(JobNotFoundError)
    async def _job_not_found_handler(_: Request, exc: JobNotFoundError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.JOB_NOT_FOUND,
            message="Job not found.",
        )

    @app.exception_handler(JobAccessDeniedError)
    async def _job_access_handler(_: Request, exc: JobAccessDeniedError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.JOB_NOT_FOUND,
            message="Job not found.",
        )

    @app.exception_handler(JobCannotCancelError)
    async def _job_cancel_handler(_: Request, exc: JobCannotCancelError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code=ErrorCode.JOB_CANNOT_CANCEL,
            message=str(exc),
        )

    @app.exception_handler(JobAlreadyCompletedError)
    async def _job_completed_handler(_: Request, exc: JobAlreadyCompletedError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code=ErrorCode.JOB_ALREADY_COMPLETED,
            message=str(exc),
        )

    @app.exception_handler(AsyncDisabledError)
    async def _async_disabled_handler(_: Request, exc: AsyncDisabledError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code=ErrorCode.ASYNC_DISABLED,
            message=str(exc),
        )

    @app.exception_handler(JobQueueFullError)
    async def _queue_full_handler(_: Request, exc: JobQueueFullError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code=ErrorCode.JOB_QUEUE_FULL,
            message=str(exc),
        )

    @app.exception_handler(IdempotencyConflictError)
    async def _idempotency_handler(_: Request, exc: IdempotencyConflictError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code=ErrorCode.IDEMPOTENCY_CONFLICT,
            message=str(exc),
        )

    @app.exception_handler(InvalidAuthConfigError)
    async def _invalid_auth_config_handler(
        _: Request, exc: InvalidAuthConfigError
    ) -> JSONResponse:
        message = str(exc)
        status_code = status.HTTP_400_BAD_REQUEST
        code = ErrorCode.INVALID_CONFIGURATION
        if "not found" in message.lower():
            status_code = status.HTTP_404_NOT_FOUND
            code = ErrorCode.RESOURCE_NOT_FOUND
        return api_error_response(status_code=status_code, code=code, message=message)

    @app.exception_handler(PathSafetyError)
    async def _path_safety_handler(_: Request, exc: PathSafetyError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.PATH_SAFETY_VIOLATION,
            message=str(exc),
        )

    @app.exception_handler(InvalidServiceRequestError)
    async def _invalid_request_handler(
        _: Request, exc: InvalidServiceRequestError
    ) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.INVALID_REQUEST,
            message=str(exc),
        )

    @app.exception_handler(OutputFormatError)
    async def _output_format_handler(_: Request, exc: OutputFormatError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.INVALID_INFERENCE_REQUEST,
            message=str(exc),
        )

    @app.exception_handler(InvalidServiceConfigError)
    async def _invalid_config_handler(
        _: Request, exc: InvalidServiceConfigError
    ) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.INVALID_CONFIGURATION,
            message=str(exc),
        )

    @app.exception_handler(ScientificGateError)
    async def _scientific_gate_handler(_: Request, exc: ScientificGateError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            code=ErrorCode.SCIENTIFIC_GATE_REJECTED,
            message=str(exc),
        )

    @app.exception_handler(BatchManifestError)
    async def _manifest_handler(_: Request, exc: BatchManifestError) -> JSONResponse:
        message = str(exc)
        status_code = status.HTTP_404_NOT_FOUND
        if "not found" not in message.lower():
            status_code = status.HTTP_400_BAD_REQUEST
        return api_error_response(
            status_code=status_code,
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message=message,
        )

    @app.exception_handler(BatchExistsError)
    async def _batch_exists_handler(_: Request, exc: BatchExistsError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code=ErrorCode.CONFLICT,
            message=str(exc),
        )

    @app.exception_handler(OrchestrationError)
    async def _orchestration_handler(_: Request, exc: OrchestrationError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.INVALID_BATCH_REQUEST,
            message=str(exc),
        )

    @app.exception_handler(InferenceError)
    async def _inference_handler(_: Request, exc: InferenceError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.INVALID_INFERENCE_REQUEST,
            message=str(exc),
        )

    @app.exception_handler(ServiceError)
    async def _service_handler(_: Request, exc: ServiceError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.INVALID_REQUEST,
            message=str(exc),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return api_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=ErrorCode.VALIDATION_ERROR,
            message="Request validation failed.",
            details={"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error for %s", request.url.path)
        return api_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=ErrorCode.INTERNAL_ERROR,
            message="An internal server error occurred.",
        )
