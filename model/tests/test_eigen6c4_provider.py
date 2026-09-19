"""Tests for explicit EIGEN-6C4 gravity source configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from ssri_model.data.geophysics import (
    GeophysicsConfig,
    GeophysicsConfigError,
    GeophysicsDataError,
    LocalGeoTIFFProvider,
    resolve_gravity_source_label,
)


def test_eigen6c4_requires_dedicated_path() -> None:
    config = GeophysicsConfig(
        gravity_data_path=Path("wgm.tif"),
        magnetic_data_path=Path("mag.tif"),
        eigen6c4_data_path=None,
        gravity_source="eigen6c4",
    )
    provider = LocalGeoTIFFProvider(config=config)
    with pytest.raises(GeophysicsConfigError, match="EIGEN6C4_DATA_PATH"):
        provider.load_gravity((-1.0, 6.0, 0.0, 7.0))


def test_eigen6c4_missing_file_fails_closed(tmp_path: Path) -> None:
    missing = tmp_path / "missing_eigen.tif"
    config = GeophysicsConfig(
        gravity_data_path=tmp_path / "wgm.tif",
        magnetic_data_path=tmp_path / "mag.tif",
        eigen6c4_data_path=missing,
        gravity_source="eigen6c4",
    )
    provider = LocalGeoTIFFProvider(config=config)
    with pytest.raises(GeophysicsDataError, match="EIGEN-6C4"):
        provider.load_gravity((-1.0, 6.0, 0.0, 7.0))


def test_resolve_gravity_source_never_invents_eigen() -> None:
    config = GeophysicsConfig(
        gravity_data_path=Path("wgm.tif"),
        magnetic_data_path=Path("mag.tif"),
        gravity_source="wgm2012_bouguer",
    )
    assert resolve_gravity_source_label(config) == "wgm2012_bouguer"
