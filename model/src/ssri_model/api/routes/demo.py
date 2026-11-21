"""Presentation demo catalogue routes (SSRI_DEMO_MODE only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from ssri_model.api.config import APIConfig
from ssri_model.api.demo_assessment import (
    ASSESSMENT_PREVIEW_LABEL,
    ILLUSTRATIVE_DISCLOSURE,
    list_demo_scenarios,
)
from ssri_model.api.dependencies import get_api_config
from ssri_model.api.errors import ErrorCode, api_error_response

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/scenarios")
def demo_scenarios(api_config: APIConfig = Depends(get_api_config)) -> JSONResponse:
    """List deterministic illustrative scenarios when presentation demo mode is on."""
    if not api_config.demo_mode:
        return api_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Presentation demo catalogue is unavailable when SSRI_DEMO_MODE is off.",
        )
    scenarios = list_demo_scenarios()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "demo_mode": True,
            "label": ASSESSMENT_PREVIEW_LABEL,
            "disclosure": ILLUSTRATIVE_DISCLOSURE,
            "count": len(scenarios),
            "scenarios": scenarios,
        },
    )
