"""Live AOI feature acquisition for assessments (reuses Stage-1 feature stack)."""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from ssri_model.service.exceptions import InvalidServiceRequestError


def live_acquisition_enabled() -> bool:
    return os.getenv("SSRI_LIVE_ACQUISITION_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }


def _map_acquisition_failure(exc: BaseException) -> InvalidServiceRequestError:
    """Map pipeline exceptions to actionable API errors (no credential misdirection)."""
    name = type(exc).__name__
    message = str(exc)
    lowered = f"{name}: {message}".lower()

    if "geophysics" in lowered or "eigen-6c4" in lowered or "eigen6c4" in lowered:
        return InvalidServiceRequestError(
            "Live feature acquisition failed due to geophysics configuration/data. "
            "Check SSRI_GRAVITY_SOURCE, GRAVITY_DATA_PATH / EIGEN6C4_DATA_PATH, and "
            "MAGNETIC_DATA_PATH (container paths must be under /data/geophysics/, "
            "not Windows host paths). "
            f"Cause: {name}: {message}"
        )
    if "topography" in lowered or "opentopo" in lowered or "dem" in lowered:
        return InvalidServiceRequestError(
            "Live feature acquisition failed during DEM download. "
            "OpenTopography uses OPENTOPOGRAPHY_API_KEY; on rate-limit/unavailable "
            "the pipeline falls back to GEE COP30 (GOOGLE_APPLICATION_CREDENTIALS / "
            "GEE_SERVICE_ACCOUNT / GCP_PROJECT_ID). "
            f"Cause: {name}: {message}"
        )
    if "gee" in lowered or "earth engine" in lowered or "ee." in lowered:
        return InvalidServiceRequestError(
            "Live feature acquisition failed during Google Earth Engine access. "
            "Ensure GOOGLE_APPLICATION_CREDENTIALS, GEE_SERVICE_ACCOUNT, and "
            "GCP_PROJECT_ID / GEE_PROJECT are configured. "
            f"Cause: {name}: {message}"
        )
    return InvalidServiceRequestError(
        f"Live feature acquisition failed. Cause: {name}: {message}"
    )


def acquire_feature_array_for_bbox(
    bbox: tuple[float, float, float, float],
    *,
    output_dir: Path,
    resolution_m: float = 30.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Build a feature stack for a WGS84 bbox using existing data pipeline.

    Requires GEE (+ OpenTopography or GEE DEM fallback) and configured local
    geophysics rasters.
    """
    if not live_acquisition_enabled():
        raise InvalidServiceRequestError(
            "Live AOI feature acquisition is disabled. "
            "Set SSRI_LIVE_ACQUISITION_ENABLED=true and configure GEE/OpenTopography "
            "plus local geophysics paths."
        )
    try:
        from ssri_model.data.feature_engineering import build_feature_stack
    except Exception as exc:  # pragma: no cover
        raise InvalidServiceRequestError(
            f"Feature acquisition dependencies unavailable: {type(exc).__name__}"
        ) from exc

    end = date.today()
    start = end - timedelta(days=365)
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        stack = build_feature_stack(
            bbox,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            resolution_m=resolution_m,
            output_dir=output_dir,
        )
    except Exception as exc:
        raise _map_acquisition_failure(exc) from exc

    array = np.asarray(stack.feature_tensor)
    sources = {}
    if isinstance(stack.manifest, dict):
        sources = dict(stack.manifest.get("sources") or {})
    meta = {
        "bbox": bbox,
        "resolution_m": resolution_m,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "output_dir": str(output_dir),
        "channel_names": list(stack.channel_names),
        "sources": sources,
        "crs": stack.manifest.get("crs") if isinstance(stack.manifest, dict) else None,
    }
    return array, meta
