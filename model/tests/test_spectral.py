"""Tests for the spectral index computation module."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from rasterio.transform import Affine

from ssri_model.data.spectral import (
    DEFAULT_NODATA,
    InvalidRasterError,
    LocalSpectralComposite,
    LocalSpectralIndex,
    MissingBandError,
    compute_clay_mineral_ratio,
    compute_iron_oxide_index,
    compute_ndvi,
    compute_ndwi,
    safe_divide,
    validate_bands,
)


def _build_local_composite(
    width: int = 4,
    height: int = 4,
    nodata_fraction: float = 0.0,
) -> LocalSpectralComposite:
    """Create a synthetic Sentinel-2 composite for local index tests."""
    transform = Affine(10.0, 0.0, 500000.0, 0.0, -10.0, 4100000.0)
    crs = "EPSG:32613"
    bands = {
        "B2": np.full((height, width), 0.05, dtype=np.float64),
        "B3": np.full((height, width), 0.10, dtype=np.float64),
        "B4": np.full((height, width), 0.20, dtype=np.float64),
        "B8": np.full((height, width), 0.50, dtype=np.float64),
        "B11": np.full((height, width), 0.30, dtype=np.float64),
        "B12": np.full((height, width), 0.25, dtype=np.float64),
    }

    bands["B2"][0, 0] = 0.0
    bands["B4"][1, 1] = 0.40
    bands["B8"][1, 1] = 0.60

    if nodata_fraction > 0:
        bands["B3"][2, 2] = DEFAULT_NODATA

    return LocalSpectralComposite(
        bands=bands,
        crs=crs,
        transform=transform,
        metadata={"source": "unit-test"},
        nodata=DEFAULT_NODATA,
    )


@pytest.fixture
def local_composite() -> LocalSpectralComposite:
    """Provide a synthetic local Sentinel-2 composite."""
    return _build_local_composite()


@pytest.fixture
def mock_ee_image() -> MagicMock:
    """Provide a mocked Earth Engine image with required bands."""
    image = MagicMock(name="ee_image")
    image.bandNames.return_value.getInfo.return_value = [
        "B2",
        "B3",
        "B4",
        "B8",
        "B11",
        "B12",
    ]

    def _select(band: str) -> MagicMock:
        selected = MagicMock(name=f"band_{band}")
        selected.subtract = MagicMock(return_value=MagicMock(name=f"{band}_sub"))
        selected.add = MagicMock(return_value=MagicMock(name=f"{band}_add"))
        selected.divide = MagicMock(return_value=MagicMock(name=f"{band}_div"))
        selected.abs = MagicMock(return_value=MagicMock(name=f"{band}_abs"))
        selected.gte = MagicMock(return_value=MagicMock(name=f"{band}_gte"))
        selected.where = MagicMock(return_value=MagicMock(name=f"{band}_where"))
        selected.rename = MagicMock(return_value=MagicMock(name=f"{band}_renamed"))
        return selected

    image.select.side_effect = _select
    image.copyProperties.return_value.set.return_value = MagicMock(
        name="ee_index_result"
    )
    return image


@pytest.fixture
def ee_modules(mock_ee_image: MagicMock):
    """Patch the lazy ``ee`` import used by spectral helpers."""

    class FakeImage:
        """Stand-in for ``ee.Image``."""

    ee = MagicMock(name="ee")
    ee.Image = MagicMock(side_effect=lambda value: MagicMock(name="ee_constant"))
    ee.Image.__class__ = FakeImage

    def _isinstance(obj: object, cls: type) -> bool:
        if cls is FakeImage:
            return isinstance(obj, MagicMock) and obj is mock_ee_image
        return isinstance(obj, cls)

    with patch.dict(sys.modules, {"ee": ee}):
        with patch("ssri_model.data.spectral._is_ee_image") as checker:
            checker.side_effect = lambda obj: obj is mock_ee_image
            yield ee, mock_ee_image, checker


class TestBandValidation:
    def test_validate_bands_detects_missing_local_band(self) -> None:
        composite = LocalSpectralComposite(
            bands={"B2": np.ones((2, 2)), "B3": np.ones((2, 2))}
        )

        with pytest.raises(MissingBandError, match="Missing required Sentinel-2 bands"):
            validate_bands(composite)

    def test_validate_bands_detects_shape_mismatch(self) -> None:
        composite = LocalSpectralComposite(
            bands={
                "B2": np.ones((2, 2)),
                "B3": np.ones((2, 2)),
                "B4": np.ones((2, 2)),
                "B8": np.ones((3, 3)),
                "B11": np.ones((2, 2)),
                "B12": np.ones((2, 2)),
            }
        )

        with pytest.raises(InvalidRasterError, match="shape"):
            validate_bands(composite)

    def test_validate_bands_accepts_plain_dict(self, local_composite: LocalSpectralComposite) -> None:
        validate_bands(local_composite.bands)

    def test_validate_bands_for_ee_image(
        self,
        ee_modules: tuple[MagicMock, MagicMock, MagicMock],
    ) -> None:
        _, mock_image, _ = ee_modules
        mock_image.bandNames.return_value.getInfo.return_value = ["B2", "B3"]

        with pytest.raises(MissingBandError, match="B4"):
            validate_bands(mock_image)


class TestSafeDivide:
    def test_safe_divide_computes_expected_values(self) -> None:
        numerator = np.array([1.0, 2.0, 3.0])
        denominator = np.array([2.0, 2.0, 0.0])

        result = safe_divide(numerator, denominator, nodata=-1.0)

        np.testing.assert_allclose(result, np.array([0.5, 1.0, -1.0]))

    def test_safe_divide_does_not_emit_nan(self) -> None:
        numerator = np.array([1.0, 2.0])
        denominator = np.array([0.0, 0.0])

        result = safe_divide(numerator, denominator, nodata=DEFAULT_NODATA)

        assert not np.any(np.isnan(result))
        assert np.all(result == DEFAULT_NODATA)


class TestLocalIndexFormulas:
    def test_compute_ndvi_formula(self, local_composite: LocalSpectralComposite) -> None:
        result = compute_ndvi(local_composite)

        b4 = local_composite.bands["B4"]
        b8 = local_composite.bands["B8"]
        expected = safe_divide(b8 - b4, b8 + b4, nodata=DEFAULT_NODATA)

        assert isinstance(result, LocalSpectralIndex)
        np.testing.assert_allclose(result.data, expected)

    def test_compute_ndwi_formula(self, local_composite: LocalSpectralComposite) -> None:
        result = compute_ndwi(local_composite)

        b3 = local_composite.bands["B3"]
        b8 = local_composite.bands["B8"]
        expected = safe_divide(b3 - b8, b3 + b8, nodata=DEFAULT_NODATA)

        np.testing.assert_allclose(result.data, expected)

    def test_compute_clay_mineral_ratio_formula(
        self,
        local_composite: LocalSpectralComposite,
    ) -> None:
        result = compute_clay_mineral_ratio(local_composite)

        expected = safe_divide(
            local_composite.bands["B11"],
            local_composite.bands["B12"],
            nodata=DEFAULT_NODATA,
        )

        np.testing.assert_allclose(result.data, expected)

    def test_compute_iron_oxide_index_formula(
        self,
        local_composite: LocalSpectralComposite,
    ) -> None:
        result = compute_iron_oxide_index(local_composite)

        expected = safe_divide(
            local_composite.bands["B4"],
            local_composite.bands["B2"],
            nodata=DEFAULT_NODATA,
        )

        np.testing.assert_allclose(result.data, expected)

    def test_divide_by_zero_uses_nodata_for_iron_oxide_index(
        self,
        local_composite: LocalSpectralComposite,
    ) -> None:
        result = compute_iron_oxide_index(local_composite)

        assert result.data[0, 0] == DEFAULT_NODATA
        assert not np.isnan(result.data[0, 0])


class TestMetadataAndDimensions:
    def test_local_index_preserves_metadata_and_grid(
        self,
        local_composite: LocalSpectralComposite,
    ) -> None:
        result = compute_ndvi(local_composite)

        assert result.shape == local_composite.bands["B2"].shape
        assert result.crs == local_composite.crs
        assert result.transform == local_composite.transform
        assert result.metadata["source"] == "unit-test"
        assert result.metadata["spectral_index"] == "NDVI"
        assert result.nodata == DEFAULT_NODATA

    def test_nodata_pixels_do_not_propagate_into_valid_cells(
        self,
    ) -> None:
        composite = _build_local_composite(nodata_fraction=0.1)
        valid = composite.bands["B3"] != DEFAULT_NODATA

        result = compute_ndwi(composite)

        assert result.data[2, 2] == DEFAULT_NODATA
        assert np.all(np.isfinite(result.data[valid]))
        assert not np.any(np.isnan(result.data[valid]))


class TestEarthEnginePath:
    def test_compute_ndvi_uses_ee_band_math(
        self,
        ee_modules: tuple[MagicMock, MagicMock, MagicMock],
    ) -> None:
        _, mock_image, _ = ee_modules

        with patch("ssri_model.data.spectral._safe_divide_ee") as mock_divide:
            renamed = MagicMock(name="ndvi_renamed")
            mock_divide.return_value.rename.return_value = renamed
            compute_ndvi(mock_image)

        mock_image.select.assert_any_call("B4")
        mock_image.select.assert_any_call("B8")
        mock_divide.assert_called_once()
        renamed.copyProperties.assert_called_once_with(mock_image)

    def test_compute_ndwi_preserves_ee_metadata(
        self,
        ee_modules: tuple[MagicMock, MagicMock, MagicMock],
    ) -> None:
        mock_ee, mock_image, _ = ee_modules

        with patch("ssri_model.data.spectral._safe_divide_ee") as mock_divide:
            renamed = MagicMock(name="ndwi_renamed")
            mock_divide.return_value.rename.return_value = renamed
            compute_ndwi(mock_image)

        renamed.copyProperties.assert_called_once_with(mock_image)
        renamed.copyProperties.return_value.set.assert_called_once_with(
            "spectral_index",
            "NDWI",
        )
        mock_ee.Image.assert_called_once_with(
            renamed.copyProperties.return_value.set.return_value
        )

    def test_compute_clay_mineral_ratio_on_ee_image(
        self,
        ee_modules: tuple[MagicMock, MagicMock, MagicMock],
    ) -> None:
        _, mock_image, _ = ee_modules

        with patch("ssri_model.data.spectral._safe_divide_ee") as mock_divide:
            compute_clay_mineral_ratio(mock_image)

        mock_image.select.assert_any_call("B11")
        mock_image.select.assert_any_call("B12")
        mock_divide.assert_called_once()

    def test_compute_iron_oxide_index_on_ee_image(
        self,
        ee_modules: tuple[MagicMock, MagicMock, MagicMock],
    ) -> None:
        _, mock_image, _ = ee_modules

        with patch("ssri_model.data.spectral._safe_divide_ee") as mock_divide:
            compute_iron_oxide_index(mock_image)

        mock_image.select.assert_any_call("B2")
        mock_image.select.assert_any_call("B4")
        mock_divide.assert_called_once()
