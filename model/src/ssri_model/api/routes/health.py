"""Health and readiness routes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from ssri_model.api.config import APIConfig
from ssri_model.api.dependencies import get_api_config
from ssri_model.api.errors import ErrorCode, api_error_response
from ssri_model.api.registry_status import active_model_registry_status
from ssri_model.api.schemas import HealthResponse, ReadinessResponse
from ssri_model.infrastructure.health import check_infrastructure_health
from ssri_model.service.validation import validate_service_config

router = APIRouter(tags=["health"])


def _public_geophysics_status(raw: dict[str, Any]) -> dict[str, Any]:
    """Strip absolute paths from geophysics readiness (safe for anonymous clients)."""
    assets = []
    for item in raw.get("assets") or []:
        assets.append(
            {
                "filename": item.get("filename"),
                "present": bool(item.get("present")),
                "sha256_ok": bool(item.get("sha256_ok")),
                "valid_geotiff": bool(item.get("valid_geotiff")),
                "materialized": bool(item.get("materialized")),
                "bytes": item.get("bytes"),
                "detail": item.get("detail"),
                "raster": item.get("raster"),
            }
        )
    return {
        "available": bool(raw.get("available")),
        "materialized_count": int(raw.get("materialized_count") or 0),
        "assets": assets,
        "detail": raw.get("detail"),
    }


def _geophysics_required_for_readiness(api_config: APIConfig) -> bool:
    """Production (and live-acquisition) must expose readable Lagos geophysics clips."""
    environment = str(api_config.service_config.environment.value).lower()
    if environment == "production":
        return True
    live = (os.getenv("SSRI_LIVE_ACQUISITION_ENABLED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return live


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
        """Readiness: filesystem probe + infra + durable geophysics recovery.

        Postgres and Redis probes use connect/socket timeouts (typically 5s each).
        This handler does not depend on Supabase Auth or Celery workers.
        """
        try:
            validate_service_config(api_config.service_config)
            output_root = Path(api_config.output_root)
            output_root.mkdir(parents=True, exist_ok=True)
            probe = output_root / ".ready_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            # Single probe — previously this path checked infrastructure twice.
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
                message=f"Service is not ready: {type(exc).__name__}",
            )
        model_registry = active_model_registry_status(api_config.output_root)
        geophysics_raw: dict[str, Any]
        try:
            from ssri_model.storage.durable import ensure_geophysics_assets_local

            geophysics_raw = ensure_geophysics_assets_local()
        except Exception as exc:  # noqa: BLE001
            geophysics_raw = {
                "available": False,
                "materialized_count": 0,
                "assets": [],
                "detail": f"geophysics recovery failed: {type(exc).__name__}",
            }
        geophysics = _public_geophysics_status(geophysics_raw)
        if _geophysics_required_for_readiness(api_config) and not geophysics["available"]:
            return api_error_response(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code=ErrorCode.SERVICE_NOT_READY,
                message=(
                    "Required geophysics assets are not readable after durable recovery."
                ),
                details={"geophysics": geophysics, "model_registry": model_registry},
            )
        payload = ReadinessResponse(
            status="ready",
            service=api_config.service_name,
            infrastructure=infra.to_dict(),
            demo_mode=bool(api_config.demo_mode),
            model_registry=model_registry,
            geophysics=geophysics,
        )
        return JSONResponse(status_code=status.HTTP_200_OK, content=payload.model_dump())

    return prefixed
