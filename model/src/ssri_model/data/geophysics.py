"""Geophysical anomaly loading and grid alignment for SSRI."""

from __future__ import annotations

import logging
import math
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Union

import numpy as np
import rasterio
from dotenv import load_dotenv
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window, from_bounds

from ssri_model.data.topography import RasterGrid

load_dotenv()

if TYPE_CHECKING:
    import ee

logger = logging.getLogger(__name__)

DEFAULT_NODATA = -9999.0

BoundingBox = tuple[float, float, float, float]
AOI = Union[BoundingBox, "ee.Geometry"]
GridReference = Union["GridSpec", RasterGrid]


class GeophysicsError(Exception):
    """Base exception for geophysics module errors."""


class GeophysicsConfigError(GeophysicsError):
    """Raised when geophysics configuration is invalid."""


class GeophysicsDataError(GeophysicsError):
    """Raised when geophysical datasets are missing or unreadable."""


class GeophysicsAlignmentError(GeophysicsError):
    """Raised when raster alignment or resampling fails."""


class ProviderType(str, Enum):
    """Supported geophysics data providers."""

    LOCAL_GEOTIFF = "local_geotiff"
    # Backward-compatible alias; loader is local GeoTIFF, not a live EIGEN-6C4 service.
    EIGEN6C4 = "eigen6c4"


@dataclass(frozen=True)
class GeophysicsConfig:
    """Geophysics dataset configuration loaded from environment variables."""

    gravity_data_path: Path | None
    magnetic_data_path: Path | None
    eigen6c4_data_path: Path | None = None
    gravity_source: str = "wgm2012_bouguer"

    @classmethod
    def from_env(cls) -> GeophysicsConfig:
        """Load geophysics paths from environment variables.

        Relative paths resolve against ``SSRI_DATA_ROOT`` / repo ``data/`` root,
        never the process CWD alone (which is ``/app`` inside containers).
        """
        source = (os.getenv("SSRI_GRAVITY_SOURCE") or "wgm2012_bouguer").strip().lower()
        return cls(
            gravity_data_path=_optional_resolved_path(
                os.getenv("GRAVITY_DATA_PATH"),
                env_var="GRAVITY_DATA_PATH",
            ),
            magnetic_data_path=_optional_resolved_path(
                os.getenv("MAGNETIC_DATA_PATH"),
                env_var="MAGNETIC_DATA_PATH",
            ),
            eigen6c4_data_path=_optional_resolved_path(
                os.getenv("EIGEN6C4_DATA_PATH"),
                env_var="EIGEN6C4_DATA_PATH",
            ),
            gravity_source=source,
        )


def _looks_like_windows_path(path: Path | str) -> bool:
    """True when a path string is a Windows drive path (invalid on Linux)."""
    text = str(path)
    return len(text) >= 2 and text[1] == ":" and text[0].isalpha()


def _discover_repo_root() -> Path | None:
    """Walk parents of this file for the SSRI checkout root."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        has_geophysics = (parent / "data" / "geophysics").is_dir()
        has_project = (parent / "infra").is_dir() or (parent / "docs").is_dir()
        if has_geophysics and has_project:
            return parent
    return None


def _config_root() -> Path:
    """Root for relative geophysics path resolution (repo or configured data root)."""
    for key in ("SSRI_REPO_ROOT", "SSRI_CONFIG_ROOT"):
        configured = (os.getenv(key) or "").strip()
        if configured:
            return Path(configured).expanduser().resolve()
    discovered = _discover_repo_root()
    if discovered is not None:
        return discovered
    data_root = (os.getenv("SSRI_DATA_ROOT") or "").strip()
    if data_root:
        return Path(data_root).expanduser().resolve()
    if Path("/data/geophysics").is_dir():
        return Path("/data").resolve()
    return Path.cwd().resolve()


def _data_root() -> Path:
    """Prefer ``SSRI_DATA_ROOT``, else ``<repo>/data``, else container ``/data``."""
    configured = (os.getenv("SSRI_DATA_ROOT") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    discovered = _discover_repo_root()
    if discovered is not None:
        return (discovered / "data").resolve()
    if Path("/data").is_dir():
        return Path("/data").resolve()
    return (_config_root() / "data").resolve()


def resolve_geophysics_path(
    raw: str | Path,
    *,
    env_var: str,
    provider: str,
    required_format: str = "single-band GeoTIFF (.tif/.tiff)",
) -> Path:
    """Resolve a configured geophysics path to an absolute filesystem path.

    Absolute paths are used as-is (after expanduser). Relative paths are
    resolved against :func:`_config_root` (repository/config root), never
    solely against ``os.getcwd()``.
    """
    text = str(raw).strip().strip('"').strip("'")
    if not text:
        raise GeophysicsConfigError(
            f"{env_var} is empty. Configure a path to a {required_format} for "
            f"provider={provider}."
        )
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = (_config_root() / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def _optional_resolved_path(raw: str | None, *, env_var: str) -> Path | None:
    if raw is None or not str(raw).strip():
        return None
    text = str(raw).strip().strip('"').strip("'")
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        return (_config_root() / candidate).resolve()
    # Keep Windows drive paths intact on Linux so the missing-file handler can
    # explain the host/container mismatch instead of pathlib collapsing them.
    if _looks_like_windows_path(candidate) and sys.platform != "win32":
        return candidate
    return candidate.resolve()


def _missing_dataset_error(
    *,
    provider: str,
    env_var: str,
    resolved: Path,
    fallback_allowed: bool = False,
) -> GeophysicsDataError:
    """Build an actionable missing-raster error (never hides the path)."""
    return GeophysicsDataError(
        f"{provider} dataset unavailable. "
        f"Resolved absolute path: {resolved}. "
        f"Configuration variable: {env_var}. "
        f"Expected format: single-band GeoTIFF (.tif/.tiff) with CRS metadata. "
        f"Fallback to another gravity product allowed: {fallback_allowed}. "
        f"cwd={Path.cwd()} config_root={_config_root()} "
        f"data_root={_data_root()} exists={resolved.is_file()}."
    )


# Backwards-compatible alias.
_repo_root = _config_root


@dataclass(frozen=True)
class GridSpec:
    """Target raster grid specification for alignment operations."""

    crs: rasterio.crs.CRS
    transform: Affine
    width: int
    height: int
    nodata: float = DEFAULT_NODATA

    @classmethod
    def from_raster_grid(cls, grid: RasterGrid) -> GridSpec:
        """Build a ``GridSpec`` from an existing ``RasterGrid``."""
        return cls(
            crs=grid.crs,
            transform=grid.transform,
            width=grid.width,
            height=grid.height,
            nodata=grid.nodata,
        )

    @property
    def shape(self) -> tuple[int, int]:
        """Return grid shape as ``(height, width)``."""
        return (self.height, self.width)

    @property
    def resolution(self) -> tuple[float, float]:
        """Return pixel size as ``(x_resolution, y_resolution)``."""
        return (abs(self.transform.a), abs(self.transform.e))


class GeophysicsProvider(ABC):
    """Abstract interface for geophysical anomaly data providers."""

    @abstractmethod
    def load_gravity(
        self,
        aoi: AOI,
        target_grid: GridReference | None = None,
    ) -> RasterGrid:
        """Load gravity anomaly data for an area of interest."""

    @abstractmethod
    def load_magnetics(
        self,
        aoi: AOI,
        target_grid: GridReference | None = None,
    ) -> RasterGrid:
        """Load magnetic anomaly data for an area of interest."""


def _resolve_bounds(aoi: AOI) -> BoundingBox:
    """Normalize AOI input to a WGS84 bounding box."""
    if isinstance(aoi, tuple):
        if len(aoi) != 4:
            raise GeophysicsError(
                f"Bounding box must contain four values, received {len(aoi)}"
            )
        min_lon, min_lat, max_lon, max_lat = aoi
        if min_lon >= max_lon or min_lat >= max_lat:
            raise GeophysicsError(
                "Invalid bounding box: min values must be less than max values"
            )
        return aoi

    import ee

    if isinstance(aoi, ee.Geometry):
        coordinates = aoi.bounds().getInfo()["coordinates"][0]
        lons = [point[0] for point in coordinates]
        lats = [point[1] for point in coordinates]
        return (min(lons), min(lats), max(lons), max(lats))

    raise GeophysicsError(f"Unsupported AOI type: {type(aoi)!r}")


def _to_grid_spec(reference: GridReference) -> GridSpec:
    """Convert a grid reference to ``GridSpec``."""
    if isinstance(reference, GridSpec):
        return reference
    return GridSpec.from_raster_grid(reference)


def _window_covering_at_least_one_pixel(window: Window) -> Window:
    """Expand a sub-pixel read window to cover at least one source pixel.

    Regional gravity/magnetics grids are coarse (~0.03° / ~2'). A 30 m Lagos
    FeatureStack AOI is often smaller than one native cell, so ``from_bounds``
    yields width/height < 1 and ``dataset.read`` returns shape ``(0, 0)``. That
    empty array then fails reprojection to the UTM target grid.

    Windows that already span ≥1 pixel are returned unchanged so existing
    full-tile loads keep prior behavior.
    """
    width = float(window.width)
    height = float(window.height)
    if width >= 1.0 and height >= 1.0:
        return window

    col_off = math.floor(float(window.col_off))
    row_off = math.floor(float(window.row_off))
    col_end = math.ceil(float(window.col_off) + max(width, 0.0))
    row_end = math.ceil(float(window.row_off) + max(height, 0.0))
    out_width = max(1, col_end - col_off)
    out_height = max(1, row_end - row_off)
    return Window(
        col_off=col_off,
        row_off=row_off,
        width=out_width,
        height=out_height,
    )


def _assert_geophysics_raster_exists(
    path: Path,
    *,
    provider: str,
    env_var: str,
    fallback_allowed: bool = False,
) -> None:
    """Fail closed with an actionable error before opening the raster."""
    if path.is_file():
        return
    if _looks_like_windows_path(path) and sys.platform != "win32":
        raise GeophysicsDataError(
            f"{provider} dataset unavailable: configured path looks like a "
            f"Windows host path inside a non-Windows container/process. "
            f"Resolved path: {path}. Configuration variable: {env_var}. "
            f"Expected format: single-band GeoTIFF (.tif/.tiff). "
            f"Use a container-mounted path such as "
            f"/data/geophysics/processed/<file>.tif "
            f"(Compose mounts ../data/geophysics → /data/geophysics). "
            f"Fallback to another gravity product allowed: {fallback_allowed}."
        )
    raise _missing_dataset_error(
        provider=provider,
        env_var=env_var,
        resolved=path,
        fallback_allowed=fallback_allowed,
    )


def _load_geotiff_for_aoi(
    path: Path,
    aoi: AOI,
    *,
    provider: str = "geophysics",
    env_var: str = "GRAVITY_DATA_PATH",
    fallback_allowed: bool = False,
) -> RasterGrid:
    """Load and clip a GeoTIFF dataset to an AOI bounding box."""
    _assert_geophysics_raster_exists(
        path,
        provider=provider,
        env_var=env_var,
        fallback_allowed=fallback_allowed,
    )

    min_lon, min_lat, max_lon, max_lat = _resolve_bounds(aoi)
    logger.info(
        "Loading geophysical raster from %s for bounds (%.4f, %.4f, %.4f, %.4f)",
        path,
        min_lon,
        min_lat,
        max_lon,
        max_lat,
    )

    try:
        with rasterio.open(path) as dataset:
            if dataset.crs is None:
                raise GeophysicsDataError(
                    f"Geophysical dataset {path} is missing CRS metadata"
                )

            left, bottom, right, top = transform_bounds(
                "EPSG:4326",
                dataset.crs,
                min_lon,
                min_lat,
                max_lon,
                max_lat,
            )
            window = _window_covering_at_least_one_pixel(
                from_bounds(
                    left,
                    bottom,
                    right,
                    top,
                    transform=dataset.transform,
                )
            )
            nodata = (
                float(dataset.nodata) if dataset.nodata is not None else DEFAULT_NODATA
            )
            data = dataset.read(
                1,
                window=window,
                boundless=True,
                fill_value=nodata,
            ).astype(np.float64)
            if data.size == 0:
                raise GeophysicsDataError(
                    f"Geophysical read produced an empty array for AOI bounds "
                    f"({min_lon}, {min_lat}, {max_lon}, {max_lat}) from {path}"
                )
            transform = dataset.window_transform(window)
            crs = dataset.crs
    except GeophysicsDataError:
        raise
    except Exception as exc:
        raise GeophysicsDataError(
            f"Failed to read geophysical dataset {path}: {exc}"
        ) from exc

    return RasterGrid(
        data=data,
        transform=transform,
        crs=crs,
        nodata=nodata,
    )


def _align_to_target(
    source: RasterGrid,
    target_grid: GridReference,
) -> RasterGrid:
    """Align a source grid to a target grid specification."""
    target = _to_grid_spec(target_grid)

    if source.crs != target.crs:
        logger.info(
            "Reprojecting geophysical raster from %s to %s",
            source.crs,
            target.crs,
        )
        aligned = reproject_to_grid(source, target)
    else:
        logger.info("Resampling geophysical raster to target grid resolution")
        aligned = resample_to_grid(source, target)

    validate_alignment(target, aligned)
    return aligned


class LocalGeoTIFFProvider(GeophysicsProvider):
    """Load regional gravity/magnetic anomaly GeoTIFFs from local paths.

    Environment variables:
    - ``GRAVITY_DATA_PATH``: default gravity GeoTIFF (typically WGM2012 Bouguer)
    - ``MAGNETIC_DATA_PATH``: EMAG2v3 upward-continued (or equivalent) GeoTIFF
    - ``EIGEN6C4_DATA_PATH``: optional PRD EIGEN-6C4 gravity GeoTIFF
    - ``SSRI_GRAVITY_SOURCE``: ``wgm2012_bouguer`` (default) or ``eigen6c4``

    Do **not** set ``SSRI_GRAVITY_SOURCE=eigen6c4`` unless ``EIGEN6C4_DATA_PATH``
    points at a real EIGEN-6C4-derived raster. WGM2012 must never be relabelled.
    """

    def __init__(self, config: GeophysicsConfig | None = None) -> None:
        self._config = config or GeophysicsConfig.from_env()

    @property
    def gravity_source_id(self) -> str:
        """Return the configured gravity product identifier for manifests."""
        return self._config.gravity_source

    def load_gravity(
        self,
        aoi: AOI,
        target_grid: GridReference | None = None,
    ) -> RasterGrid:
        """Load regional gravity anomaly data for an AOI."""
        source = self._config.gravity_source
        if source in {"eigen6c4", "eigen-6c4", "eigen_6c4"}:
            path = self._config.eigen6c4_data_path
            if path is None:
                raise GeophysicsConfigError(
                    "EIGEN-6C4 gravity provider requested but EIGEN6C4_DATA_PATH "
                    "is unset. Configure EIGEN6C4_DATA_PATH to a real EIGEN-6C4 "
                    "GeoTIFF or explicitly select SSRI_GRAVITY_SOURCE=wgm2012_bouguer "
                    "for the engineering/non-PRD path. "
                    "Silent WGM2012 substitution is not allowed. "
                    "See docs/EIGEN6C4_ACQUISITION.md."
                )
            _assert_geophysics_raster_exists(
                path,
                provider="EIGEN-6C4",
                env_var="EIGEN6C4_DATA_PATH",
                fallback_allowed=False,
            )
            logger.info("Loading EIGEN-6C4 gravity from %s", path)
            grid = _load_geotiff_for_aoi(
                path,
                aoi,
                provider="EIGEN-6C4",
                env_var="EIGEN6C4_DATA_PATH",
                fallback_allowed=False,
            )
        else:
            if self._config.gravity_data_path is None:
                raise GeophysicsConfigError(
                    "Missing required environment variable: GRAVITY_DATA_PATH "
                    f"(provider={source or 'wgm2012_bouguer'}). "
                    "Expected a single-band GeoTIFF; relative paths resolve "
                    f"against data_root={_data_root()}."
                )
            logger.info(
                "Loading gravity source=%s from %s",
                source,
                self._config.gravity_data_path,
            )
            grid = _load_geotiff_for_aoi(
                self._config.gravity_data_path,
                aoi,
                provider=source or "wgm2012_bouguer",
                env_var="GRAVITY_DATA_PATH",
                fallback_allowed=False,
            )

        if target_grid is not None:
            grid = _align_to_target(grid, target_grid)
        return grid

    def load_magnetics(
        self,
        aoi: AOI,
        target_grid: GridReference | None = None,
    ) -> RasterGrid:
        """Load regional magnetic anomaly data for an AOI."""
        if self._config.magnetic_data_path is None:
            raise GeophysicsConfigError(
                "Missing required environment variable: MAGNETIC_DATA_PATH. "
                "Expected a single-band GeoTIFF; relative paths resolve "
                f"against data_root={_data_root()}."
            )

        grid = _load_geotiff_for_aoi(
            self._config.magnetic_data_path,
            aoi,
            provider="emag2v3_uc4km",
            env_var="MAGNETIC_DATA_PATH",
            fallback_allowed=False,
        )
        if target_grid is not None:
            grid = _align_to_target(grid, target_grid)
        return grid


# Backward-compatible alias (historical Stage-1 name). Loads whatever
# GRAVITY_DATA_PATH / SSRI_GRAVITY_SOURCE configure — not an automatic EIGEN fetch.
EIGEN6C4Provider = LocalGeoTIFFProvider


def resolve_gravity_source_label(config: GeophysicsConfig | None = None) -> str:
    """Return a manifest-safe gravity source label (never invent EIGEN-6C4)."""
    cfg = config or GeophysicsConfig.from_env()
    source = cfg.gravity_source.strip().lower()
    if source in {"eigen6c4", "eigen-6c4", "eigen_6c4"}:
        if cfg.eigen6c4_data_path and cfg.eigen6c4_data_path.exists():
            return "eigen6c4"
        return "eigen6c4_MISSING"
    if "wgm" in source:
        return "wgm2012_bouguer"
    return source or "wgm2012_bouguer"


def get_provider(
    provider_type: ProviderType = ProviderType.LOCAL_GEOTIFF,
    config: GeophysicsConfig | None = None,
) -> GeophysicsProvider:
    """Return a configured geophysics provider instance.

    Args:
        provider_type: Provider identifier.
        config: Optional explicit configuration.

    Returns:
        Concrete ``GeophysicsProvider`` implementation.

    Raises:
        GeophysicsError: If the provider type is unsupported.
    """
    if provider_type in {ProviderType.LOCAL_GEOTIFF, ProviderType.EIGEN6C4}:
        return LocalGeoTIFFProvider(config=config)

    raise GeophysicsError(f"Unsupported geophysics provider: {provider_type.value}")


def load_gravity(
    aoi: AOI,
    provider: GeophysicsProvider | None = None,
    target_grid: GridReference | None = None,
    config: GeophysicsConfig | None = None,
) -> RasterGrid:
    """Load gravity anomaly data using a configured provider.

    Args:
        aoi: Bounding box or Earth Engine geometry.
        provider: Optional explicit provider instance.
        target_grid: Optional target ``GridSpec`` or ``RasterGrid`` for alignment.
        config: Optional configuration when using the default provider.

    Returns:
        Gravity anomaly grid, optionally aligned to ``target_grid``.
    """
    selected = provider or get_provider(config=config)
    logger.info("Loading gravity anomalies using %s", type(selected).__name__)
    return selected.load_gravity(aoi, target_grid=target_grid)


def load_magnetics(
    aoi: AOI,
    provider: GeophysicsProvider | None = None,
    target_grid: GridReference | None = None,
    config: GeophysicsConfig | None = None,
) -> RasterGrid:
    """Load magnetic anomaly data using a configured provider.

    Args:
        aoi: Bounding box or Earth Engine geometry.
        provider: Optional explicit provider instance.
        target_grid: Optional target ``GridSpec`` or ``RasterGrid`` for alignment.
        config: Optional configuration when using the default provider.

    Returns:
        Magnetic anomaly grid, optionally aligned to ``target_grid``.
    """
    selected = provider or get_provider(config=config)
    logger.info("Loading magnetic anomalies using %s", type(selected).__name__)
    return selected.load_magnetics(aoi, target_grid=target_grid)


def reproject_to_grid(
    source: RasterGrid,
    target: GridReference,
    resampling: Resampling = Resampling.bilinear,
) -> RasterGrid:
    """Reproject a raster onto a target CRS and grid specification.

    Args:
        source: Input geophysical raster.
        target: Target grid specification.
        resampling: Rasterio resampling method.

    Returns:
        Reprojected ``RasterGrid`` aligned to the target specification.

    Raises:
        GeophysicsAlignmentError: If reprojection fails.
    """
    target_spec = _to_grid_spec(target)
    if source.data.size == 0 or min(source.data.shape) == 0:
        raise GeophysicsAlignmentError(
            f"Cannot reproject empty source raster (shape={source.data.shape}) "
            f"from {source.crs} to {target_spec.crs}"
        )
    if target_spec.width <= 0 or target_spec.height <= 0:
        raise GeophysicsAlignmentError(
            f"Cannot reproject to empty target grid "
            f"({target_spec.width} x {target_spec.height})"
        )
    destination = np.full(
        target_spec.shape,
        target_spec.nodata,
        dtype=np.float64,
    )

    logger.info(
        "Reprojecting raster from %s to %s at resolution (%.2f, %.2f)",
        source.crs,
        target_spec.crs,
        target_spec.resolution[0],
        target_spec.resolution[1],
    )

    try:
        reproject(
            source=source.data,
            destination=destination,
            src_transform=source.transform,
            src_crs=source.crs,
            dst_transform=target_spec.transform,
            dst_crs=target_spec.crs,
            src_nodata=source.nodata,
            dst_nodata=target_spec.nodata,
            resampling=resampling,
        )
    except Exception as exc:
        raise GeophysicsAlignmentError(
            f"Failed to reproject raster from {source.crs} to {target_spec.crs}: {exc}"
        ) from exc

    return RasterGrid(
        data=destination,
        transform=target_spec.transform,
        crs=target_spec.crs,
        nodata=target_spec.nodata,
    )


def resample_to_grid(
    source: RasterGrid,
    target: GridReference,
    resampling: Resampling = Resampling.bilinear,
) -> RasterGrid:
    """Resample a raster to a target grid without changing CRS.

    Args:
        source: Input geophysical raster.
        target: Target grid specification.
        resampling: Rasterio resampling method.

    Returns:
        Resampled ``RasterGrid`` aligned to the target specification.

    Raises:
        GeophysicsAlignmentError: If the source and target CRS differ.
    """
    target_spec = _to_grid_spec(target)
    if source.crs != target_spec.crs:
        raise GeophysicsAlignmentError(
            "CRS mismatch during resampling: use reproject_to_grid() explicitly "
            f"to transform from {source.crs} to {target_spec.crs}"
        )

    destination = np.full(
        target_spec.shape,
        target_spec.nodata,
        dtype=np.float64,
    )

    logger.info(
        "Resampling raster to %dx%d at resolution (%.2f, %.2f)",
        target_spec.width,
        target_spec.height,
        target_spec.resolution[0],
        target_spec.resolution[1],
    )

    try:
        reproject(
            source=source.data,
            destination=destination,
            src_transform=source.transform,
            src_crs=source.crs,
            dst_transform=target_spec.transform,
            dst_crs=target_spec.crs,
            src_nodata=source.nodata,
            dst_nodata=target_spec.nodata,
            resampling=resampling,
        )
    except Exception as exc:
        raise GeophysicsAlignmentError(
            f"Failed to resample raster to target grid: {exc}"
        ) from exc

    return RasterGrid(
        data=destination,
        transform=target_spec.transform,
        crs=target_spec.crs,
        nodata=target_spec.nodata,
    )


def validate_alignment(reference: GridReference, candidate: RasterGrid) -> None:
    """Validate that a candidate raster matches a reference grid.

    Args:
        reference: Expected grid specification.
        candidate: Raster to validate.

    Raises:
        GeophysicsAlignmentError: If shape, transform, or CRS do not match.
    """
    ref = _to_grid_spec(reference)

    if candidate.shape != ref.shape:
        raise GeophysicsAlignmentError(
            f"Shape mismatch: expected {ref.shape}, received {candidate.shape}"
        )
    if candidate.transform != ref.transform:
        raise GeophysicsAlignmentError(
            "Affine transform mismatch between reference and candidate grids"
        )
    if candidate.crs != ref.crs:
        raise GeophysicsAlignmentError(
            f"CRS mismatch: expected {ref.crs}, received {candidate.crs}"
        )

    logger.debug(
        "Validated grid alignment for %dx%d raster in %s",
        candidate.width,
        candidate.height,
        candidate.crs,
    )
