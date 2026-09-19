"""Feature stack builder for SSRI multi-channel geospatial ML inputs."""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Union

import numpy as np
import rasterio
from rasterio.transform import Affine
from rasterio.warp import transform_bounds

from ssri_model import __version__
from ssri_model.data.gee_client import get_sentinel_composite
from ssri_model.data.geophysics import (
    GeophysicsAlignmentError,
    GridSpec,
    load_gravity,
    load_magnetics,
    reproject_to_grid,
    resample_to_grid,
    resolve_gravity_source_label,
    validate_alignment,
)
from ssri_model.data.spectral import (
    LocalSpectralIndex,
    compute_clay_mineral_ratio,
    compute_iron_oxide_index,
    compute_ndvi,
    compute_ndwi,
)
from ssri_model.data.topography import (
    DEMType,
    RasterGrid,
    compute_plan_curvature,
    compute_profile_curvature,
    compute_relative_relief,
    compute_slope,
    compute_twi,
    compute_valley_depth,
    download_dem,
    get_last_dem_acquisition_source,
    load_dem,
)

if TYPE_CHECKING:
    import ee

logger = logging.getLogger(__name__)

DEFAULT_NODATA = -9999.0

# Earth Engine ``Image.sampleRectangle`` hard limit (pixels).
EE_SAMPLE_RECTANGLE_PIXEL_LIMIT = 262_144
# Stay under the hard limit with margin for EE scale rounding.
EE_SAMPLE_SAFE_PIXEL_LIMIT = 250_000
# Max side length for a square tile under the safe limit: floor(sqrt(250000)) = 500.
EE_SAMPLE_MAX_TILE_SIDE = int(EE_SAMPLE_SAFE_PIXEL_LIMIT**0.5)
# Reject absurdly large AOIs (too many EE round-trips / memory).
EE_SAMPLE_MAX_TOTAL_PIXELS = 20_000_000

BoundingBox = tuple[float, float, float, float]
AOI = Union[BoundingBox, "ee.Geometry"]
DateInput = Union[str, date]

CHANNEL_ORDER: tuple[str, ...] = (
    "elevation",
    "slope",
    "plan_curvature",
    "profile_curvature",
    "twi",
    "relative_relief",
    "valley_depth",
    "ndvi",
    "ndwi",
    "clay_mineral_ratio",
    "iron_oxide_index",
    "gravity",
    "magnetics",
)

CHANNEL_DESCRIPTIONS: dict[str, str] = {
    "elevation": "Digital elevation model height in meters",
    "slope": "Terrain slope in degrees",
    "plan_curvature": "Plan curvature describing lateral convexity/concavity",
    "profile_curvature": "Profile curvature describing vertical convexity/concavity",
    "twi": "Topographic Wetness Index",
    "relative_relief": "Relative Relief Index (local elevation range)",
    "valley_depth": "Valley depth below local ridge envelope",
    "ndvi": "Normalized Difference Vegetation Index",
    "ndwi": "Normalized Difference Water Index",
    "clay_mineral_ratio": "Clay mineral ratio (B11/B12)",
    "iron_oxide_index": "Iron oxide index (B4/B2)",
    "gravity": "Regional gravity anomaly (mGal; source recorded in FeatureStack manifest)",
    "magnetics": "EMAG2v3 4 km upward-continued total-field anomaly (nT; regional ~2')",
}


class FeatureStackError(Exception):
    """Base exception for feature stack errors."""


class FeatureAlignmentError(FeatureStackError):
    """Raised when feature layers are not aligned to the reference grid."""


class FeatureExportError(FeatureStackError):
    """Raised when feature stack export fails."""


@dataclass(frozen=True)
class FeatureStack:
    """Aligned multi-channel feature tensor and associated metadata."""

    feature_tensor: np.ndarray
    channel_names: tuple[str, ...]
    grid_spec: GridSpec
    metadata: Mapping[str, Any]
    manifest: Mapping[str, Any]

    def save_numpy(self, path: Path | str) -> Path:
        """Save the feature tensor to a NumPy ``.npy`` file."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Saving feature tensor to %s", destination)
        try:
            np.save(destination, self.feature_tensor)
        except OSError as exc:
            raise FeatureExportError(
                f"Failed to save NumPy feature stack to {destination}: {exc}"
            ) from exc
        return destination

    def save_geotiff(self, path: Path | str) -> Path:
        """Save the feature tensor as a multi-band GeoTIFF."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Saving multi-band GeoTIFF to %s", destination)

        profile = {
            "driver": "GTiff",
            "height": self.grid_spec.height,
            "width": self.grid_spec.width,
            "count": len(self.channel_names),
            "dtype": self.feature_tensor.dtype,
            "crs": self.grid_spec.crs,
            "transform": self.grid_spec.transform,
            "nodata": self.grid_spec.nodata,
        }

        try:
            with rasterio.open(destination, "w", **profile) as dataset:
                for index, band in enumerate(self.feature_tensor, start=1):
                    dataset.write(band, index)
                    dataset.set_band_description(index, self.channel_names[index - 1])
        except Exception as exc:
            raise FeatureExportError(
                f"Failed to save GeoTIFF feature stack to {destination}: {exc}"
            ) from exc

        return destination

    def save_manifest(self, path: Path | str) -> Path:
        """Save the feature stack manifest as JSON."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Saving feature stack manifest to %s", destination)

        try:
            with destination.open("w", encoding="utf-8") as handle:
                json.dump(self.manifest, handle, indent=2, default=str)
        except OSError as exc:
            raise FeatureExportError(
                f"Failed to save manifest to {destination}: {exc}"
            ) from exc

        return destination


def _resolve_aoi_bounds(aoi: AOI) -> BoundingBox:
    """Resolve an AOI to a WGS84 bounding box."""
    if isinstance(aoi, tuple):
        if len(aoi) != 4:
            raise FeatureStackError(
                f"Bounding box must contain four values, received {len(aoi)}"
            )
        return aoi

    import ee

    if isinstance(aoi, ee.Geometry):
        coordinates = aoi.bounds().getInfo()["coordinates"][0]
        lons = [point[0] for point in coordinates]
        lats = [point[1] for point in coordinates]
        return (min(lons), min(lats), max(lons), max(lats))

    raise FeatureStackError(f"Unsupported AOI type: {type(aoi)!r}")


def _utm_crs_for_bbox(bbox: BoundingBox) -> rasterio.crs.CRS:
    """Select a UTM CRS for a WGS84 bounding box."""
    min_lon, min_lat, max_lon, max_lat = bbox
    center_lon = (min_lon + max_lon) / 2.0
    center_lat = (min_lat + max_lat) / 2.0
    zone = int((center_lon + 180.0) // 6.0) + 1
    epsg = 32600 + zone if center_lat >= 0 else 32700 + zone
    return rasterio.crs.CRS.from_epsg(epsg)


def build_grid_spec_from_aoi(aoi: AOI, resolution_m: float) -> GridSpec:
    """Build a projected reference grid for an AOI and target resolution."""
    if resolution_m <= 0:
        raise FeatureStackError("resolution_m must be greater than zero")

    bbox = _resolve_aoi_bounds(aoi)
    crs = _utm_crs_for_bbox(bbox)
    west, south, east, north = bbox
    left, bottom, right, top = transform_bounds(
        "EPSG:4326",
        crs,
        west,
        south,
        east,
        north,
    )
    width = max(1, int(round((right - left) / resolution_m)))
    height = max(1, int(round((top - bottom) / resolution_m)))
    transform = Affine(resolution_m, 0.0, left, 0.0, -resolution_m, top)

    return GridSpec(
        crs=crs,
        transform=transform,
        width=width,
        height=height,
        nodata=DEFAULT_NODATA,
    )


def _validate_layer_alignment(
    reference: GridSpec,
    layer: RasterGrid,
    layer_name: str,
) -> None:
    """Validate that a layer matches the reference grid specification."""
    try:
        validate_alignment(reference, layer)
    except GeophysicsAlignmentError as exc:
        raise FeatureAlignmentError(
            f"Layer '{layer_name}' is not aligned to the reference grid: {exc}"
        ) from exc

    resolution = reference.resolution
    layer_resolution = (abs(layer.transform.a), abs(layer.transform.e))
    if not np.allclose(resolution, layer_resolution, rtol=0.0, atol=1e-6):
        raise FeatureAlignmentError(
            f"Layer '{layer_name}' resolution {layer_resolution} does not match "
            f"reference resolution {resolution}"
        )


def _align_raster_to_grid(source: RasterGrid, target: GridSpec) -> RasterGrid:
    """Explicitly align a raster to a target grid without silent resampling."""
    if source.crs != target.crs:
        logger.info(
            "Explicitly reprojecting layer from %s to %s",
            source.crs,
            target.crs,
        )
        aligned = reproject_to_grid(source, target)
    elif source.shape != target.shape or source.transform != target.transform:
        logger.info("Explicitly resampling layer to target grid dimensions")
        aligned = resample_to_grid(source, target)
    else:
        aligned = source

    return aligned


def _utm_window_to_wgs84_bbox(
    grid_spec: GridSpec,
    col_off: int,
    row_off: int,
    width: int,
    height: int,
) -> BoundingBox:
    """Convert a pixel window on the UTM reference grid to a WGS84 bbox."""
    from rasterio.transform import xy

    west, north = xy(grid_spec.transform, row_off, col_off, offset="ul")
    east, south = xy(
        grid_spec.transform,
        row_off + height,
        col_off + width,
        offset="ul",
    )
    min_x = min(west, east)
    max_x = max(west, east)
    min_y = min(south, north)
    max_y = max(south, north)
    bounds = transform_bounds(
        grid_spec.crs,
        "EPSG:4326",
        min_x,
        min_y,
        max_x,
        max_y,
    )
    return (bounds[0], bounds[1], bounds[2], bounds[3])


def _ee_sample_tile_plan(
    grid_spec: GridSpec,
    *,
    max_tile_side: int = EE_SAMPLE_MAX_TILE_SIDE,
    safe_pixel_limit: int = EE_SAMPLE_SAFE_PIXEL_LIMIT,
    max_total_pixels: int = EE_SAMPLE_MAX_TOTAL_PIXELS,
) -> list[tuple[int, int, int, int]]:
    """Return deterministic ``(row_off, col_off, height, width)`` EE sample tiles.

    Tiles cover the full target grid without overlap. Each tile's pixel count is
    at most ``max_tile_side ** 2`` and therefore under Earth Engine's
    ``sampleRectangle`` limit when ``max_tile_side`` is derived from
    ``safe_pixel_limit``.
    """
    total = int(grid_spec.width) * int(grid_spec.height)
    if total <= 0:
        raise FeatureStackError(
            f"Invalid target grid dimensions {grid_spec.width}x{grid_spec.height}"
        )
    if total > max_total_pixels:
        raise FeatureStackError(
            f"AOI grid is too large for live Earth Engine acquisition "
            f"({total} pixels > max {max_total_pixels}). "
            "Reduce the AOI size or use offline features."
        )
    if max_tile_side <= 0:
        raise FeatureStackError("max_tile_side must be positive")
    if max_tile_side * max_tile_side > safe_pixel_limit:
        raise FeatureStackError(
            f"max_tile_side={max_tile_side} exceeds safe_pixel_limit={safe_pixel_limit}"
        )

    if total <= safe_pixel_limit:
        return [(0, 0, grid_spec.height, grid_spec.width)]

    tiles: list[tuple[int, int, int, int]] = []
    for row_off in range(0, grid_spec.height, max_tile_side):
        for col_off in range(0, grid_spec.width, max_tile_side):
            height = min(max_tile_side, grid_spec.height - row_off)
            width = min(max_tile_side, grid_spec.width - col_off)
            if height <= 0 or width <= 0:
                continue
            tiles.append((row_off, col_off, height, width))
    if not tiles:
        raise FeatureStackError("Failed to build Earth Engine sample tile plan")
    return tiles


def _sample_ee_rectangle_array(
    image: ee.Image,
    bbox: BoundingBox,
    *,
    scale_m: float = 30.0,
) -> tuple[np.ndarray, BoundingBox]:
    """Sample one WGS84 rectangle via EE ``sampleRectangle`` (single request)."""
    import ee
    from rasterio.transform import from_bounds

    west, south, east, north = bbox
    region = ee.Geometry.Rectangle(
        [west, south, east, north],
        proj="EPSG:4326",
        geodesic=False,
    )
    prepared = (
        ee.Image(image)
        .select(0)
        .rename("value")
        .toFloat()
        .unmask(0.0)
        .clipToBoundsAndScale(geometry=region, scale=scale_m)
    )
    sampled = prepared.sampleRectangle(region=region, defaultValue=0)

    try:
        payload = sampled.getInfo()
    except Exception as exc:
        message = str(exc)
        if "Too many pixels" in message or "262144" in message:
            raise FeatureStackError(
                "Earth Engine sampleRectangle exceeded the 262,144-pixel limit "
                f"for bbox {bbox}. This indicates a tiling bug; please report. "
                f"Cause: {exc}"
            ) from exc
        raise FeatureStackError(
            f"Failed to export Earth Engine image to local grid: {exc}"
        ) from exc

    if not payload:
        raise FeatureStackError("Earth Engine export returned empty payload")

    properties = payload.get("properties", payload)
    raw = properties.get("value") if isinstance(properties, dict) else None
    if raw is None and isinstance(properties, dict):
        for candidate in properties.values():
            if isinstance(candidate, list):
                raw = candidate
                break
    if raw is None:
        raise FeatureStackError(
            "Earth Engine export missing raster array; "
            f"keys={list(properties) if isinstance(properties, dict) else type(properties)}"
        )
    data = np.array(raw, dtype=np.float64)
    if data.ndim != 2:
        raise FeatureStackError(
            f"Earth Engine export produced unexpected array ndim={data.ndim}"
        )
    if data.size == 0 or min(data.shape) == 0:
        raise FeatureStackError(
            f"Earth Engine export produced empty array shape={data.shape} for bbox {bbox}"
        )
    if data.shape[0] * data.shape[1] > EE_SAMPLE_RECTANGLE_PIXEL_LIMIT:
        raise FeatureStackError(
            "Earth Engine returned more than 262,144 pixels for one sample tile "
            f"(got {data.shape[0] * data.shape[1]}). Reduce AOI or report a tiling bug."
        )
    return data, bbox


def _export_ee_image_to_grid(
    image: ee.Image,
    grid_spec: GridSpec,
    aoi: AOI,
) -> RasterGrid:
    """Export an Earth Engine image and align it to ``grid_spec``.

    Samples in EPSG:4326 (EE-friendly), then explicitly reprojects/resamples
    onto the SSRI UTM target grid. Large AOIs are acquired as deterministic
    non-overlapping UTM tiles so each ``sampleRectangle`` stays under the
    Earth Engine 262,144-pixel limit without lowering resolution or cropping.
    """
    from rasterio.transform import from_bounds

    tiles = _ee_sample_tile_plan(grid_spec)
    logger.info(
        "Earth Engine export: grid=%dx%d tiles=%d (safe_limit=%d)",
        grid_spec.width,
        grid_spec.height,
        len(tiles),
        EE_SAMPLE_SAFE_PIXEL_LIMIT,
    )

    mosaic = np.full(grid_spec.shape, grid_spec.nodata, dtype=np.float64)

    for row_off, col_off, height, width in tiles:
        tile_transform = Affine(
            grid_spec.transform.a,
            grid_spec.transform.b,
            grid_spec.transform.c + col_off * grid_spec.transform.a,
            grid_spec.transform.d,
            grid_spec.transform.e,
            grid_spec.transform.f + row_off * grid_spec.transform.e,
        )
        tile_spec = GridSpec(
            crs=grid_spec.crs,
            transform=tile_transform,
            width=width,
            height=height,
            nodata=grid_spec.nodata,
        )
        tile_bbox = _utm_window_to_wgs84_bbox(
            grid_spec, col_off, row_off, width, height
        )
        data, used_bbox = _sample_ee_rectangle_array(image, tile_bbox, scale_m=30.0)
        west, south, east, north = used_bbox
        geographic = RasterGrid(
            data=data,
            transform=from_bounds(west, south, east, north, data.shape[1], data.shape[0]),
            crs=rasterio.crs.CRS.from_epsg(4326),
            nodata=grid_spec.nodata,
        )
        aligned = _align_raster_to_grid(geographic, tile_spec)
        if aligned.data.shape != (height, width):
            raise FeatureAlignmentError(
                f"EE tile aligned shape {aligned.data.shape} != expected {(height, width)}"
            )
        mosaic[row_off : row_off + height, col_off : col_off + width] = aligned.data

    return RasterGrid(
        data=mosaic,
        transform=grid_spec.transform,
        crs=grid_spec.crs,
        nodata=grid_spec.nodata,
    )


def _spectral_index_to_grid(
    index: ee.Image | LocalSpectralIndex,
    grid_spec: GridSpec,
    aoi: AOI,
) -> RasterGrid:
    """Convert a spectral index result to an aligned ``RasterGrid``."""
    if isinstance(index, LocalSpectralIndex):
        grid = RasterGrid(
            data=index.data.astype(np.float64),
            transform=index.transform or grid_spec.transform,
            crs=rasterio.crs.CRS.from_user_input(index.crs or grid_spec.crs),
            nodata=index.nodata,
        )
        return _align_raster_to_grid(grid, grid_spec)

    return _export_ee_image_to_grid(index, grid_spec, aoi)


def _stack_layers(
    layers: Mapping[str, RasterGrid],
    grid_spec: GridSpec,
) -> np.ndarray:
    """Validate and stack ordered feature layers into a tensor."""
    logger.info("Creating feature tensor from %d channels", len(CHANNEL_ORDER))
    stacked: list[np.ndarray] = []

    for name in CHANNEL_ORDER:
        if name not in layers:
            raise FeatureStackError(f"Missing feature layer: {name}")

        layer = layers[name]
        _validate_layer_alignment(grid_spec, layer, name)
        stacked.append(layer.data.astype(np.float64))

    tensor = np.stack(stacked, axis=0)
    if tensor.shape != (len(CHANNEL_ORDER), grid_spec.height, grid_spec.width):
        raise FeatureAlignmentError(
            f"Feature tensor shape {tensor.shape} does not match expected "
            f"({len(CHANNEL_ORDER)}, {grid_spec.height}, {grid_spec.width})"
        )

    return tensor


def _build_manifest(
    *,
    aoi: AOI,
    grid_spec: GridSpec,
    start_date: DateInput,
    end_date: DateInput,
    resolution_m: float,
    dem_source: str,
    gravity_provider: str,
    magnetic_provider: str,
    tensor_shape: tuple[int, int, int],
) -> dict[str, Any]:
    """Build a JSON-serializable feature stack manifest."""
    bbox = _resolve_aoi_bounds(aoi)
    channels = [
        {
            "index": index,
            "name": name,
            "description": CHANNEL_DESCRIPTIONS[name],
        }
        for index, name in enumerate(CHANNEL_ORDER, start=1)
    ]

    return {
        "package_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "aoi": {
            "bbox_wgs84": {
                "min_lon": bbox[0],
                "min_lat": bbox[1],
                "max_lon": bbox[2],
                "max_lat": bbox[3],
            }
        },
        "crs": grid_spec.crs.to_string(),
        "projection": {
            "transform": list(grid_spec.transform),
            "width": grid_spec.width,
            "height": grid_spec.height,
        },
        "resolution_m": resolution_m,
        "acquisition": {
            "start_date": str(start_date),
            "end_date": str(end_date),
        },
        "sources": {
            "dem": dem_source,
            "gravity_provider": gravity_provider,
            "magnetic_provider": magnetic_provider,
        },
        "channels": channels,
        "tensor_shape": list(tensor_shape),
        "nodata": grid_spec.nodata,
    }


def _build_metadata(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Create runtime metadata from a manifest."""
    return {
        "aoi": manifest["aoi"],
        "crs": manifest["crs"],
        "resolution_m": manifest["resolution_m"],
        "acquisition": manifest["acquisition"],
        "sources": manifest["sources"],
        "channel_descriptions": CHANNEL_DESCRIPTIONS,
        "created_at": manifest["created_at"],
        "package_version": manifest["package_version"],
    }


def build_feature_stack(
    aoi: AOI,
    start_date: DateInput,
    end_date: DateInput,
    resolution_m: float = 30.0,
    output_dir: Path | str | None = None,
) -> FeatureStack:
    """Build a perfectly aligned multi-channel SSRI feature stack.

    Args:
        aoi: Area of interest as a bounding box or Earth Engine geometry.
        start_date: Sentinel-2 composite start date.
        end_date: Sentinel-2 composite end date.
        resolution_m: Target pixel size in meters for the reference grid.
        output_dir: Optional directory for ``feature_stack.npy``,
            ``feature_stack.tif``, and ``manifest.json`` exports.

    Returns:
        ``FeatureStack`` containing a ``(channels, height, width)`` tensor.
    """
    logger.info("Building SSRI feature stack")
    grid_spec = build_grid_spec_from_aoi(aoi, resolution_m)

    logger.info("Downloading Sentinel-2 composite")
    sentinel = get_sentinel_composite(aoi, start_date, end_date)

    logger.info("Computing spectral indices")
    ndvi = compute_ndvi(sentinel)
    ndwi = compute_ndwi(sentinel)
    clay = compute_clay_mineral_ratio(sentinel)
    iron = compute_iron_oxide_index(sentinel)

    logger.info("Downloading DEM")
    with tempfile.TemporaryDirectory() as tmp_dir:
        dem_path = Path(tmp_dir) / "dem.tif"
        download_dem(aoi, dem_path, dem_type=DEMType.COPERNICUS)
        dem_raw = load_dem(dem_path)
    dem_source = get_last_dem_acquisition_source() or DEMType.COPERNICUS.value

    logger.info("Aligning DEM to reference grid")
    dem = _align_raster_to_grid(dem_raw, grid_spec)
    _validate_layer_alignment(grid_spec, dem, "elevation")

    logger.info("Computing terrain derivatives")
    terrain_layers = {
        "elevation": dem,
        "slope": compute_slope(dem),
        "plan_curvature": compute_plan_curvature(dem),
        "profile_curvature": compute_profile_curvature(dem),
        "twi": compute_twi(dem),
        "relative_relief": compute_relative_relief(dem),
        "valley_depth": compute_valley_depth(dem),
    }

    for name, layer in terrain_layers.items():
        _validate_layer_alignment(grid_spec, layer, name)

    logger.info("Exporting spectral indices to reference grid")
    spectral_layers = {
        "ndvi": _spectral_index_to_grid(ndvi, grid_spec, aoi),
        "ndwi": _spectral_index_to_grid(ndwi, grid_spec, aoi),
        "clay_mineral_ratio": _spectral_index_to_grid(clay, grid_spec, aoi),
        "iron_oxide_index": _spectral_index_to_grid(iron, grid_spec, aoi),
    }

    for name, layer in spectral_layers.items():
        _validate_layer_alignment(grid_spec, layer, name)

    logger.info("Loading gravity anomalies")
    gravity = load_gravity(aoi, target_grid=grid_spec)
    _validate_layer_alignment(grid_spec, gravity, "gravity")

    logger.info("Loading magnetic anomalies")
    magnetics = load_magnetics(aoi, target_grid=grid_spec)
    _validate_layer_alignment(grid_spec, magnetics, "magnetics")

    layers = {
        **terrain_layers,
        **spectral_layers,
        "gravity": gravity,
        "magnetics": magnetics,
    }

    logger.info("Aligning and stacking feature layers")
    tensor = _stack_layers(layers, grid_spec)

    manifest = _build_manifest(
        aoi=aoi,
        grid_spec=grid_spec,
        start_date=start_date,
        end_date=end_date,
        resolution_m=resolution_m,
        dem_source=dem_source,
        gravity_provider=resolve_gravity_source_label(),
        magnetic_provider="emag2v3_uc4km",
        tensor_shape=tensor.shape,
    )
    metadata = _build_metadata(manifest)

    feature_stack = FeatureStack(
        feature_tensor=tensor,
        channel_names=CHANNEL_ORDER,
        grid_spec=grid_spec,
        metadata=metadata,
        manifest=manifest,
    )

    if output_dir is not None:
        logger.info("Saving feature stack outputs")
        out = Path(output_dir)
        feature_stack.save_numpy(out / "feature_stack.npy")
        feature_stack.save_geotiff(out / "feature_stack.tif")
        feature_stack.save_manifest(out / "manifest.json")

    logger.info("Feature stack build complete with shape %s", tensor.shape)
    return feature_stack
