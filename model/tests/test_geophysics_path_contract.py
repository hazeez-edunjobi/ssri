"""Path resolution, provider contract, and acquisition error mapping tests."""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from ssri_model.api.acquisition import _map_acquisition_failure
from ssri_model.data.geophysics import (
    DEFAULT_NODATA,
    GeophysicsConfig,
    GeophysicsDataError,
    LocalGeoTIFFProvider,
    resolve_geophysics_path,
    resolve_gravity_source_label,
)
from ssri_model.data.topography import (
    TopographyDownloadError,
    download_dem,
    get_last_dem_acquisition_source,
)


def _write_geotiff(path: Path, *, base_value: float = 10.0) -> None:
    transform = Affine(30.0, 0.0, 500000.0, 0.0, -30.0, 4100000.0)
    crs = rasterio.crs.CRS.from_epsg(32613)
    data = np.full((8, 8), base_value, dtype=np.float64)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=8,
        width=8,
        count=1,
        dtype="float64",
        crs=crs,
        transform=transform,
        nodata=DEFAULT_NODATA,
    ) as dataset:
        dataset.write(data, 1)


def test_valid_configured_path_loads(tmp_path: Path) -> None:
    gravity = tmp_path / "gravity.tif"
    magnetic = tmp_path / "magnetic.tif"
    _write_geotiff(gravity, base_value=20.0)
    _write_geotiff(magnetic, base_value=40.0)
    provider = LocalGeoTIFFProvider(
        config=GeophysicsConfig(
            gravity_data_path=gravity,
            magnetic_data_path=magnetic,
            gravity_source="wgm2012_bouguer",
        )
    )
    grid = provider.load_gravity((-1.0, 50.0, 1.0, 52.0))
    assert grid.data.size > 0


def test_relative_path_resolves_against_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SSRI_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path / "unrelated" if False else tmp_path)
    nested = tmp_path / "cwd_only"
    nested.mkdir()
    monkeypatch.chdir(nested)

    relative = "data/geophysics/processed/demo_gravity.tif"
    target = tmp_path / relative
    _write_geotiff(target)

    resolved = resolve_geophysics_path(
        relative,
        env_var="GRAVITY_DATA_PATH",
        provider="wgm2012_bouguer",
    )
    assert resolved == target.resolve()
    assert resolved.is_file()


def test_missing_geophysics_file_is_actionable(tmp_path: Path) -> None:
    missing = tmp_path / "missing.tif"
    provider = LocalGeoTIFFProvider(
        config=GeophysicsConfig(
            gravity_data_path=missing,
            magnetic_data_path=tmp_path / "mag.tif",
            gravity_source="wgm2012_bouguer",
        )
    )
    with pytest.raises(GeophysicsDataError) as exc_info:
        provider.load_gravity((-1.0, 50.0, 1.0, 52.0))
    message = str(exc_info.value)
    assert str(missing.resolve()) in message or str(missing) in message
    assert "GRAVITY_DATA_PATH" in message
    assert "Fallback" in message


def test_eigen6c4_requested_unavailable_no_wgm_substitution(tmp_path: Path) -> None:
    wgm = tmp_path / "wgm.tif"
    _write_geotiff(wgm)
    provider = LocalGeoTIFFProvider(
        config=GeophysicsConfig(
            gravity_data_path=wgm,
            magnetic_data_path=tmp_path / "mag.tif",
            eigen6c4_data_path=tmp_path / "missing_eigen.tif",
            gravity_source="eigen6c4",
        )
    )
    with pytest.raises(GeophysicsDataError, match="EIGEN-6C4"):
        provider.load_gravity((-1.0, 6.0, 0.0, 7.0))


def test_explicit_wgm2012_provenance(tmp_path: Path) -> None:
    config = GeophysicsConfig(
        gravity_data_path=tmp_path / "wgm.tif",
        magnetic_data_path=tmp_path / "mag.tif",
        gravity_source="wgm2012_bouguer",
    )
    assert resolve_gravity_source_label(config) == "wgm2012_bouguer"


def test_geophysics_failure_not_blamed_on_opentopo() -> None:
    err = _map_acquisition_failure(
        GeophysicsDataError(
            "wgm2012_bouguer dataset unavailable. "
            "Resolved absolute path: /data/missing.tif. "
            "Configuration variable: GRAVITY_DATA_PATH."
        )
    )
    detail = str(err)
    assert "geophysics" in detail.lower()
    assert "OPENTOPOGRAPHY_API_KEY" not in detail


def test_opentopo_rate_limit_falls_back_to_gee(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SSRI_DEM_PROVIDER", "auto")
    import ssri_model.data.topography as topography

    monkeypatch.setattr(topography, "_opentopo_rate_limited", False)

    def _fail_opentopo(*_args, **_kwargs):
        raise TopographyDownloadError("HTTP 429 maximum rate limit exceeded")

    gee_path = tmp_path / "gee_dem.tif"
    _write_geotiff(gee_path)

    with patch(
        "ssri_model.data.topography.download_dem_from_opentopo",
        side_effect=_fail_opentopo,
    ), patch(
        "ssri_model.data.topography.download_dem_from_gee",
        return_value=gee_path,
    ) as gee_mock:
        out = download_dem((-1.0, 6.0, 0.0, 7.0), tmp_path / "dem.tif")
        assert out == gee_path
        gee_mock.assert_called_once()
    assert get_last_dem_acquisition_source() is not None
    assert "gee" in (get_last_dem_acquisition_source() or "")


def test_opentopo_missing_key_falls_back_to_gee_in_auto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SSRI_DEM_PROVIDER", "auto")
    import ssri_model.data.topography as topography

    monkeypatch.setattr(topography, "_opentopo_rate_limited", False)
    gee_path = tmp_path / "gee_dem.tif"
    _write_geotiff(gee_path)

    with patch(
        "ssri_model.data.topography.download_dem_from_opentopo",
        side_effect=topography.TopographyConfigError(
            "Missing required environment variable: OPENTOPOGRAPHY_API_KEY"
        ),
    ), patch(
        "ssri_model.data.topography.download_dem_from_gee",
        return_value=gee_path,
    ) as gee_mock:
        out = download_dem((-1.0, 6.0, 0.0, 7.0), tmp_path / "dem.tif")
        assert out == gee_path
        gee_mock.assert_called_once()
    assert "gee" in (get_last_dem_acquisition_source() or "")


def test_from_env_resolves_relative_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SSRI_REPO_ROOT", str(tmp_path))
    relative = "data/geophysics/processed/lagos_gravity.tif"
    target = tmp_path / relative
    _write_geotiff(target)
    monkeypatch.setenv("GRAVITY_DATA_PATH", relative)
    monkeypatch.setenv("MAGNETIC_DATA_PATH", relative)
    monkeypatch.setenv("SSRI_GRAVITY_SOURCE", "wgm2012_bouguer")
    config = GeophysicsConfig.from_env()
    assert config.gravity_data_path == target.resolve()
    assert config.gravity_source == "wgm2012_bouguer"
