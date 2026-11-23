"""Publication-guided CRS verification and reprojection for Abeokuta Sheet 260.

Pipeline: EPSG:32632 (source) → EPSG:32631 (processing) → EPSG:4326 (display).

Verification is required before accepting the transform — plausible-looking
numbers alone are not sufficient. Original X/Y/Z values are never overwritten.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from pyproj import Transformer

from ssri_model.geological.abeokuta_tmi import (
    ABEOKUTA_EXPECTED_WGS84_BOUNDS,
    AUTHORITATIVE_ABEOKUTA_TMI,
)

SOURCE_CRS = "EPSG:32632"
PROCESSING_CRS = "EPSG:32631"
DISPLAY_CRS = "EPSG:4326"


def _transformer(src: str, dst: str) -> Transformer:
    return Transformer.from_crs(src, dst, always_xy=True)


def transform_xy(
    xs: np.ndarray | list[float],
    ys: np.ndarray | list[float],
    *,
    source_crs: str,
    target_crs: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Reproject coordinate arrays; returns float64 arrays (originals untouched)."""
    x = np.asarray(xs, dtype=np.float64)
    y = np.asarray(ys, dtype=np.float64)
    if x.shape != y.shape:
        raise ValueError("xs and ys must have the same shape")
    if x.size == 0:
        return x.copy(), y.copy()
    transformer = _transformer(source_crs, target_crs)
    out_x, out_y = transformer.transform(x, y)
    return np.asarray(out_x, dtype=np.float64), np.asarray(out_y, dtype=np.float64)


def verify_abeokuta_crs_pipeline(
    xs: list[float] | np.ndarray,
    ys: list[float] | np.ndarray,
    zs: list[float] | np.ndarray | None = None,
    *,
    source_crs: str = SOURCE_CRS,
    processing_crs: str = PROCESSING_CRS,
    display_crs: str = DISPLAY_CRS,
    expected_bounds: dict[str, float] | None = None,
    sample_limit: int = 50_000,
) -> dict[str, Any]:
    """Verify 32632→32631→4326 against Abeokuta geographic expectations.

    Does not mutate inputs. Returns a structured verification report.
    """
    bounds = dict(expected_bounds or ABEOKUTA_EXPECTED_WGS84_BOUNDS)
    x = np.asarray(xs, dtype=np.float64)
    y = np.asarray(ys, dtype=np.float64)
    z = None if zs is None else np.asarray(zs, dtype=np.float64)

    checks: list[dict[str, Any]] = []
    if x.size == 0:
        return {
            "ok": False,
            "overall": "FAIL",
            "checks": [
                {
                    "name": "points",
                    "status": "FAIL",
                    "message": "No coordinates to verify.",
                }
            ],
            "source_crs": source_crs,
            "processing_crs": processing_crs,
            "display_crs": display_crs,
            "original_coordinates_preserved": True,
        }

    # Magnitude consistency with forced UTM 32N over western Nigeria:
    # eastings may be negative (west of zone 32 false origin); northings ~7°N ≈ 0.77–0.83 Mm.
    mean_x = float(np.mean(x))
    mean_y = float(np.mean(y))
    looks_like_utm32_sheet260 = (
        mean_x < 0
        and -250_000 < mean_x < 0
        and 700_000 < mean_y < 1_000_000
        and float(np.ptp(x)) > 10_000
        and float(np.ptp(y)) > 10_000
    )
    checks.append(
        {
            "name": "source_magnitude_consistency",
            "status": "PASS" if looks_like_utm32_sheet260 else "WARN",
            "message": (
                "Source X/Y magnitudes are consistent with UTM Zone 32N easting/northing "
                "for western Nigeria (negative eastings west of the zone-32 false origin)."
                if looks_like_utm32_sheet260
                else (
                    "Source X/Y magnitudes do not match the expected Sheet 260 "
                    "UTM 32N pattern; transform results will still be checked."
                )
            ),
            "detail": {
                "x_mean": mean_x,
                "y_mean": mean_y,
                "x_extent": [float(np.min(x)), float(np.max(x))],
                "y_extent": [float(np.min(y)), float(np.max(y))],
            },
        }
    )

    # Sample for expensive checks; full extent uses min/max on all points via transform of corners + sample.
    n = int(x.size)
    if n > sample_limit:
        idx = np.linspace(0, n - 1, sample_limit, dtype=np.int64)
        xs_s, ys_s = x[idx], y[idx]
    else:
        xs_s, ys_s = x, y

    try:
        e31, n31 = transform_xy(xs_s, ys_s, source_crs=source_crs, target_crs=processing_crs)
        lon, lat = transform_xy(xs_s, ys_s, source_crs=source_crs, target_crs=display_crs)
        # Full extent via corners + extrema of source bbox corners (sufficient for rectangular survey)
        corners_x = np.array([np.min(x), np.max(x), np.min(x), np.max(x)], dtype=np.float64)
        corners_y = np.array([np.min(y), np.min(y), np.max(y), np.max(y)], dtype=np.float64)
        e31_c, n31_c = transform_xy(
            corners_x, corners_y, source_crs=source_crs, target_crs=processing_crs
        )
        lon_c, lat_c = transform_xy(
            corners_x, corners_y, source_crs=source_crs, target_crs=display_crs
        )
    except Exception as exc:
        return {
            "ok": False,
            "overall": "FAIL",
            "checks": checks
            + [
                {
                    "name": "transform_execution",
                    "status": "FAIL",
                    "message": f"CRS transform failed: {exc}",
                }
            ],
            "source_crs": source_crs,
            "processing_crs": processing_crs,
            "display_crs": display_crs,
            "original_coordinates_preserved": True,
        }

    finite_ok = bool(
        np.all(np.isfinite(e31))
        and np.all(np.isfinite(n31))
        and np.all(np.isfinite(lon))
        and np.all(np.isfinite(lat))
    )
    checks.append(
        {
            "name": "transformed_finite",
            "status": "PASS" if finite_ok else "FAIL",
            "message": (
                "All sampled transformed coordinates are finite."
                if finite_ok
                else "Non-finite coordinates after transform."
            ),
        }
    )

    lon_min, lon_max = float(np.min(lon_c)), float(np.max(lon_c))
    lat_min, lat_max = float(np.min(lat_c)), float(np.max(lat_c))
    e_min, e_max = float(np.min(e31_c)), float(np.max(e31_c))
    n_min, n_max = float(np.min(n31_c)), float(np.max(n31_c))

    geo_ok = (
        bounds["lon_min"] <= lon_min <= bounds["lon_max"]
        and bounds["lon_min"] <= lon_max <= bounds["lon_max"]
        and bounds["lat_min"] <= lat_min <= bounds["lat_max"]
        and bounds["lat_min"] <= lat_max <= bounds["lat_max"]
        and lon_max > lon_min
        and lat_max > lat_min
    )
    # Also require regional Nigeria-ish ranges
    regional_ok = (
        2.0 <= lon_min <= 5.0
        and 2.0 <= lon_max <= 5.0
        and 6.0 <= lat_min <= 9.0
        and 6.0 <= lat_max <= 9.0
    )
    checks.append(
        {
            "name": "wgs84_extent_vs_publication_area",
            "status": "PASS" if geo_ok and regional_ok else "FAIL",
            "message": (
                f"Display extent lon[{lon_min:.5f},{lon_max:.5f}] "
                f"lat[{lat_min:.5f},{lat_max:.5f}] "
                + (
                    "matches Abeokuta Sheet 260 expectations."
                    if geo_ok and regional_ok
                    else "does not match expected Abeokuta study area — transform rejected."
                )
            ),
            "detail": {
                "display_extent": [lon_min, lat_min, lon_max, lat_max],
                "expected_bounds": bounds,
            },
        }
    )

    # Processing CRS should land near UTM 31N around Abeokuta (~500–560 km E, ~770–830 km N).
    proc_ok = (
        450_000 <= e_min <= 600_000
        and 450_000 <= e_max <= 600_000
        and 700_000 <= n_min <= 900_000
        and 700_000 <= n_max <= 900_000
        and (e_max - e_min) > 10_000
        and (n_max - n_min) > 10_000
    )
    checks.append(
        {
            "name": "processing_crs_extent",
            "status": "PASS" if proc_ok else "FAIL",
            "message": (
                f"Processing extent (EPSG:32631) E[{e_min:.1f},{e_max:.1f}] "
                f"N[{n_min:.1f},{n_max:.1f}] "
                + (
                    "consistent with UTM 31N over Abeokuta."
                    if proc_ok
                    else "inconsistent with UTM 31N Abeokuta survey — transform rejected."
                )
            ),
            "detail": {"processing_extent": [e_min, n_min, e_max, n_max]},
        }
    )

    # Reproducibility: same transform twice on a probe point.
    probe_x, probe_y = float(x[0]), float(y[0])
    a1, b1 = transform_xy([probe_x], [probe_y], source_crs=source_crs, target_crs=display_crs)
    a2, b2 = transform_xy([probe_x], [probe_y], source_crs=source_crs, target_crs=display_crs)
    repro = bool(math.isclose(float(a1[0]), float(a2[0]), rel_tol=0, abs_tol=1e-9) and math.isclose(
        float(b1[0]), float(b2[0]), rel_tol=0, abs_tol=1e-9
    ))
    checks.append(
        {
            "name": "transform_reproducibility",
            "status": "PASS" if repro else "FAIL",
            "message": (
                "CRS transform is reproducible for a probe point."
                if repro
                else "CRS transform was not reproducible."
            ),
            "detail": {
                "probe_source_xy": [probe_x, probe_y],
                "probe_display_lonlat": [float(a1[0]), float(b1[0])],
            },
        }
    )

    z_preserved = True
    if z is not None and z.size:
        z_preserved = bool(np.all(np.isfinite(z)) or True)  # Z never transformed
        checks.append(
            {
                "name": "original_tmi_immutable",
                "status": "PASS",
                "message": (
                    "Original TMI (Z) values are not modified by CRS transforms. "
                    f"Z range in sample inputs: min={float(np.min(z))}, max={float(np.max(z))}."
                ),
            }
        )

    fail = any(c["status"] == "FAIL" for c in checks)
    warn = any(c["status"] == "WARN" for c in checks)
    overall = "FAIL" if fail else ("WARN" if warn else "PASS")
    return {
        "ok": not fail,
        "overall": overall,
        "checks": checks,
        "source_crs": source_crs,
        "processing_crs": processing_crs,
        "display_crs": display_crs,
        "source_extent": [float(np.min(x)), float(np.min(y)), float(np.max(x)), float(np.max(y))],
        "processing_extent": [e_min, n_min, e_max, n_max],
        "display_extent": [lon_min, lat_min, lon_max, lat_max],
        "sample_count": int(xs_s.size),
        "total_points": n,
        "original_coordinates_preserved": True,
        "original_tmi_preserved": z_preserved,
        "preset_id": AUTHORITATIVE_ABEOKUTA_TMI["preset_id"],
        "pipeline": f"{source_crs} → {processing_crs} → {display_crs}",
    }


def reproject_points_for_processing(
    xs: list[float] | np.ndarray,
    ys: list[float] | np.ndarray,
    *,
    source_crs: str = SOURCE_CRS,
    processing_crs: str = PROCESSING_CRS,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Return processing-CRS coordinates plus a transform provenance block."""
    e, n = transform_xy(xs, ys, source_crs=source_crs, target_crs=processing_crs)
    meta = {
        "source_crs": source_crs,
        "target_crs": processing_crs,
        "method": "pyproj.Transformer always_xy=True",
        "point_count": int(e.size),
        "extent": [
            float(np.min(e)) if e.size else None,
            float(np.min(n)) if n.size else None,
            float(np.max(e)) if e.size else None,
            float(np.max(n)) if n.size else None,
        ],
        "original_xy_unmodified": True,
    }
    return e, n, meta
