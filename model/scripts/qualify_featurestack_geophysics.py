"""Qualify real WGM2012/EMAG2v3 consumption through SSRI geophysics loaders."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GRAVITY = ROOT / "data" / "geophysics" / "processed" / "lagos_gravity_wgm2012_bouguer.tif"
MAGNETIC = (
    ROOT / "data" / "geophysics" / "processed" / "lagos_magnetic_emag2v3_uc4km.tif"
)

# Tiny Lagos AOI for FeatureStack-like alignment (degrees).
AOI = (3.35, 6.45, 3.45, 6.55)


def main() -> int:
    os.environ["GRAVITY_DATA_PATH"] = str(GRAVITY)
    os.environ["MAGNETIC_DATA_PATH"] = str(MAGNETIC)

    from ssri_model.data.feature_engineering import build_grid_spec_from_aoi
    from ssri_model.data.geophysics import load_gravity, load_magnetics

    if not GRAVITY.is_file() or not MAGNETIC.is_file():
        print("FEATURESTACK_GEOPHYSICS=FAIL missing_processed_rasters")
        return 1

    grid = build_grid_spec_from_aoi(AOI, resolution_m=30.0)
    gravity = load_gravity(AOI, target_grid=grid)
    magnetics = load_magnetics(AOI, target_grid=grid)

    assert gravity.shape == grid.shape
    assert magnetics.shape == grid.shape
    assert gravity.crs == grid.crs
    assert magnetics.crs == grid.crs

    g = gravity.data.astype(np.float64)
    m = magnetics.data.astype(np.float64)
    g_mask = np.isclose(g, gravity.nodata) | ~np.isfinite(g)
    m_mask = np.isclose(m, magnetics.nodata) | ~np.isfinite(m)
    # EMAG documented sentinel must not appear as valid after alignment.
    if np.any(np.isclose(m[~m_mask], 99999.0)):
        print("FEATURESTACK_GEOPHYSICS=FAIL emag_nodata_leak")
        return 1
    if g[~g_mask].size == 0 or m[~m_mask].size == 0:
        print("FEATURESTACK_GEOPHYSICS=FAIL empty_valid")
        return 1
    if not np.isfinite(g[~g_mask]).all() or not np.isfinite(m[~m_mask]).all():
        print("FEATURESTACK_GEOPHYSICS=FAIL nan_inf")
        return 1

    g_valid = g[~g_mask]
    m_valid = m[~m_mask]
    g_z = (g_valid - g_valid.mean()) / (g_valid.std() + 1e-12)
    m_z = (m_valid - m_valid.mean()) / (m_valid.std() + 1e-12)
    if not np.isfinite(g_z).all() or not np.isfinite(m_z).all():
        print("FEATURESTACK_GEOPHYSICS=FAIL norm_nan")
        return 1

    print("FEATURESTACK_GEOPHYSICS=OK")
    print(f"TARGET_CRS={grid.crs}")
    print(f"TARGET_SHAPE={grid.height}x{grid.width}")
    print(f"TARGET_RES_M={abs(grid.transform.a):.3f}")
    print(f"GRAVITY_VALID={int((~g_mask).sum())}")
    print(f"MAGNETIC_VALID={int((~m_mask).sum())}")
    print(f"GRAVITY_MINMAX={float(g_valid.min()):.3f}:{float(g_valid.max()):.3f}")
    print(f"MAGNETIC_MINMAX={float(m_valid.min()):.3f}:{float(m_valid.max()):.3f}")
    print("GRAVITY_PROVIDER=wgm2012_bouguer")
    print("MAGNETIC_PROVIDER=emag2v3_uc4km")
    print(
        "NOTE=native_geophysics_resolution_is_regional_2arcmin;"
        "30m_target_is_resampled_not_native"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
