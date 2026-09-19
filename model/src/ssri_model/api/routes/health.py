"""Health and readiness routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from ssri_model.api.config import APIConfig
from ssri_model.api.dependencies import get_api_config
from ssri_model.api.errors import ErrorCode, api_error_response
from ssri_model.api.schemas import HealthResponse, ReadinessResponse
from ssri_model.infrastructure.health import check_infrastructure_health
from ssri_model.service.validation import validate_service_config

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def root_health(api_config: APIConfig = Depends(get_api_config)) -> HealthResponse:
    return HealthResponse(status="ok", service=api_config.service_name)


def health_router(prefix: str) -> APIRouter:
    prefixed = APIRouter(prefix=prefix, tags=["health"])

    @prefixed.get("/health", response_model=HealthResponse)
    def versioned_health(
        api_config: APIConfig = Depends(get_api_config),
    ) -> HealthResponse:
        return HealthResponse(status="ok", service=api_config.service_name)

    @prefixed.get("/ready")
    def readiness(api_config: APIConfig = Depends(get_api_config)) -> JSONResponse:
        try:
            validate_service_config(api_config.service_config)
            output_root = Path(api_config.output_root)
            output_root.mkdir(parents=True, exist_ok=True)
            probe = output_root / ".ready_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            infra = check_infrastructure_health(api_config.infrastructure_config)
            if not infra.ready:
                return api_error_response(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    code=ErrorCode.SERVICE_NOT_READY,
                    message="Infrastructure dependencies are not ready.",
                    details={"infrastructure": infra.to_dict()},
                )
        except Exception as exc:
            return api_error_response(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code=ErrorCode.SERVICE_NOT_READY,
                message=f"Service is not ready: {exc}",
            )
        payload = ReadinessResponse(
            status="ready",
            service=api_config.service_name,
            infrastructure=check_infrastructure_health(
                api_config.infrastructure_config
            ).to_dict(),
        )
        return JSONResponse(status_code=status.HTTP_200_OK, content=payload.model_dump())

    return prefixed
