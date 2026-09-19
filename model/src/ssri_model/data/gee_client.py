"""Google Earth Engine client for SSRI remote sensing workflows."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Union

from dotenv import load_dotenv

load_dotenv()

if TYPE_CHECKING:
    import ee

logger = logging.getLogger(__name__)

SENTINEL2_SR_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"

BoundingBox = tuple[float, float, float, float]
AOI = Union[BoundingBox, "ee.Geometry"]
DateInput = Union[str, date]

_initialized = False


class GEEClientError(Exception):
    """Base exception for GEE client errors."""


class GEEAuthenticationError(GEEClientError):
    """Raised when Earth Engine authentication fails."""


class GEEInitializationError(GEEClientError):
    """Raised when Earth Engine initialization fails."""


@dataclass(frozen=True)
class GEEConfig:
    """Earth Engine service account configuration from environment variables."""

    credentials_path: str
    service_account: str
    project_id: str

    @classmethod
    def from_env(cls) -> GEEConfig:
        """Load configuration from environment variables.

        Accepts both the canonical names and legacy aliases used in ``.env``:
        - credentials: ``GOOGLE_APPLICATION_CREDENTIALS`` or ``GEE_PRIVATE_KEY_PATH``
        - project: ``GCP_PROJECT_ID`` or ``GEE_PROJECT``
        - account: ``GEE_SERVICE_ACCOUNT``
        """
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv(
            "GEE_PRIVATE_KEY_PATH"
        )
        service_account = os.getenv("GEE_SERVICE_ACCOUNT")
        project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GEE_PROJECT")

        missing = [
            name
            for name, value in (
                ("GOOGLE_APPLICATION_CREDENTIALS|GEE_PRIVATE_KEY_PATH", credentials_path),
                ("GEE_SERVICE_ACCOUNT", service_account),
                ("GCP_PROJECT_ID|GEE_PROJECT", project_id),
            )
            if not value
        ]
        if missing:
            raise GEEAuthenticationError(
                "Missing required environment variables: "
                + ", ".join(missing)
            )

        assert credentials_path is not None
        assert service_account is not None
        assert project_id is not None

        resolved = Path(credentials_path)
        if not resolved.is_file():
            # Resolve relative paths against CWD, package parents, and credentials/.
            here = Path(__file__).resolve()
            search_roots = [Path.cwd(), *here.parents[:6]]
            candidates: list[Path] = []
            for root in search_roots:
                candidates.append(root / credentials_path)
                candidates.append(root / "credentials" / Path(credentials_path).name)
                candidates.append(root / "credentials" / "earth-engine.json")
            for candidate in candidates:
                if candidate.is_file():
                    resolved = candidate.resolve()
                    break
        if not resolved.is_file():
            raise GEEAuthenticationError(
                f"Credentials file not found: {credentials_path}"
            )

        return cls(
            credentials_path=str(resolved),
            service_account=service_account,
            project_id=project_id,
        )


def authenticate(config: GEEConfig | None = None) -> ee.ServiceAccountCredentials:
    """Authenticate with Earth Engine using a Google Cloud service account.

    Args:
        config: Optional explicit configuration. Defaults to environment
            variables loaded via ``GEEConfig.from_env()``.

    Returns:
        Service account credentials ready for ``ee.Initialize()``.

    Raises:
        GEEAuthenticationError: If configuration is invalid or credentials
            cannot be created.
    """
    import ee

    cfg = config or GEEConfig.from_env()

    if not os.path.isfile(cfg.credentials_path):
        raise GEEAuthenticationError(
            f"Credentials file not found: {cfg.credentials_path}"
        )

    logger.info("Authenticating Earth Engine service account: %s", cfg.service_account)

    try:
        credentials = ee.ServiceAccountCredentials(
            cfg.service_account,
            key_file=cfg.credentials_path,
        )
    except Exception as exc:
        raise GEEAuthenticationError(
            f"Failed to create service account credentials: {exc}"
        ) from exc

    logger.debug("Service account credentials created successfully")
    return credentials


def initialize(config: GEEConfig | None = None, *, force: bool = False) -> None:
    """Initialize the Earth Engine Python API once per process.

    Args:
        config: Optional explicit configuration. Defaults to environment
            variables loaded via ``GEEConfig.from_env()``.
        force: Re-initialize even if Earth Engine was already initialized.

    Raises:
        GEEAuthenticationError: If authentication fails.
        GEEInitializationError: If ``ee.Initialize()`` fails.
    """
    import ee

    global _initialized

    if _initialized and not force:
        logger.debug("Earth Engine already initialized; skipping")
        return

    cfg = config or GEEConfig.from_env()
    credentials = authenticate(cfg)

    try:
        ee.Initialize(credentials, project=cfg.project_id)
    except Exception as exc:
        message = str(exc)
        hint = ""
        if "serviceusage.services.use" in message or "Service Usage" in message:
            hint = (
                " IAM fix required: grant the Earth Engine service account "
                "roles/serviceusage.serviceUsageConsumer on the GCP project, "
                "enable Earth Engine API, and register the project for EE access."
            )
        raise GEEInitializationError(
            f"Failed to initialize Earth Engine for project "
            f"'{cfg.project_id}': {exc}.{hint}"
        ) from exc

    _initialized = True
    logger.info("Earth Engine initialized for project: %s", cfg.project_id)


def bbox_to_geometry(bbox: BoundingBox) -> ee.Geometry:
    """Convert a bounding box to an ``ee.Geometry.Rectangle``.

    Args:
        bbox: Tuple of ``(min_lon, min_lat, max_lon, max_lat)`` in WGS84.

    Returns:
        Rectangular Earth Engine geometry.

    Raises:
        GEEClientError: If the bounding box is invalid.
    """
    import ee

    if len(bbox) != 4:
        raise GEEClientError(
            f"Bounding box must contain four values, received {len(bbox)}"
        )

    min_lon, min_lat, max_lon, max_lat = bbox
    if min_lon >= max_lon or min_lat >= max_lat:
        raise GEEClientError(
            "Invalid bounding box: min values must be less than max values"
        )

    logger.debug(
        "Created rectangle geometry for bbox (%.4f, %.4f, %.4f, %.4f)",
        min_lon,
        min_lat,
        max_lon,
        max_lat,
    )
    return ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])


def point_radius_to_geometry(
    lon: float,
    lat: float,
    radius_meters: float,
) -> ee.Geometry:
    """Convert a point and radius to a buffered ``ee.Geometry``.

    Args:
        lon: Longitude in WGS84 degrees.
        lat: Latitude in WGS84 degrees.
        radius_meters: Buffer radius in meters.

    Returns:
        Buffered Earth Engine geometry.

    Raises:
        GEEClientError: If the radius is not positive.
    """
    import ee

    if radius_meters <= 0:
        raise GEEClientError("Radius must be greater than zero meters")

    logger.debug(
        "Created buffered point geometry at (%.4f, %.4f) with radius %.1fm",
        lon,
        lat,
        radius_meters,
    )
    return ee.Geometry.Point([lon, lat]).buffer(radius_meters)


def _resolve_aoi(aoi: AOI) -> ee.Geometry:
    """Normalize AOI input to an Earth Engine geometry."""
    import ee

    if isinstance(aoi, tuple):
        return bbox_to_geometry(aoi)

    if isinstance(aoi, ee.Geometry):
        return aoi

    raise GEEClientError(f"Unsupported AOI type: {type(aoi)!r}")


def _format_date(value: DateInput) -> str:
    """Convert supported date inputs to an Earth Engine date string."""
    if isinstance(value, date):
        return value.isoformat()
    return value


def _mask_s2_clouds(image: ee.Image) -> ee.Image:
    """Mask clouds and cirrus in a Sentinel-2 SR image using the QA60 band."""
    qa = image.select("QA60")
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = (
        qa.bitwiseAnd(cloud_bit_mask)
        .eq(0)
        .And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    )
    return image.updateMask(mask).divide(10000)


def get_sentinel_composite(
    aoi: AOI,
    start_date: DateInput,
    end_date: DateInput,
) -> ee.Image:
    """Build a cloud-masked Sentinel-2 SR median composite for an AOI.

    Uses ``COPERNICUS/S2_SR_HARMONIZED``, filters by bounds and date,
    applies a QA60 cloud mask, and preserves the source projection.

    Args:
        aoi: Area of interest as a bounding box or ``ee.Geometry``.
        start_date: Inclusive start date (``YYYY-MM-DD`` string or ``date``).
        end_date: Exclusive end date (``YYYY-MM-DD`` string or ``date``).

    Returns:
        Cloud-masked median composite as an ``ee.Image``.

    Raises:
        GEEInitializationError: If Earth Engine is not initialized and
            initialization fails.
        GEEClientError: If composite generation fails.
    """
    import ee

    global _initialized

    if not _initialized:
        initialize()

    geometry = _resolve_aoi(aoi)
    start = _format_date(start_date)
    end = _format_date(end_date)

    logger.info(
        "Building Sentinel-2 SR composite for AOI from %s to %s",
        start,
        end,
    )

    try:
        collection = (
            ee.ImageCollection(SENTINEL2_SR_COLLECTION)
            .filterBounds(geometry)
            .filterDate(start, end)
            .map(_mask_s2_clouds)
        )
        reference = collection.first()
        composite = collection.median().setDefaultProjection(
            reference.select("B4").projection()
        )
    except Exception as exc:
        raise GEEClientError(
            f"Failed to build Sentinel-2 composite for {start} to {end}: {exc}"
        ) from exc

    logger.debug("Sentinel-2 SR median composite created successfully")
    return composite


def reset_initialization() -> None:
    """Reset initialization state. Intended for testing only."""
    global _initialized
    _initialized = False
