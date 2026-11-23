"""Analytical-surface QA for magnetic processing (software correctness).

Synthetic surfaces are not scientific validation of Abeokuta geology.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from ssri_model.geological.magnetic_processing import (
    analytic_signal,
    first_horizontal_derivative,
    first_vertical_derivative,
    gaussian_filter_grid,
    grid_points_to_array,
    radially_averaged_power_spectrum,
    reduction_to_equator,
    source_lattice_reconciliation,
    tilt_derivative,
)

REPO_CSV = Path(__file__).resolve().parents[2] / "sheet 260_Abeokuta.csv"


def _grid_from_func(fn, *, n=32, dx=100.0):
    xs = []
    ys = []
    zs = []
    for iy in range(n):
        for ix in range(n):
            x = 500_000.0 + ix * dx
            y = 790_000.0 + iy * dx
            xs.append(x)
            ys.append(y)
            zs.append(fn(ix * dx, iy * dx))
    grid, mask, meta = grid_points_to_array(
        np.asarray(xs), np.asarray(ys), np.asarray(zs), resolution=dx, method="scatter_bin"
    )
    return grid, mask, meta


def test_constant_surface_derivatives_near_zero():
    grid, mask, meta = _grid_from_func(lambda x, y: 42.0)
    dx = meta["resolution_x_m"]
    dy = meta["resolution_y_m"]
    fvd, _ = first_vertical_derivative(grid, mask, dx=dx, dy=dy)
    fhd, _ = first_horizontal_derivative(grid, mask, dx=dx, dy=dy)
    assert float(np.max(np.abs(fvd[mask]))) < 1e-4
    assert float(np.max(np.abs(fhd[mask]))) < 1e-4


def test_linear_gradient_horizontal_magnitude():
    # T = 0.01 * x_local  → ∂T/∂x ≈ 0.01 nT/m
    # Periodic FFT of a pure ramp has edge ringing; use a larger grid and
    # check that the central region is order-correct and positive.
    grid, mask, meta = _grid_from_func(lambda x, y: 0.01 * x, n=64)
    dx = meta["resolution_x_m"]
    dy = meta["resolution_y_m"]
    fhd, meta_h = first_horizontal_derivative(grid, mask, dx=dx, dy=dy)
    interior = np.zeros_like(mask, dtype=bool)
    interior[16:48, 16:48] = True
    vals = fhd[interior & mask]
    assert meta_h["units"] == "nT_per_m"
    assert float(np.median(vals)) > 0.005
    assert abs(float(np.median(vals)) - 0.01) < 0.008


def test_sinusoid_gaussian_lowpass_attenuates_short_wave():
    # Wavelength 400 m on 100 m grid — shorter than 2000 m cutoff → attenuated
    lam = 400.0
    grid, mask, meta = _grid_from_func(
        lambda x, y: math.sin(2 * math.pi * x / lam), n=64
    )
    dx = meta["resolution_x_m"]
    dy = meta["resolution_y_m"]
    out, gmeta = gaussian_filter_grid(
        grid, mask, dx=dx, dy=dy, wavelength_m=2000.0, sigma=0.5, mode="low_pass"
    )
    assert gmeta["response_type"] == "low_pass"
    assert float(np.std(out[mask])) < 0.5 * float(np.std(grid[mask]))


def test_gaussian_highpass_residual_mode():
    grid, mask, meta = _grid_from_func(lambda x, y: math.sin(2 * math.pi * x / 2000.0))
    dx = meta["resolution_x_m"]
    dy = meta["resolution_y_m"]
    lp, _ = gaussian_filter_grid(
        grid, mask, dx=dx, dy=dy, wavelength_m=2000.0, sigma=0.5, mode="low_pass"
    )
    hp, hmeta = gaussian_filter_grid(
        grid, mask, dx=dx, dy=dy, wavelength_m=2000.0, sigma=0.5, mode="high_pass"
    )
    assert hmeta["response_type"] == "high_pass_residual"
    # T ≈ LP + HP
    recon = lp[mask] + hp[mask]
    assert float(np.sqrt(np.mean((recon - grid[mask]) ** 2))) < 1e-3


def test_missing_cells_remain_nodata_not_interpolated():
    xs = np.array([0.0, 100.0, 0.0, 100.0, 200.0])
    ys = np.array([0.0, 0.0, 100.0, 100.0, 100.0])
    zs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    grid, mask, meta = grid_points_to_array(xs, ys, zs, resolution=100.0, method="scatter_bin")
    assert meta["cells_populated_by_interpolation"] == 0
    assert meta["cells_remaining_nodata"] >= 1
    assert int(np.count_nonzero(~mask)) == meta["cells_remaining_nodata"]


def test_nearest_marks_interpolated_cells():
    xs = np.array([0.0, 200.0, 0.0, 200.0])
    ys = np.array([0.0, 0.0, 200.0, 200.0])
    zs = np.array([1.0, 2.0, 3.0, 4.0])
    grid, mask, meta = grid_points_to_array(xs, ys, zs, resolution=100.0, method="nearest")
    assert meta["cells_remaining_nodata"] == 0
    assert meta["cells_populated_by_interpolation"] > 0


def test_rte_clip_diagnostics_and_optional_disable():
    grid, mask, meta = _grid_from_func(
        lambda x, y: 10.0 * math.sin(2 * math.pi * x / 800.0)
        + 5.0 * math.cos(2 * math.pi * y / 1200.0)
    )
    dx = meta["resolution_x_m"]
    dy = meta["resolution_y_m"]
    clipped, cmeta = reduction_to_equator(
        grid, mask, dx=dx, dy=dy, inclination_deg=11.04, declination_deg=3.52, amplitude_clip=10.0
    )
    unclipped, umeta = reduction_to_equator(
        grid,
        mask,
        dx=dx,
        dy=dy,
        inclination_deg=11.04,
        declination_deg=3.52,
        amplitude_clip=None,
    )
    assert cmeta["implementation_choices"]["amplitude_clip"]["publication_parameter"] is False
    assert cmeta["implementation_choices"]["amplitude_clip"]["clip_applied"] is True
    assert umeta["implementation_choices"]["amplitude_clip"]["clip_applied"] is False
    assert np.all(np.isfinite(clipped[mask]))
    assert np.all(np.isfinite(unclipped[mask]))


def test_analytic_signal_and_tilt_units():
    grid, mask, meta = _grid_from_func(
        lambda x, y: math.exp(-((x - 1500) ** 2 + (y - 1500) ** 2) / (2 * 400**2))
    )
    dx = meta["resolution_x_m"]
    dy = meta["resolution_y_m"]
    ams, ameta = analytic_signal(grid, mask, dx=dx, dy=dy)
    tilt, tmeta = tilt_derivative(grid, mask, dx=dx, dy=dy)
    assert ameta["units"] == "nT_per_m"
    assert tmeta["units"] == "radians"
    assert float(np.min(ams[mask])) >= -1e-6
    assert float(np.min(tilt[mask])) >= -math.pi / 2 - 1e-5
    assert float(np.max(tilt[mask])) <= math.pi / 2 + 1e-5


def test_raps_frequency_calibration_peak_near_known_wavelength():
    lam = 800.0
    grid, mask, meta = _grid_from_func(
        lambda x, y: math.sin(2 * math.pi * x / lam), n=64, dx=50.0
    )
    dx = meta["resolution_x_m"]
    dy = meta["resolution_y_m"]
    payload, pmeta = radially_averaged_power_spectrum(grid, mask, dx=dx, dy=dy, n_bins=48)
    assert pmeta["wavenumber_convention"].startswith("angular")
    assert payload["dc_excluded"] is True
    assert payload["depth_interpretation"]["claimed"] is False
    waves = payload["wavelength_m"]
    logp = payload["log10_power"]
    pairs = [
        (w, lp)
        for w, lp in zip(waves, logp)
        if w is not None and lp is not None and 200 < w < 2000
    ]
    assert pairs
    best = max(pairs, key=lambda t: t[1])
    # Peak wavelength should be near the injected sinusoid (FFT radial averaging tolerance)
    assert abs(best[0] - lam) / lam < 0.35


def test_nodata_propagated_through_filters():
    grid, mask, meta = _grid_from_func(lambda x, y: float(x + y), n=24)
    # Punch a hole
    mask2 = mask.copy()
    mask2[10:14, 10:14] = False
    grid2 = grid.copy()
    grid2[~mask2] = -9999.0
    dx = meta["resolution_x_m"]
    dy = meta["resolution_y_m"]
    out, _ = first_vertical_derivative(grid2, mask2, dx=dx, dy=dy)
    assert np.all(out[~mask2] == -9999.0)


@pytest.mark.skipif(not REPO_CSV.is_file(), reason="Abeokuta CSV missing")
def test_abeokuta_source_lattice_reconciliation_matches_inspect():
    import csv

    xs = []
    ys = []
    with REPO_CSV.open(encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            xs.append(float(row[0]))
            ys.append(float(row[1]))
    recon = source_lattice_reconciliation(np.asarray(xs), np.asarray(ys), spacing=100.0)
    assert recon["expected_lattice_cells"] == 315282
    assert recon["empty_lattice_positions"] == 7129
    assert recon["original_observation_count"] == 308153
