"""Tests for the Google Earth Engine client."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ssri_model.data import gee_client
from ssri_model.data.gee_client import (
    GEEAuthenticationError,
    GEEClientError,
    GEEConfig,
    GEEInitializationError,
    authenticate,
    bbox_to_geometry,
    get_sentinel_composite,
    initialize,
    point_radius_to_geometry,
    reset_initialization,
)


@pytest.fixture(autouse=True)
def reset_gee_state() -> None:
    """Ensure each test starts with a clean initialization state."""
    reset_initialization()
    yield
    reset_initialization()


@pytest.fixture
def gee_config(tmp_path: Path) -> GEEConfig:
    """Create a valid GEE configuration with a temporary credentials file."""
    credentials_file = tmp_path / "earth-engine.json"
    credentials_file.write_text('{"type": "service_account"}', encoding="utf-8")
    return GEEConfig(
        credentials_path=str(credentials_file),
        service_account="ssri-gee@test-project.iam.gserviceaccount.com",
        project_id="test-project",
    )


@pytest.fixture
def mock_ee() -> MagicMock:
    """Provide a mocked ``ee`` module."""

    class FakeGeometry:
        """Stand-in for ``ee.Geometry`` in unit tests."""

    ee = MagicMock(name="ee")
    ee.ServiceAccountCredentials.return_value = MagicMock(name="credentials")
    ee.Geometry = FakeGeometry
    ee.Geometry.Rectangle = MagicMock(name="Rectangle")
    ee.Geometry.Point = MagicMock(name="Point")
    ee.ImageCollection = MagicMock(name="ImageCollection")
    return ee


@pytest.fixture
def ee_modules(mock_ee: MagicMock):
    """Patch the lazy ``ee`` import used by the client."""
    with patch.dict(sys.modules, {"ee": mock_ee}):
        yield mock_ee


class TestAuthentication:
    def test_authenticate_creates_service_account_credentials(
        self,
        gee_config: GEEConfig,
        ee_modules: MagicMock,
    ) -> None:
        credentials = authenticate(gee_config)

        ee_modules.ServiceAccountCredentials.assert_called_once_with(
            gee_config.service_account,
            key_file=gee_config.credentials_path,
        )
        assert credentials is ee_modules.ServiceAccountCredentials.return_value

    def test_authenticate_raises_when_env_vars_missing(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(GEEAuthenticationError, match="Missing required"):
                GEEConfig.from_env()

    def test_authenticate_raises_when_credentials_file_missing(
        self,
        tmp_path: Path,
        ee_modules: MagicMock,
    ) -> None:
        config = GEEConfig(
            credentials_path=str(tmp_path / "missing.json"),
            service_account="ssri-gee@test-project.iam.gserviceaccount.com",
            project_id="test-project",
        )

        with pytest.raises(GEEAuthenticationError, match="Credentials file not found"):
            authenticate(config)


class TestInitialization:
    def test_initialize_calls_ee_initialize_once(
        self,
        gee_config: GEEConfig,
        ee_modules: MagicMock,
    ) -> None:
        initialize(gee_config)
        initialize(gee_config)

        ee_modules.Initialize.assert_called_once()

    def test_initialize_raises_meaningful_error(
        self,
        gee_config: GEEConfig,
        ee_modules: MagicMock,
    ) -> None:
        ee_modules.Initialize.side_effect = RuntimeError("project access denied")

        with pytest.raises(
            GEEInitializationError,
            match="Failed to initialize Earth Engine",
        ):
            initialize(gee_config)


class TestGeometryHelpers:
    def test_bbox_to_geometry(self, ee_modules: MagicMock) -> None:
        rectangle = MagicMock(name="rectangle")
        ee_modules.Geometry.Rectangle.return_value = rectangle

        geometry = bbox_to_geometry((-1.0, 50.0, 1.0, 52.0))

        ee_modules.Geometry.Rectangle.assert_called_once_with([-1.0, 50.0, 1.0, 52.0])
        assert geometry is rectangle

    def test_bbox_to_geometry_rejects_invalid_bbox(self, ee_modules: MagicMock) -> None:
        with pytest.raises(GEEClientError, match="Invalid bounding box"):
            bbox_to_geometry((1.0, 52.0, -1.0, 50.0))

    def test_point_radius_to_geometry(self, ee_modules: MagicMock) -> None:
        point = MagicMock(name="point")
        buffered = MagicMock(name="buffered")
        point.buffer.return_value = buffered
        ee_modules.Geometry.Point.return_value = point

        geometry = point_radius_to_geometry(0.5, 51.5, 1000.0)

        ee_modules.Geometry.Point.assert_called_once_with([0.5, 51.5])
        point.buffer.assert_called_once_with(1000.0)
        assert geometry is buffered

    def test_point_radius_to_geometry_rejects_non_positive_radius(
        self,
        ee_modules: MagicMock,
    ) -> None:
        with pytest.raises(GEEClientError, match="Radius must be greater than zero"):
            point_radius_to_geometry(0.5, 51.5, 0.0)


class TestSentinelComposite:
    def _build_collection_chain(self, mock_ee: MagicMock) -> MagicMock:
        collection = MagicMock(name="collection")
        filtered_bounds = MagicMock(name="filtered_bounds")
        filtered_dates = MagicMock(name="filtered_dates")
        mapped = MagicMock(name="mapped")
        reference = MagicMock(name="reference")
        projection = MagicMock(name="projection")
        median = MagicMock(name="median")
        composite = MagicMock(name="composite")

        mock_ee.ImageCollection.return_value = collection
        collection.filterBounds.return_value = filtered_bounds
        filtered_bounds.filterDate.return_value = filtered_dates
        filtered_dates.map.return_value = mapped
        mapped.first.return_value = reference
        reference.select.return_value.projection.return_value = projection
        mapped.median.return_value = median
        median.setDefaultProjection.return_value = composite
        return collection

    def test_get_sentinel_composite_filters_and_masks_collection(
        self,
        ee_modules: MagicMock,
    ) -> None:
        collection = self._build_collection_chain(ee_modules)
        gee_client._initialized = True

        result = get_sentinel_composite(
            (-1.0, 50.0, 1.0, 52.0),
            date(2024, 1, 1),
            date(2024, 2, 1),
        )

        ee_modules.ImageCollection.assert_called_with("COPERNICUS/S2_SR_HARMONIZED")
        collection.filterBounds.assert_called_once()
        collection.filterBounds.return_value.filterDate.assert_called_once_with(
            "2024-01-01",
            "2024-02-01",
        )
        collection.filterBounds.return_value.filterDate.return_value.map.assert_called_once()
        mapped = collection.filterBounds.return_value.filterDate.return_value.map.return_value
        mapped.median.return_value.setDefaultProjection.assert_called_once()
        assert result is mapped.median.return_value.setDefaultProjection.return_value

    def test_get_sentinel_composite_initializes_when_needed(
        self,
        gee_config: GEEConfig,
        ee_modules: MagicMock,
    ) -> None:
        self._build_collection_chain(ee_modules)

        with patch("ssri_model.data.gee_client.initialize") as mock_initialize:
            get_sentinel_composite(
                (-1.0, 50.0, 1.0, 52.0),
                "2024-01-01",
                "2024-02-01",
            )

        mock_initialize.assert_called_once()

    def test_get_sentinel_composite_accepts_existing_geometry(
        self,
        ee_modules: MagicMock,
    ) -> None:
        self._build_collection_chain(ee_modules)
        gee_client._initialized = True
        geometry = ee_modules.Geometry()

        get_sentinel_composite(geometry, "2024-01-01", "2024-02-01")

        ee_modules.ImageCollection.return_value.filterBounds.assert_called_once_with(
            geometry
        )

    def test_get_sentinel_composite_wraps_unexpected_errors(
        self,
        ee_modules: MagicMock,
    ) -> None:
        ee_modules.ImageCollection.side_effect = RuntimeError("collection unavailable")
        gee_client._initialized = True

        with pytest.raises(GEEClientError, match="Failed to build Sentinel-2 composite"):
            get_sentinel_composite(
                (-1.0, 50.0, 1.0, 52.0),
                "2024-01-01",
                "2024-02-01",
            )
