"""Spectral index computation for Sentinel-2 Surface Reflectance composites."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Mapping, Union

import numpy as np
from rasterio.transform import Affine

if TYPE_CHECKING:
    import ee

logger = logging.getLogger(__name__)

DEFAULT_NODATA = -9999.0
DIVISION_EPSILON = 1e-10

REQUIRED_BANDS: tuple[str, ...] = ("B2", "B3", "B4", "B8", "B11", "B12")

SpectralInput = Union["ee.Image", "LocalSpectralComposite", Mapping[str, np.ndarray]]


class SpectralError(Exception):
    """Base exception for spectral processing errors."""


class MissingBandError(SpectralError):
    """Raised when a required Sentinel-2 band is absent."""


class InvalidRasterError(SpectralError):
    """Raised when band arrays have invalid shape or inconsistent dimensions."""


@dataclass(frozen=True)
class LocalSpectralComposite:
    """Local Sentinel-2 band stack for spectral index computation."""

    bands: Mapping[str, np.ndarray]
    crs: object | None = None
    transform: Affine | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    nodata: float = DEFAULT_NODATA


@dataclass(frozen=True)
class LocalSpectralIndex:
    """Single-band spectral index derived from a local Sentinel-2 composite."""

    data: np.ndarray
    name: str
    crs: object | None = None
    transform: Affine | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
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


def _is_ee_image(source: object) -> bool:
    """Return True when ``source`` is an Earth Engine image."""
    import ee

    return isinstance(source, ee.Image)


def _normalize_local_input(source: SpectralInput) -> LocalSpectralComposite:
    """Convert supported local inputs to ``LocalSpectralComposite``."""
    if isinstance(source, LocalSpectralComposite):
        return source
    if isinstance(source, Mapping):
        return LocalSpectralComposite(bands=dict(source))
    raise SpectralError(
        f"Unsupported spectral input type for local processing: {type(source)!r}"
    )


def validate_bands(source: SpectralInput) -> None:
    """Validate that all required Sentinel-2 bands are present.

    Args:
        source: Earth Engine image or local band mapping.

    Raises:
        MissingBandError: If one or more required bands are missing.
        InvalidRasterError: If local band arrays have inconsistent shapes.
    """
    if _is_ee_image(source):
        _validate_ee_bands(source)
        return

    composite = _normalize_local_input(source)
    _validate_local_bands(composite)


def _validate_ee_bands(image: ee.Image) -> None:
    """Validate required band names on an Earth Engine image."""
    try:
        available = set(image.bandNames().getInfo())
    except Exception as exc:
        raise SpectralError(
            f"Failed to read Earth Engine band names: {exc}"
        ) from exc

    missing = [band for band in REQUIRED_BANDS if band not in available]
    if missing:
        raise MissingBandError(
            "Missing required Sentinel-2 bands: " + ", ".join(missing)
        )


def _validate_local_bands(composite: LocalSpectralComposite) -> None:
    """Validate required local band arrays."""
    missing = [band for band in REQUIRED_BANDS if band not in composite.bands]
    if missing:
        raise MissingBandError(
            "Missing required Sentinel-2 bands: " + ", ".join(missing)
        )

    reference_shape: tuple[int, ...] | None = None
    for band in REQUIRED_BANDS:
        array = composite.bands[band]
        if array.ndim != 2:
            raise InvalidRasterError(
                f"Band {band} must be a 2-D array, received {array.ndim}-D"
            )
        if reference_shape is None:
            reference_shape = array.shape
            continue
        if array.shape != reference_shape:
            raise InvalidRasterError(
                f"Band {band} shape {array.shape} does not match reference "
                f"shape {reference_shape}"
            )


def safe_divide(
    numerator: np.ndarray,
    denominator: np.ndarray,
    nodata: float = DEFAULT_NODATA,
    epsilon: float = DIVISION_EPSILON,
) -> np.ndarray:
    """Perform element-wise division without divide-by-zero or silent NaNs.

    Args:
        numerator: Dividend array.
        denominator: Divisor array.
        nodata: Value assigned where division is undefined.
        epsilon: Minimum absolute denominator treated as valid.

    Returns:
        Floating-point array with explicit nodata fill where division is unsafe.
    """
    if numerator.shape != denominator.shape:
        raise InvalidRasterError(
            "Numerator and denominator arrays must share the same shape"
        )

    result = np.full(numerator.shape, nodata, dtype=np.float64)
    valid = np.isfinite(numerator) & np.isfinite(denominator)
    valid &= np.abs(denominator) >= epsilon
    np.divide(numerator, denominator, out=result, where=valid)
    return result


def _safe_divide_ee(
    numerator: ee.Image,
    denominator: ee.Image,
    nodata: float = DEFAULT_NODATA,
    epsilon: float = DIVISION_EPSILON,
) -> ee.Image:
    """Perform safe division on Earth Engine images."""
    import ee

    valid = denominator.abs().gte(epsilon)
    ratio = numerator.divide(denominator)
    return ratio.where(valid, ee.Image(nodata))


def _local_valid_mask(composite: LocalSpectralComposite) -> np.ndarray:
    """Return a mask of pixels valid across all required Sentinel-2 bands."""
    mask: np.ndarray | None = None
    for band in REQUIRED_BANDS:
        array = composite.bands[band].astype(np.float64)
        band_valid = np.isfinite(array)
        if composite.nodata is not None:
            band_valid &= array != composite.nodata
        mask = band_valid if mask is None else mask & band_valid
    assert mask is not None
    return mask


def _apply_local_mask(
    composite: LocalSpectralComposite,
    data: np.ndarray,
    nodata: float,
) -> np.ndarray:
    """Apply the composite validity mask to a derived index array."""
    masked = data.copy()
    masked[~_local_valid_mask(composite)] = nodata
    return masked


def _build_local_index(
    composite: LocalSpectralComposite,
    data: np.ndarray,
    name: str,
    nodata: float,
) -> LocalSpectralIndex:
    """Build a local spectral index preserving source metadata."""
    if data.shape != composite.bands["B2"].shape:
        raise InvalidRasterError(
            f"Derived index {name} shape {data.shape} does not match input bands"
        )

    metadata = dict(composite.metadata)
    metadata["spectral_index"] = name

    return LocalSpectralIndex(
        data=data,
        name=name,
        crs=composite.crs,
        transform=composite.transform,
        metadata=metadata,
        nodata=nodata,
    )


def _preserve_ee_metadata(source: ee.Image, result: ee.Image, name: str) -> ee.Image:
    """Copy source image properties and annotate the derived index name."""
    import ee

    # copyProperties/set return ee.Element; cast back to Image for reproject/export.
    return ee.Image(result.copyProperties(source).set("spectral_index", name))


def compute_ndvi(
    source: SpectralInput,
    nodata: float = DEFAULT_NODATA,
) -> ee.Image | LocalSpectralIndex:
    """Compute Normalized Difference Vegetation Index (NDVI).

    Formula: ``(B8 - B4) / (B8 + B4)``

    Args:
        source: Sentinel-2 composite as an Earth Engine image or local bands.
        nodata: Output nodata value for undefined pixels.

    Returns:
        NDVI raster preserving source metadata and spatial reference.
    """
    logger.info("Computing NDVI")
    validate_bands(source)

    if _is_ee_image(source):
        b4 = source.select("B4")
        b8 = source.select("B8")
        ndvi = _safe_divide_ee(b8.subtract(b4), b8.add(b4), nodata=nodata).rename(
            "NDVI"
        )
        return _preserve_ee_metadata(source, ndvi, "NDVI")

    composite = _normalize_local_input(source)
    b4 = composite.bands["B4"].astype(np.float64)
    b8 = composite.bands["B8"].astype(np.float64)
    ndvi = safe_divide(b8 - b4, b8 + b4, nodata=nodata)
    ndvi = _apply_local_mask(composite, ndvi, nodata)
    return _build_local_index(composite, ndvi, "NDVI", nodata)


def compute_ndwi(
    source: SpectralInput,
    nodata: float = DEFAULT_NODATA,
) -> ee.Image | LocalSpectralIndex:
    """Compute Normalized Difference Water Index (NDWI).

    Formula: ``(B3 - B8) / (B3 + B8)``

    Args:
        source: Sentinel-2 composite as an Earth Engine image or local bands.
        nodata: Output nodata value for undefined pixels.

    Returns:
        NDWI raster preserving source metadata and spatial reference.
    """
    logger.info("Computing NDWI")
    validate_bands(source)

    if _is_ee_image(source):
        b3 = source.select("B3")
        b8 = source.select("B8")
        ndwi = _safe_divide_ee(b3.subtract(b8), b3.add(b8), nodata=nodata).rename(
            "NDWI"
        )
        return _preserve_ee_metadata(source, ndwi, "NDWI")

    composite = _normalize_local_input(source)
    b3 = composite.bands["B3"].astype(np.float64)
    b8 = composite.bands["B8"].astype(np.float64)
    ndwi = safe_divide(b3 - b8, b3 + b8, nodata=nodata)
    ndwi = _apply_local_mask(composite, ndwi, nodata)
    return _build_local_index(composite, ndwi, "NDWI", nodata)


def compute_clay_mineral_ratio(
    source: SpectralInput,
    nodata: float = DEFAULT_NODATA,
) -> ee.Image | LocalSpectralIndex:
    """Compute clay mineral ratio from SWIR bands.

    Formula: ``B11 / B12``

    Args:
        source: Sentinel-2 composite as an Earth Engine image or local bands.
        nodata: Output nodata value for undefined pixels.

    Returns:
        Clay mineral ratio raster preserving source metadata and spatial reference.
    """
    logger.info("Computing clay mineral ratio")
    validate_bands(source)

    if _is_ee_image(source):
        b11 = source.select("B11")
        b12 = source.select("B12")
        ratio = _safe_divide_ee(b11, b12, nodata=nodata).rename("CLAY_MINERAL_RATIO")
        return _preserve_ee_metadata(source, ratio, "CLAY_MINERAL_RATIO")

    composite = _normalize_local_input(source)
    b11 = composite.bands["B11"].astype(np.float64)
    b12 = composite.bands["B12"].astype(np.float64)
    ratio = safe_divide(b11, b12, nodata=nodata)
    ratio = _apply_local_mask(composite, ratio, nodata)
    return _build_local_index(composite, ratio, "CLAY_MINERAL_RATIO", nodata)


def compute_iron_oxide_index(
    source: SpectralInput,
    nodata: float = DEFAULT_NODATA,
) -> ee.Image | LocalSpectralIndex:
    """Compute iron oxide index from red and blue bands.

    Formula: ``B4 / B2``

    Args:
        source: Sentinel-2 composite as an Earth Engine image or local bands.
        nodata: Output nodata value for undefined pixels.

    Returns:
        Iron oxide index raster preserving source metadata and spatial reference.
    """
    logger.info("Computing iron oxide index")
    validate_bands(source)

    if _is_ee_image(source):
        b2 = source.select("B2")
        b4 = source.select("B4")
        index = _safe_divide_ee(b4, b2, nodata=nodata).rename("IRON_OXIDE_INDEX")
        return _preserve_ee_metadata(source, index, "IRON_OXIDE_INDEX")

    composite = _normalize_local_input(source)
    b2 = composite.bands["B2"].astype(np.float64)
    b4 = composite.bands["B4"].astype(np.float64)
    index = safe_divide(b4, b2, nodata=nodata)
    index = _apply_local_mask(composite, index, nodata)
    return _build_local_index(composite, index, "IRON_OXIDE_INDEX", nodata)
