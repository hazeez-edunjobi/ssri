"""Standalone validation of Lagos gravity/magnetic qualification GeoTIFFs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
GRAVITY = ROOT / "data" / "geophysics" / "processed" / "lagos_gravity_wgm2012_bouguer.tif"
MAGNETIC = (
    ROOT / "data" / "geophysics" / "processed" / "lagos_magnetic_emag2v3_uc4km.tif"
)

# Qualification AOI that must be covered.
AOI = (3.2, 6.3, 3.6, 6.7)
GRAVITY_NODATA = -9999.0
MAGNETIC_NODATA = 99999.0


def _check_raster(
    path: Path,
    *,
    expected_nodata: float,
    units_label: str,
    plausible: tuple[float, float],
    aoi: tuple[float, float, float, float],
) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing_file:{path.name}"]

    with rasterio.open(path) as ds:
        if ds.count != 1:
            errors.append(f"band_count:{ds.count}")
        if ds.crs is None:
            errors.append("missing_crs")
        else:
            epsg = ds.crs.to_epsg()
            if epsg != 4326 and "4326" not in ds.crs.to_string():
                errors.append(f"unexpected_crs:{ds.crs}")
        if ds.dtypes[0] not in {"float32", "float64"}:
            errors.append(f"dtype:{ds.dtypes[0]}")
        if ds.nodata is None:
            errors.append("missing_nodata")
        elif not np.isclose(float(ds.nodata), expected_nodata):
            errors.append(f"nodata_mismatch:{ds.nodata}")

        left, bottom, right, top = ds.bounds
        amin_lon, amin_lat, amax_lon, amax_lat = aoi
        if not (left <= amin_lon and right >= amax_lon and bottom <= amin_lat and top >= amax_lat):
            errors.append(
                f"aoi_not_covered:bounds=({left},{bottom},{right},{top})"
            )

        # Detect obvious north-south inversion: transform.e should be negative for north-up.
        if ds.transform.e >= 0:
            errors.append("possible_axis_inversion:positive_y_pixel_size")

        data = ds.read(1).astype(np.float64)
        nodata = float(ds.nodata) if ds.nodata is not None else expected_nodata
        mask = np.isclose(data, nodata) | ~np.isfinite(data)
        valid = data[~mask]
        if valid.size == 0:
            errors.append("all_nodata")
        else:
            vmin, vmax = float(valid.min()), float(valid.max())
            if vmin < plausible[0] or vmax > plausible[1]:
                errors.append(f"implausible_range:{vmin}:{vmax}:{units_label}")
            # Nodata sentinel must not appear in valid set.
            if np.any(np.isclose(valid, expected_nodata)):
                errors.append("nodata_in_valid_values")
            if np.any(~np.isfinite(valid)):
                errors.append("nan_inf_in_valid")

        # Pixel size should be ~2 arc-min (0.0333 deg), allow mild clip rounding.
        res_x, res_y = abs(ds.res[0]), abs(ds.res[1])
        if not (0.02 <= res_x <= 0.05 and 0.02 <= res_y <= 0.05):
            errors.append(f"unexpected_resolution:{res_x}:{res_y}")

    return errors


def main() -> int:
    g_err = _check_raster(
        GRAVITY,
        expected_nodata=GRAVITY_NODATA,
        units_label="mGal",
        plausible=(-800.0, 1200.0),
        aoi=AOI,
    )
    m_err = _check_raster(
        MAGNETIC,
        expected_nodata=MAGNETIC_NODATA,
        units_label="nT",
        plausible=(-3000.0, 3000.0),
        aoi=AOI,
    )

    print("GRAVITY_RASTER=" + ("OK" if not g_err else "FAIL"))
    if g_err:
        print("GRAVITY_ERRORS=" + ",".join(g_err))
    print("MAGNETIC_RASTER=" + ("OK" if not m_err else "FAIL"))
    if m_err:
        print("MAGNETIC_ERRORS=" + ",".join(m_err))

    return 0 if not g_err and not m_err else 1


if __name__ == "__main__":
    raise SystemExit(main())
