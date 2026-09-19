"""Prepare Lagos-region WGM2012 / EMAG2v3 GeoTIFF qualification rasters.

Does not invent data. Converts/clips authoritative downloads only.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "geophysics" / "raw"
PROCESSED = ROOT / "data" / "geophysics" / "processed"
PROVENANCE = ROOT / "data" / "geophysics" / "provenance"

# Lagos AOI with margin for warp/resample (degrees).
LAGOS_BOUNDS = (2.5, 5.5, 4.5, 7.5)  # min_lon, min_lat, max_lon, max_lat
CRS_WGS84 = CRS.from_epsg(4326)

WGM_RAW = RAW / "WGM2012_Bouguer_ponc_2min.grd"
EMAG_RAW = RAW / "EMAG2_V3_20170530_UpCont.tif"

GRAVITY_OUT = PROCESSED / "lagos_gravity_wgm2012_bouguer.tif"
MAGNETIC_OUT = PROCESSED / "lagos_magnetic_emag2v3_uc4km.tif"

EMAG_NODATA = 99999.0
GRAVITY_NODATA = -9999.0


def _clip_write(
    *,
    src_path: Path,
    dst_path: Path,
    bounds: tuple[float, float, float, float],
    nodata_out: float,
    force_nodata_values: set[float] | None = None,
    description: str,
) -> dict:
    min_lon, min_lat, max_lon, max_lat = bounds
    with rasterio.open(src_path) as src:
        window = from_bounds(min_lon, min_lat, max_lon, max_lat, transform=src.transform)
        data = src.read(1, window=window, boundless=True, fill_value=np.nan).astype(
            np.float64
        )
        transform = src.window_transform(window)

        # Normalize nodata representation.
        mask = ~np.isfinite(data)
        src_nodata = src.nodata
        if src_nodata is not None and np.isfinite(src_nodata):
            mask |= np.isclose(data, float(src_nodata), equal_nan=False)
        if force_nodata_values:
            for sentinel in force_nodata_values:
                mask |= np.isclose(data, sentinel, rtol=0.0, atol=0.0)

        valid = data[~mask]
        if valid.size == 0:
            raise RuntimeError(f"Clip for {src_path.name} produced only nodata")

        out = np.full(data.shape, nodata_out, dtype=np.float32)
        out[~mask] = valid.astype(np.float32)

        profile = {
            "driver": "GTiff",
            "height": out.shape[0],
            "width": out.shape[1],
            "count": 1,
            "dtype": "float32",
            "crs": CRS_WGS84,
            "transform": transform,
            "nodata": nodata_out,
            "compress": "deflate",
            "tiled": True,
        }
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(dst_path, "w", **profile) as dst:
            dst.write(out, 1)
            dst.update_tags(
                DESCRIPTION=description,
                SSRI_QUALIFICATION="true",
                SOURCE_FILE=src_path.name,
            )

        return {
            "source": src_path.name,
            "output": str(dst_path.relative_to(ROOT)).replace("\\", "/"),
            "shape": [int(out.shape[0]), int(out.shape[1])],
            "bounds": [min_lon, min_lat, max_lon, max_lat],
            "crs": "EPSG:4326",
            "nodata": nodata_out,
            "valid_min": float(np.min(valid)),
            "valid_max": float(np.max(valid)),
            "valid_count": int(valid.size),
            "nodata_count": int(mask.sum()),
            "dtype": "float32",
        }


def main() -> int:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    PROVENANCE.mkdir(parents=True, exist_ok=True)

    if not WGM_RAW.is_file():
        raise SystemExit(f"Missing WGM raw file: {WGM_RAW}")
    if not EMAG_RAW.is_file():
        raise SystemExit(f"Missing EMAG raw file: {EMAG_RAW}")

    gravity_meta = _clip_write(
        src_path=WGM_RAW,
        dst_path=GRAVITY_OUT,
        bounds=LAGOS_BOUNDS,
        nodata_out=GRAVITY_NODATA,
        description=(
            "WGM2012 Complete Spherical Bouguer anomaly (mGal), "
            "Lagos AOI clip; native ~2 arc-min"
        ),
    )
    magnetic_meta = _clip_write(
        src_path=EMAG_RAW,
        dst_path=MAGNETIC_OUT,
        bounds=LAGOS_BOUNDS,
        nodata_out=EMAG_NODATA,
        force_nodata_values={EMAG_NODATA},
        description=(
            "EMAG2v3 4 km upward-continued total-field magnetic anomaly (nT), "
            "Lagos AOI clip; native ~2 arc-min; nodata=99999"
        ),
    )

    provenance = {
        "gravity": {
            "dataset": "WGM2012 Complete Spherical Bouguer anomaly",
            "provider": "Bureau Gravimétrique International (BGI)",
            "citation_doi": "https://doi.org/10.18168/bgi.23",
            "source_url_original": (
                "http://webftp.omp.obs-mip.fr/bgi/wgm_grid/data/"
                "WGM2012_Bouguer_ponc_2min.grd"
            ),
            "source_url_obtained": (
                "https://web.archive.org/web/20170708002547if_/"
                "http://webftp.omp.obs-mip.fr/bgi/wgm_grid/data/"
                "WGM2012_Bouguer_ponc_2min.grd"
            ),
            "note": (
                "Official BGI FTP hostname no longer resolves; obtained via "
                "Internet Archive snapshot of the authoritative BGI distribution."
            ),
            "license": (
                "Academic/research use per BGI WGM2012 disclaimer "
                "(no warranty; BGI not responsible for consequences of use)."
            ),
            "units": "mGal",
            "native_resolution": "2 arc-minutes",
            "crs_assigned": "EPSG:4326",
            "anomaly_definition": "Complete spherical Bouguer anomaly",
            "processed": gravity_meta,
            "scientific_limitation": (
                "Regional ~2' grid; bilinear resampling onto SSRI 30 m UTM does "
                "not create new geophysical information."
            ),
        },
        "magnetics": {
            "dataset": "EMAG2v3 4 km upward-continued magnetic anomaly",
            "provider": "NOAA / NCEI",
            "citation_doi": "https://doi.org/10.7289/V5H70CVX",
            "source_url": (
                "https://www.ngdc.noaa.gov/geomag/data/EMAG2/"
                "EMAG2_V3_20170530/EMAG2_V3_20170530_UpCont.tif"
            ),
            "version": "EMAG2_V3_20170530",
            "units": "nT",
            "native_resolution": "2 arc-minutes",
            "crs_assigned": "EPSG:4326",
            "nodata": 99999,
            "anomaly_definition": (
                "Scalar total-field lithospheric magnetic anomaly at continuous "
                "4 km altitude above the WGS84 ellipsoid"
            ),
            "processed": magnetic_meta,
            "scientific_limitation": (
                "Regional ~2' grid; bilinear resampling onto SSRI 30 m UTM does "
                "not create new geophysical information."
            ),
        },
        "aoi_bounds_wgs84": {
            "min_lon": LAGOS_BOUNDS[0],
            "min_lat": LAGOS_BOUNDS[1],
            "max_lon": LAGOS_BOUNDS[2],
            "max_lat": LAGOS_BOUNDS[3],
        },
    }
    (PROVENANCE / "lagos_geophysics_provenance.json").write_text(
        json.dumps(provenance, indent=2),
        encoding="utf-8",
    )
    print("PREPARE_GEOPHYSICS=OK")
    print(f"GRAVITY_OUT={GRAVITY_OUT}")
    print(f"MAGNETIC_OUT={MAGNETIC_OUT}")
    print(
        f"GRAVITY_RANGE={gravity_meta['valid_min']:.3f}:{gravity_meta['valid_max']:.3f}"
    )
    print(
        f"MAGNETIC_RANGE={magnetic_meta['valid_min']:.3f}:{magnetic_meta['valid_max']:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
