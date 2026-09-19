"""Topography retrieval and terrain derivative computation for SSRI."""

from __future__ import annotations

import logging
import math
import os
import re
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Union

import numpy as np
import rasterio
import requests
from dotenv import load_dotenv
from rasterio.transform import Affine
from scipy.ndimage import maximum_filter, minimum_filter

load_dotenv()

if TYPE_CHECKING:
    import ee

logger = logging.getLogger(__name__)

OPENTOPOGRAPHY_API_URL = "https://portal.opentopography.org/API/globaldem"
DEFAULT_NODATA = -9999.0
RELATIVE_RELIEF_WINDOW = 5
VALLEY_DEPTH_WINDOW = 5
# OpenTopography rejects bboxes with either side below ~250 m; default above that.
DEFAULT_OPENTOPO_MIN_BBOX_SIDE_M = 500.0
METERS_PER_DEGREE_LAT = 111_320.0
# Earth Engine DEM collections (scientifically equivalent public DEMs).
GEE_COP30_COLLECTION = "COPERNICUS/DEM/GLO30"
GEE_SRTM_IMAGE = "USGS/SRTMGL1_003"
# auto: OpenTopography first, GEE on rate-limit / auth failures.
DEFAULT_DEM_PROVIDER = "auto"

BoundingBox = tuple[float, float, float, float]
AOI = Union[BoundingBox, "ee.Geometry"]


class TopographyError(Exception):
    """Base exception for topography module errors."""


class TopographyConfigError(TopographyError):
    """Raised when topography configuration is invalid."""


class TopographyDownloadError(TopographyError):
    """Raised when DEM download from OpenTopography fails."""


class TopographyProcessingError(TopographyError):
    """Raised when terrain derivative computation fails."""


class DEMType(str, Enum):
    """Supported OpenTopography global DEM products."""

    SRTM = "SRTMGL1"
    COPERNICUS = "COP30"


@dataclass(frozen=True)
class TopographyConfig:
    """OpenTopography API configuration loaded from environment variables."""

    api_key: str
    min_bbox_side_m: float = DEFAULT_OPENTOPO_MIN_BBOX_SIDE_M

    @classmethod
    def from_env(cls) -> TopographyConfig:
        """Load OpenTopography configuration from environment variables."""
        api_key = (os.getenv("OPENTOPOGRAPHY_API_KEY") or "").strip()
        if not api_key:
            raise TopographyConfigError(
                "Missing required environment variable: OPENTOPOGRAPHY_API_KEY"
            )
        raw_min = os.getenv("SSRI_OPENTOPO_MIN_BBOX_SIDE_M", "").strip()
        if raw_min:
            try:
                min_bbox_side_m = float(raw_min)
            except ValueError as exc:
                raise TopographyConfigError(
                    "SSRI_OPENTOPO_MIN_BBOX_SIDE_M must be a positive number"
                ) from exc
        else:
            min_bbox_side_m = DEFAULT_OPENTOPO_MIN_BBOX_SIDE_M
        if min_bbox_side_m <= 0:
            raise TopographyConfigError(
                "SSRI_OPENTOPO_MIN_BBOX_SIDE_M must be positive"
            )
        return cls(api_key=api_key, min_bbox_side_m=min_bbox_side_m)


@dataclass(frozen=True)
class RasterGrid:
    """In-memory single-band raster aligned to a DEM grid."""

    data: np.ndarray
    transform: Affine
    crs: rasterio.crs.CRS
    nodata: float = DEFAULT_NODATA

    @property
    def height(self) -> int:
        """Return raster height in pixels."""
        return int(self.data.shape[0])

    @property
    def width(self) -> int:
        """Return raster width in pixels."""
        return int(self.data.shape[1])

    @property
    def shape(self) -> tuple[int, int]:
        """Return raster shape as ``(height, width)``."""
        return (self.height, self.width)


def _get_whitebox() -> object:
    """Return a WhiteboxTools instance (overridable in tests).

    The ``whitebox`` package downloads its native binary into site-packages on
    first use. Non-root containers cannot write there — bake the binary into
    the image (see Dockerfile) or set ``SSRI_WHITEBOX_DIR`` to a directory that
    already contains ``whitebox_tools``.
    """
    import os
    from pathlib import Path

    import whitebox
    from whitebox import whitebox_tools as wbt_mod

    configured = os.getenv("SSRI_WHITEBOX_DIR", "").strip()
    if configured:
        exe_dir = Path(configured)
        exe = exe_dir / "whitebox_tools"
        if not exe.is_file():
            raise TopographyProcessingError(
                f"SSRI_WHITEBOX_DIR={configured!r} does not contain whitebox_tools"
            )
        original = wbt_mod.download_wbt
        wbt_mod.download_wbt = lambda *args, **kwargs: None  # type: ignore[assignment]
        try:
            tools = whitebox.WhiteboxTools()
            tools.set_whitebox_dir(str(exe_dir))
            return tools
        finally:
            wbt_mod.download_wbt = original

    pkg_exe = Path(wbt_mod.__file__).resolve().parent / "whitebox_tools"
    if not pkg_exe.is_file() and not os.access(pkg_exe.parent, os.W_OK):
        raise TopographyProcessingError(
            "WhiteboxTools binary is missing and site-packages is not writable. "
            "Rebuild the API image (Dockerfile pre-downloads WBT) or set "
            "SSRI_WHITEBOX_DIR to a directory containing whitebox_tools."
        )
    return whitebox.WhiteboxTools()


def _resolve_bounds(aoi: AOI) -> BoundingBox:
    """Normalize AOI input to a WGS84 bounding box."""
    if isinstance(aoi, tuple):
        if len(aoi) != 4:
            raise TopographyError(
                f"Bounding box must contain four values, received {len(aoi)}"
            )
        min_lon, min_lat, max_lon, max_lat = aoi
        if min_lon >= max_lon or min_lat >= max_lat:
            raise TopographyError(
                "Invalid bounding box: min values must be less than max values"
            )
        return aoi

    import ee

    if isinstance(aoi, ee.Geometry):
        coordinates = aoi.bounds().getInfo()["coordinates"][0]
        lons = [point[0] for point in coordinates]
        lats = [point[1] for point in coordinates]
        return (min(lons), min(lats), max(lons), max(lats))

    raise TopographyError(f"Unsupported AOI type: {type(aoi)!r}")


def _bbox_side_lengths_m(bbox: BoundingBox) -> tuple[float, float]:
    """Return approximate ``(width_m, height_m)`` for a WGS84 bbox."""
    min_lon, min_lat, max_lon, max_lat = bbox
    mid_lat = 0.5 * (min_lat + max_lat)
    meters_per_deg_lon = METERS_PER_DEGREE_LAT * max(
        1e-6, abs(math.cos(math.radians(mid_lat)))
    )
    width_m = (max_lon - min_lon) * meters_per_deg_lon
    height_m = (max_lat - min_lat) * METERS_PER_DEGREE_LAT
    return width_m, height_m


def ensure_min_bbox_side_m(
    bbox: BoundingBox,
    *,
    min_side_m: float = DEFAULT_OPENTOPO_MIN_BBOX_SIDE_M,
) -> BoundingBox:
    """Expand a WGS84 bbox so both sides are at least ``min_side_m`` meters.

    OpenTopography rejects requests where either side is below ~250 m. Small
    assessment AOIs are expanded symmetrically about the bbox center without
    changing axis order ``(min_lon, min_lat, max_lon, max_lat)``.
    """
    if min_side_m <= 0:
        raise TopographyError("min_side_m must be positive")
    min_lon, min_lat, max_lon, max_lat = bbox
    if min_lon >= max_lon or min_lat >= max_lat:
        raise TopographyError(
            "Invalid bounding box: min values must be less than max values"
        )

    mid_lon = 0.5 * (min_lon + max_lon)
    mid_lat = 0.5 * (min_lat + max_lat)
    meters_per_deg_lon = METERS_PER_DEGREE_LAT * max(
        1e-6, abs(math.cos(math.radians(mid_lat)))
    )
    width_m, height_m = _bbox_side_lengths_m(bbox)

    target_width_m = max(width_m, min_side_m)
    target_height_m = max(height_m, min_side_m)
    half_width_deg = (target_width_m * 0.5) / meters_per_deg_lon
    half_height_deg = (target_height_m * 0.5) / METERS_PER_DEGREE_LAT

    padded = (
        max(-180.0, mid_lon - half_width_deg),
        max(-90.0, mid_lat - half_height_deg),
        min(180.0, mid_lon + half_width_deg),
        min(90.0, mid_lat + half_height_deg),
    )
    if padded[0] >= padded[2] or padded[1] >= padded[3]:
        raise TopographyError(
            f"Failed to expand bbox {bbox} to min_side_m={min_side_m}"
        )
    return padded


def _redact_opentopo_secrets(text: str) -> str:
    """Remove OpenTopography API keys from URLs and error text."""
    return re.sub(
        r"(API_Key=)[^&\s\"']+",
        r"\1***REDACTED***",
        text,
        flags=re.IGNORECASE,
    )


def _write_geotiff(grid: RasterGrid, output_path: Path) -> None:
    """Write a single-band GeoTIFF preserving CRS and affine transform."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": grid.height,
        "width": grid.width,
        "count": 1,
        "dtype": grid.data.dtype,
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": grid.nodata,
    }
    with rasterio.open(output_path, "w", **profile) as dataset:
        dataset.write(grid.data, 1)


def _read_geotiff(path: Path) -> RasterGrid:
    """Read a single-band GeoTIFF into a ``RasterGrid``."""
    with rasterio.open(path) as dataset:
        data = dataset.read(1).astype(np.float64)
        nodata = dataset.nodata if dataset.nodata is not None else DEFAULT_NODATA
        return RasterGrid(
            data=data,
            transform=dataset.transform,
            crs=dataset.crs,
            nodata=float(nodata),
        )


def _valid_mask(grid: RasterGrid) -> np.ndarray:
    """Return a boolean mask of finite, non-nodata pixels."""
    mask = np.isfinite(grid.data)
    if grid.nodata is not None:
        mask &= grid.data != grid.nodata
    return mask


def _apply_reference_nodata(reference: RasterGrid, data: np.ndarray) -> np.ndarray:
    """Mask invalid reference pixels and replace with nodata."""
    output = data.copy()
    invalid = ~_valid_mask(reference)
    output[invalid] = reference.nodata
    return output


def _validate_grid_alignment(reference: RasterGrid, derived: RasterGrid) -> None:
    """Ensure derived raster matches the reference DEM grid."""
    if reference.shape != derived.shape:
        raise TopographyProcessingError(
            "Derived raster shape "
            f"{derived.height}x{derived.width} does not match reference "
            f"{reference.height}x{reference.width}"
        )
    if reference.transform != derived.transform:
        raise TopographyProcessingError(
            "Derived raster affine transform does not match reference DEM"
        )
    if reference.crs != derived.crs:
        raise TopographyProcessingError(
            "Derived raster CRS does not match reference DEM"
        )


def _run_whitebox_tool(
    dem: RasterGrid,
    tool: str,
    output_name: str,
    **kwargs: object,
) -> RasterGrid:
    """Execute a WhiteboxTools terrain analysis and return a aligned raster."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        dem_path = tmp_path / "dem.tif"
        output_path = tmp_path / output_name
        _write_geotiff(dem, dem_path)

        wbt = _get_whitebox()
        wbt.verbose = False
        setattr(wbt, "work_dir", str(tmp_path))

        try:
            method = getattr(wbt, tool)
            success = method(str(dem_path), str(output_path), **kwargs)
        except Exception as exc:
            raise TopographyProcessingError(
                f"WhiteboxTools '{tool}' failed: {exc}"
            ) from exc

        if success is False:
            raise TopographyProcessingError(
                f"WhiteboxTools '{tool}' returned failure for {dem_path}"
            )

        if not output_path.exists():
            raise TopographyProcessingError(
                f"WhiteboxTools '{tool}' did not produce output at {output_path}"
            )

        result = _read_geotiff(output_path)
        _validate_grid_alignment(dem, result)
        result_data = _apply_reference_nodata(dem, result.data)
        return RasterGrid(
            data=result_data,
            transform=result.transform,
            crs=result.crs,
            nodata=dem.nodata,
        )


def _dem_provider() -> str:
    """Return ``opentopo``, ``gee``, or ``auto`` from ``SSRI_DEM_PROVIDER``."""
    raw = (os.getenv("SSRI_DEM_PROVIDER") or DEFAULT_DEM_PROVIDER).strip().lower()
    if raw not in {"opentopo", "gee", "auto"}:
        raise TopographyConfigError(
            f"SSRI_DEM_PROVIDER must be opentopo|gee|auto, received {raw!r}"
        )
    return raw


def _is_opentopo_rate_or_auth_error(message: str) -> bool:
    lowered = message.lower()
    return any(
        token in lowered
        for token in (
            "401",
            "403",
            "429",
            "rate limit",
            "maximum rate",
            "unauthorized",
            "forbidden",
        )
    )


def download_dem_from_gee(
    aoi: AOI,
    output_path: Path | str,
    dem_type: DEMType = DEMType.COPERNICUS,
    *,
    scale_m: float = 30.0,
) -> Path:
    """Download a DEM GeoTIFF via Earth Engine (COP30 / SRTM).

    Used when OpenTopography is unavailable (e.g. free-tier 50 calls/24h).
    Product is the same public DEM family documented in the FeatureStack
    manifest (Copernicus GLO-30 or SRTM GL1).
    """
    from rasterio.transform import from_bounds

    from ssri_model.data.gee_client import initialize

    initialize()
    import ee

    resolved = _resolve_bounds(aoi)
    min_lon, min_lat, max_lon, max_lat = ensure_min_bbox_side_m(
        resolved,
        min_side_m=DEFAULT_OPENTOPO_MIN_BBOX_SIDE_M,
    )
    geometry = ee.Geometry.Rectangle(
        [min_lon, min_lat, max_lon, max_lat], proj="EPSG:4326", geodesic=False
    )

    if dem_type == DEMType.COPERNICUS:
        image = (
            ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1")
            .select("DEM")
            .mosaic()
        )
        source_name = "COPERNICUS/DEM/GLO30_2024_1"
    else:
        image = ee.Image(GEE_SRTM_IMAGE).select("elevation")
        source_name = GEE_SRTM_IMAGE

    logger.info(
        "Downloading DEM via Earth Engine source=%s bbox=%s scale_m=%s",
        source_name,
        (min_lon, min_lat, max_lon, max_lat),
        scale_m,
    )
    prepared = (
        ee.Image(image)
        .select(0)
        .rename("elevation")
        .toFloat()
        .unmask(DEFAULT_NODATA)
        .clipToBoundsAndScale(geometry=geometry, scale=scale_m)
    )
    try:
        sampled = prepared.sampleRectangle(region=geometry, defaultValue=DEFAULT_NODATA)
        info = sampled.getInfo()
    except Exception as exc:  # noqa: BLE001 — wrap EE failures
        raise TopographyDownloadError(
            f"Earth Engine DEM download failed for {dem_type.value}: {exc}"
        ) from exc

    props = info.get("properties") or {}
    raw = props.get("elevation")
    if raw is None:
        for candidate in props.values():
            if isinstance(candidate, list):
                raw = candidate
                break
    if raw is None:
        raise TopographyDownloadError(
            f"Earth Engine DEM response missing elevation band; keys={list(props)}"
        )

    data = np.asarray(raw, dtype=np.float64)
    if data.ndim != 2 or data.size == 0:
        raise TopographyDownloadError(
            f"Earth Engine DEM returned invalid array shape={getattr(data, 'shape', None)}"
        )

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    transform = from_bounds(min_lon, min_lat, max_lon, max_lat, data.shape[1], data.shape[0])
    profile = {
        "driver": "GTiff",
        "height": data.shape[0],
        "width": data.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": transform,
        "nodata": DEFAULT_NODATA,
        "compress": "deflate",
    }
    try:
        with rasterio.open(destination, "w", **profile) as dst:
            dst.write(data.astype(np.float32), 1)
            dst.update_tags(ssri_dem_source=f"gee:{source_name}")
    except OSError as exc:
        raise TopographyDownloadError(
            f"Failed to write GEE DEM GeoTIFF to {destination}: {exc}"
        ) from exc

    logger.info("Saved Earth Engine DEM to %s shape=%s", destination, data.shape)
    return destination


def download_dem_from_opentopo(
    aoi: AOI,
    output_path: Path | str,
    dem_type: DEMType = DEMType.SRTM,
    config: TopographyConfig | None = None,
    timeout: float = 120.0,
) -> Path:
    """Download a DEM GeoTIFF from OpenTopography for an AOI."""
    cfg = config or TopographyConfig.from_env()
    resolved = _resolve_bounds(aoi)
    min_lon, min_lat, max_lon, max_lat = ensure_min_bbox_side_m(
        resolved,
        min_side_m=cfg.min_bbox_side_m,
    )
    if (min_lon, min_lat, max_lon, max_lat) != resolved:
        logger.info(
            "Expanded OpenTopography AOI from %s to %s (min_side_m=%.1f)",
            resolved,
            (min_lon, min_lat, max_lon, max_lat),
            cfg.min_bbox_side_m,
        )
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    params = {
        "demtype": dem_type.value,
        "south": min_lat,
        "north": max_lat,
        "west": min_lon,
        "east": max_lon,
        "outputFormat": "GTiff",
        "API_Key": cfg.api_key,
    }
    # Log the exact OpenTopography request with the API key redacted (diagnosis).
    redacted_params = {**params, "API_Key": "***REDACTED***"}
    prepared = requests.Request(
        "GET", OPENTOPOGRAPHY_API_URL, params=redacted_params
    ).prepare()
    width_m, height_m = _bbox_side_lengths_m((min_lon, min_lat, max_lon, max_lat))
    logger.info(
        "OpenTopography request URL (API key redacted): %s",
        prepared.url,
    )
    logger.info(
        "OpenTopography request params: demtype=%s south=%s north=%s west=%s "
        "east=%s outputFormat=%s API_Key_len=%d API_Key_empty=%s "
        "delta_lon=%.8f delta_lat=%.8f width_m=%.2f height_m=%.2f",
        params["demtype"],
        params["south"],
        params["north"],
        params["west"],
        params["east"],
        params["outputFormat"],
        len(cfg.api_key),
        cfg.api_key.strip() == "",
        float(params["east"]) - float(params["west"]),
        float(params["north"]) - float(params["south"]),
        width_m,
        height_m,
    )

    try:
        response = requests.get(
            OPENTOPOGRAPHY_API_URL,
            params=params,
            timeout=timeout,
            stream=True,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        body_preview = ""
        response_obj = getattr(exc, "response", None)
        if response_obj is not None:
            try:
                body_preview = (response_obj.text or "")[:500]
            except Exception:
                body_preview = ""
        message = _redact_opentopo_secrets(str(exc))
        if body_preview:
            message = f"{message} body={_redact_opentopo_secrets(body_preview)!r}"
        raise TopographyDownloadError(
            f"OpenTopography request failed for {dem_type.value}: {message}"
        ) from exc

    content_type = response.headers.get("Content-Type", "")
    if "text" in content_type or "html" in content_type or "json" in content_type:
        raise TopographyDownloadError(
            "OpenTopography returned an error response instead of GeoTIFF data"
        )

    try:
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    handle.write(chunk)
    except OSError as exc:
        raise TopographyDownloadError(
            f"Failed to write DEM GeoTIFF to {destination}: {exc}"
        ) from exc

    logger.info("OpenTopography DEM saved to %s", destination)
    return destination


# Once OpenTopography rate-limits in this process, stay on GEE for remaining calls.
_opentopo_rate_limited = False
# Last successful DEM acquisition provider label for FeatureStack provenance.
_last_dem_acquisition_source: str | None = None


def get_last_dem_acquisition_source() -> str | None:
    """Return the provider label from the most recent successful ``download_dem``."""
    return _last_dem_acquisition_source


def _set_last_dem_acquisition_source(label: str) -> None:
    global _last_dem_acquisition_source
    _last_dem_acquisition_source = label


def download_dem(
    aoi: AOI,
    output_path: Path | str,
    dem_type: DEMType = DEMType.SRTM,
    config: TopographyConfig | None = None,
    timeout: float = 120.0,
) -> Path:
    """Download a DEM GeoTIFF for an AOI (OpenTopography and/or Earth Engine).

    Provider selection via ``SSRI_DEM_PROVIDER``:

    - ``opentopo`` — OpenTopography only
    - ``gee`` — Earth Engine COP30/SRTM only
    - ``auto`` (default) — OpenTopography first; on rate-limit/auth errors,
      fall back to Earth Engine (same public DEM products)

    Args:
        aoi: Bounding box ``(min_lon, min_lat, max_lon, max_lat)`` or
            ``ee.Geometry`` (converted to bounds server-side).
        output_path: Destination path for the downloaded GeoTIFF.
        dem_type: DEM product identifier (COP30 or SRTM GL1).
        config: Optional OpenTopography configuration.
        timeout: HTTP request timeout in seconds (OpenTopography path).

    Returns:
        Path to the saved GeoTIFF.
    """
    global _opentopo_rate_limited

    provider = _dem_provider()
    destination = Path(output_path)
    product = dem_type.value

    if provider == "gee" or (provider == "auto" and _opentopo_rate_limited):
        path = download_dem_from_gee(aoi, destination, dem_type=dem_type)
        _set_last_dem_acquisition_source(f"gee_{product}")
        return path

    try:
        path = download_dem_from_opentopo(
            aoi, destination, dem_type=dem_type, config=config, timeout=timeout
        )
        _set_last_dem_acquisition_source(f"opentopo_{product}")
        return path
    except TopographyDownloadError as exc:
        if provider == "opentopo" or not _is_opentopo_rate_or_auth_error(str(exc)):
            raise
        _opentopo_rate_limited = True
        logger.warning(
            "OpenTopography DEM failed (%s); falling back to Earth Engine for "
            "this and subsequent calls in-process",
            exc,
        )
        path = download_dem_from_gee(aoi, destination, dem_type=dem_type)
        _set_last_dem_acquisition_source(f"gee_{product}_fallback_from_opentopo")
        return path
    except TopographyConfigError as exc:
        # Missing/invalid OpenTopo configuration is "unavailable" under auto mode.
        if provider != "auto":
            raise
        logger.warning(
            "OpenTopography not configured (%s); falling back to Earth Engine COP30/SRTM",
            exc,
        )
        path = download_dem_from_gee(aoi, destination, dem_type=dem_type)
        _set_last_dem_acquisition_source(f"gee_{product}_fallback_from_opentopo_config")
        return path


def load_dem(path: Path | str) -> RasterGrid:
    """Load a DEM GeoTIFF into memory.

    Args:
        path: Path to a single-band GeoTIFF.

    Returns:
        ``RasterGrid`` containing elevation values and georeferencing.

    Raises:
        TopographyProcessingError: If the file cannot be read.
    """
    dem_path = Path(path)
    logger.debug("Loading DEM from %s", dem_path)

    try:
        grid = _read_geotiff(dem_path)
    except Exception as exc:
        raise TopographyProcessingError(
            f"Failed to load DEM from {dem_path}: {exc}"
        ) from exc

    logger.debug(
        "Loaded DEM grid %dx%d with CRS %s",
        grid.width,
        grid.height,
        grid.crs,
    )
    return grid


def compute_slope(dem: RasterGrid) -> RasterGrid:
    """Compute slope in degrees using WhiteboxTools.

    Args:
        dem: Reference elevation grid.

    Returns:
        Slope raster aligned to the input DEM grid.
    """
    logger.info("Computing slope")
    return _run_whitebox_tool(dem, "slope", "slope.tif", zfactor=1.0)


def compute_plan_curvature(dem: RasterGrid) -> RasterGrid:
    """Compute plan curvature using WhiteboxTools.

    Args:
        dem: Reference elevation grid.

    Returns:
        Plan curvature raster aligned to the input DEM grid.
    """
    logger.info("Computing plan curvature")
    return _run_whitebox_tool(dem, "plan_curvature", "plan_curvature.tif")


def compute_profile_curvature(dem: RasterGrid) -> RasterGrid:
    """Compute profile curvature using WhiteboxTools.

    Args:
        dem: Reference elevation grid.

    Returns:
        Profile curvature raster aligned to the input DEM grid.
    """
    logger.info("Computing profile curvature")
    return _run_whitebox_tool(dem, "profile_curvature", "profile_curvature.tif")


def compute_twi(dem: RasterGrid) -> RasterGrid:
    """Compute Topographic Wetness Index (TWI) using WhiteboxTools.

    Whitebox ``wetness_index`` requires specific contributing area (SCA) and
    slope rasters, not the DEM directly.

    Args:
        dem: Reference elevation grid.

    Returns:
        TWI raster aligned to the input DEM grid.
    """
    logger.info("Computing topographic wetness index")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        dem_path = tmp_path / "dem.tif"
        slope_path = tmp_path / "slope.tif"
        sca_path = tmp_path / "sca.tif"
        output_path = tmp_path / "twi.tif"
        _write_geotiff(dem, dem_path)

        wbt = _get_whitebox()
        wbt.verbose = False
        setattr(wbt, "work_dir", str(tmp_path))

        try:
            slope_ok = wbt.slope(str(dem_path), str(slope_path), zfactor=1.0)
            sca_ok = wbt.fd8_flow_accumulation(
                str(dem_path),
                str(sca_path),
                out_type="specific contributing area",
            )
            success = wbt.wetness_index(
                str(sca_path),
                str(slope_path),
                str(output_path),
            )
        except Exception as exc:
            raise TopographyProcessingError(
                f"WhiteboxTools 'wetness_index' failed: {exc}"
            ) from exc

        if slope_ok is False or sca_ok is False or success is False:
            raise TopographyProcessingError(
                f"WhiteboxTools wetness_index pipeline failed for {dem_path}"
            )
        if not output_path.exists():
            raise TopographyProcessingError(
                f"WhiteboxTools 'wetness_index' did not produce output at {output_path}"
            )

        result = _read_geotiff(output_path)
        _validate_grid_alignment(dem, result)
        result_data = _apply_reference_nodata(dem, result.data)
        return RasterGrid(
            data=result_data,
            transform=result.transform,
            crs=result.crs,
            nodata=dem.nodata,
        )


def compute_relative_relief(
    dem: RasterGrid,
    window_size: int = RELATIVE_RELIEF_WINDOW,
) -> RasterGrid:
    """Compute Relative Relief Index (local elevation range).

    RRI is defined as the difference between the focal maximum and focal
    minimum elevation within a square moving window.

    Args:
        dem: Reference elevation grid.
        window_size: Moving window size in pixels (must be odd and >= 3).

    Returns:
        Relative relief raster aligned to the input DEM grid.
    """
    if window_size < 3 or window_size % 2 == 0:
        raise TopographyProcessingError(
            "Relative relief window_size must be an odd integer >= 3"
        )

    logger.info("Computing relative relief index with window %d", window_size)

    working = dem.data.astype(np.float64)
    valid = _valid_mask(dem)

    local_max = maximum_filter(
        np.where(valid, working, -np.inf),
        size=window_size,
        mode="nearest",
    )
    local_min = minimum_filter(
        np.where(valid, working, np.inf),
        size=window_size,
        mode="nearest",
    )
    relative_relief = local_max - local_min
    relative_relief[~valid | (local_max == -np.inf) | (local_min == np.inf)] = dem.nodata
    output = _apply_reference_nodata(dem, relative_relief)

    return RasterGrid(
        data=output,
        transform=dem.transform,
        crs=dem.crs,
        nodata=dem.nodata,
    )


def compute_valley_depth(
    dem: RasterGrid,
    window_size: int = VALLEY_DEPTH_WINDOW,
) -> RasterGrid:
    """Compute valley depth as elevation below the local ridge envelope.

    Valley depth is computed as the focal maximum elevation minus the current
    cell elevation within a square moving window.

    Args:
        dem: Reference elevation grid.
        window_size: Moving window size in pixels (must be odd and >= 3).

    Returns:
        Valley depth raster aligned to the input DEM grid.
    """
    if window_size < 3 or window_size % 2 == 0:
        raise TopographyProcessingError(
            "Valley depth window_size must be an odd integer >= 3"
        )

    logger.info("Computing valley depth with window %d", window_size)

    working = dem.data.astype(np.float64)
    valid = _valid_mask(dem)

    local_max = maximum_filter(
        np.where(valid, working, -np.inf),
        size=window_size,
        mode="nearest",
    )
    valley_depth = local_max - working
    valley_depth[~valid | (local_max == -np.inf)] = dem.nodata
    output = _apply_reference_nodata(dem, valley_depth)

    return RasterGrid(
        data=output,
        transform=dem.transform,
        crs=dem.crs,
        nodata=dem.nodata,
    )
