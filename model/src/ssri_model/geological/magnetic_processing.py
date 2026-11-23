"""Publication-guided magnetic processing for aeromagnetic TMI grids.

Supported operations (each explicit, logged, never silent defaults for non-Abeokuta):
  - tmi, rte, gaussian, analytic_signal
  - first_vertical_derivative, first_horizontal_derivative, tilt_derivative
  - radially_averaged_power_spectrum

Scientific boundary: geophysical products for comparison with the publication —
not hazard labels, faults, sinkholes, or Stage 2.5 features.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ssri_model.geological.abeokuta_tmi import ABEOKUTA_PUBLICATION_MAGNETIC_PARAMS
from ssri_model.geological.models import MEASUREMENT_TOTAL_MAGNETIC_INTENSITY

SOFTWARE_ID = "ssri_model.geological.magnetic_processing"
SOFTWARE_VERSION = "1.1.0"

OPERATION_TMI = "tmi"
OPERATION_RTE = "rte"
OPERATION_GAUSSIAN = "gaussian"
OPERATION_ANALYTIC_SIGNAL = "analytic_signal"
OPERATION_FVD = "first_vertical_derivative"
OPERATION_FHD = "first_horizontal_derivative"
OPERATION_TILT = "tilt_derivative"
OPERATION_RAPS = "radially_averaged_power_spectrum"

SUPPORTED_OPERATIONS = (
    OPERATION_TMI,
    OPERATION_RTE,
    OPERATION_GAUSSIAN,
    OPERATION_ANALYTIC_SIGNAL,
    OPERATION_FVD,
    OPERATION_FHD,
    OPERATION_TILT,
    OPERATION_RAPS,
)

# Implementation choices — not publication parameters.
IMPL_RTE_AMPLITUDE_CLIP = 10.0
IMPL_FFT_NODATA_FILL = "valid_mean"
IMPL_FFT_PADDING = "none"
IMPL_GAUSSIAN_RESPONSE = "low_pass"
IMPL_FHD_DEFINITION = "total_horizontal_gradient"
IMPL_COLLISION_POLICY = "mean_of_observations"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_array(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def default_publication_params() -> dict[str, Any]:
    return dict(ABEOKUTA_PUBLICATION_MAGNETIC_PARAMS)


def merge_magnetic_params(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    params = default_publication_params()
    if overrides:
        for key, value in overrides.items():
            if value is None:
                continue
            if key in {
                "inclination_deg",
                "declination_deg",
                "average_igrf_nT",
                "gaussian_central_wavelength_m",
                "gaussian_std",
                "rte_amplitude_clip",
                "gaussian_mode",
            }:
                if key == "gaussian_mode":
                    params[key] = str(value)
                else:
                    params[key] = float(value)
    return params


def estimate_grid_spacing_m(xs: np.ndarray, ys: np.ndarray) -> dict[str, Any]:
    """Estimate survey spacing from unique projected coordinates (metres)."""
    ux = np.unique(np.round(xs, 6))
    uy = np.unique(np.round(ys, 6))
    gaps_x = np.diff(np.sort(ux)) if ux.size > 1 else np.array([])
    gaps_y = np.diff(np.sort(uy)) if uy.size > 1 else np.array([])
    dx = float(np.median(gaps_x)) if gaps_x.size else None
    dy = float(np.median(gaps_y)) if gaps_y.size else None
    return {
        "dx_m": dx,
        "dy_m": dy,
        "unique_x": int(ux.size),
        "unique_y": int(uy.size),
        "regularity_ratio_x": (
            float(np.mean(np.isclose(gaps_x, dx, rtol=0, atol=max(abs(dx or 0) * 0.05, 1e-6))))
            if gaps_x.size and dx
            else None
        ),
        "regularity_ratio_y": (
            float(np.mean(np.isclose(gaps_y, dy, rtol=0, atol=max(abs(dy or 0) * 0.05, 1e-6))))
            if gaps_y.size and dy
            else None
        ),
    }


def source_lattice_reconciliation(
    xs_src: np.ndarray,
    ys_src: np.ndarray,
    *,
    spacing: float = 100.0,
) -> dict[str, Any]:
    """Reconcile inspect-style source lattice gaps (EPSG:32632 file XY)."""
    ux = np.unique(np.round(xs_src, 8))
    uy = np.unique(np.round(ys_src, 8))
    expected = int(ux.size * uy.size)
    observed_xy = len({(round(float(x), 8), round(float(y), 8)) for x, y in zip(xs_src, ys_src)})
    missing = expected - observed_xy
    return {
        "frame": "source_file_xy",
        "spacing": spacing,
        "unique_x": int(ux.size),
        "unique_y": int(uy.size),
        "expected_lattice_cells": expected,
        "observed_unique_xy": observed_xy,
        "empty_lattice_positions": missing,
        "original_observation_count": int(xs_src.size),
        "note": (
            "Source-CRS lattice count matches inspect.missing_lattice_cells when "
            "unique_x×unique_y − unique_xy. This is independent of processing-CRS scatter-bin NoData."
        ),
    }


def grid_points_to_array(
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    *,
    resolution: float | None = None,
    nodata: float = -9999.0,
    method: str = "scatter_bin",
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Grid points onto a regular array in projected metres.

    ``scatter_bin`` (default for Abeokuta processing CRS):
      - Cells receiving ≥1 observation are filled with the mean of those values.
      - Empty cells remain NoData — never fabricated as measured TMI.
      - Collision mean is an aggregation of observations, not spatial interpolation.

    ``nearest``:
      - Explicit KD-tree fill of every cell (interpolated); documented separately.
    """
    spacing = estimate_grid_spacing_m(xs, ys)
    dx = float(resolution or spacing["dx_m"] or 100.0)
    dy = float(resolution or spacing["dy_m"] or dx)
    if dx <= 0 or dy <= 0:
        raise ValueError("Grid spacing must be positive.")

    xmin, xmax = float(np.min(xs)), float(np.max(xs))
    ymin, ymax = float(np.min(ys)), float(np.max(ys))
    width = max(2, int(math.floor((xmax - xmin) / dx + 0.5)) + 1)
    height = max(2, int(math.floor((ymax - ymin) / dy + 0.5)) + 1)
    if width * height > 4_000_000:
        raise ValueError(f"Grid {width}×{height} exceeds safety limit.")

    expected_cells = width * height
    grid = np.full((height, width), nodata, dtype=np.float64)
    count = np.zeros((height, width), dtype=np.int32)
    sum_z = np.zeros((height, width), dtype=np.float64)

    cols = np.clip(np.rint((xs - xmin) / dx).astype(np.int64), 0, width - 1)
    rows = np.clip(np.rint((ymax - ys) / dy).astype(np.int64), 0, height - 1)

    if method in {"lattice", "bin", "scatter_bin"}:
        for r, c, v in zip(rows, cols, zs):
            ri, ci = int(r), int(c)
            sum_z[ri, ci] += float(v)
            count[ri, ci] += 1
        occupied = count > 0
        grid[occupied] = sum_z[occupied] / count[occupied]
        used_method = "scatter_bin_mean_nodata_gaps"
        cells_from_observation = int(np.count_nonzero(occupied))
        cells_interpolated = 0
        collision_cells = int(np.count_nonzero(count > 1))
        collision_policy = IMPL_COLLISION_POLICY
        interpolation_method = None
    elif method == "nearest":
        from scipy.spatial import cKDTree

        pts = np.column_stack([xs, ys])
        tree = cKDTree(pts)
        cols_i, rows_i = np.meshgrid(np.arange(width), np.arange(height))
        cx = xmin + cols_i.ravel() * dx
        cy = ymax - rows_i.ravel() * dy
        _, nn = tree.query(np.column_stack([cx, cy]), k=1)
        grid[:, :] = zs[nn].astype(np.float64).reshape(height, width)
        # Mark cells that coincide with an observation bin as observational
        for r, c in zip(rows, cols):
            count[int(r), int(c)] += 1
        occupied = count > 0
        used_method = "nearest_neighbour_kdtree"
        cells_from_observation = int(np.count_nonzero(occupied))
        cells_interpolated = int(expected_cells - cells_from_observation)
        collision_cells = int(np.count_nonzero(count > 1))
        collision_policy = None
        interpolation_method = {
            "name": "nearest_neighbour_kdtree",
            "search": "k=1",
            "note": "Every cell receives a value; empty lattice positions are interpolated, not measured.",
        }
    else:
        raise ValueError(f"Unknown gridding method '{method}'")

    mask = grid != nodata
    nodata_cells = int(np.count_nonzero(~mask))
    provenance = {
        "method": used_method,
        "original_observation_count": int(xs.size),
        "expected_lattice_cells": expected_cells,
        "observed_lattice_cell_count": cells_from_observation,
        "empty_lattice_positions": nodata_cells if method != "nearest" else int(
            expected_cells - cells_from_observation
        ),
        "cells_populated_by_direct_observations": cells_from_observation,
        "cells_populated_by_interpolation": cells_interpolated,
        "cells_remaining_nodata": nodata_cells,
        "collision_cells_mean_aggregated": collision_cells,
        "collision_policy": collision_policy,
        "interpolation_method": interpolation_method,
        "interpolation_assumptions": (
            "scatter_bin: only cells with ≥1 reprojected observation are filled "
            "(mean if multiple). Empty cells stay NoData — not measured TMI. "
            "UTM 32N→31N warps the source lattice, so processing-CRS NoData ≠ "
            "source-CRS missing_lattice_cells."
            if method != "nearest"
            else "nearest: all cells filled; interpolated cells are not observations."
        ),
        "resolution_x_m": dx,
        "resolution_y_m": dy,
        "width": width,
        "height": height,
        "xmin": xmin,
        "xmax": xmin + (width - 1) * dx,
        "ymin": ymax - (height - 1) * dy,
        "ymax": ymax,
        "origin": {"xmin": xmin, "ymax": ymax, "convention": "northwest_cell_center_approx_via_from_origin"},
        "nodata": nodata,
        "point_count": int(xs.size),
        "filled_cells": int(np.count_nonzero(mask)),
        "nodata_cells": nodata_cells,
        "spacing_estimate": spacing,
        "fft_regularity_ok": bool(
            (spacing.get("regularity_ratio_x") or 0) >= 0.85
            and (spacing.get("regularity_ratio_y") or 0) >= 0.85
        ),
        "resampling_error_metrics": {
            "status": "not_applicable_for_scatter_bin"
            if method != "nearest"
            else "nearest_assigns_existing_observation_value_no_rmse_vs_truth",
            "note": "No independent ground-truth grid; collision mean differs from last-write-wins.",
        },
    }
    return grid.astype(np.float32), mask, provenance


def _prepare_fft(
    grid: np.ndarray, mask: np.ndarray, nodata: float
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Prepare array for FFT: fill NoData with valid mean (documented)."""
    work = grid.astype(np.float64).copy()
    valid = mask & np.isfinite(work) & (work != nodata)
    if not np.any(valid):
        raise ValueError("Grid has no valid cells for magnetic filtering.")
    fill = float(np.mean(work[valid]))
    n_filled = int(np.count_nonzero(~valid))
    work[~valid] = fill
    prep = {
        "nodata_fill": IMPL_FFT_NODATA_FILL,
        "nodata_fill_value": fill,
        "nodata_cells_filled_for_fft": n_filled,
        "fft_padding": IMPL_FFT_PADDING,
        "windowing": "none",
        "detrend": "none_in_prepare",
        "implementation_choice": True,
        "note": (
            "NoData cells are temporarily replaced with the mean of valid cells for FFT "
            "stability, then masked back to NoData in the output. This is an implementation "
            "choice, not a publication parameter. No zero-padding is applied."
        ),
    }
    return work, valid, prep


def _wavenumbers(ny: int, nx: int, dy: float, dx: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Angular wavenumbers (rad/m): kx = 2π · fftfreq(n, d=dx)."""
    kx = np.fft.fftfreq(nx, d=dx) * 2.0 * np.pi
    ky = np.fft.fftfreq(ny, d=dy) * 2.0 * np.pi
    KX, KY = np.meshgrid(kx, ky)
    K = np.sqrt(KX**2 + KY**2)
    return KX, KY, K


def reduction_to_equator(
    grid: np.ndarray,
    mask: np.ndarray,
    *,
    dx: float,
    dy: float,
    inclination_deg: float,
    declination_deg: float,
    nodata: float = -9999.0,
    amplitude_clip: float | None = IMPL_RTE_AMPLITUDE_CLIP,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Frequency-domain Reduction to Magnetic Equator (Blakely-style).

    Transfer function (induced M ∥ F):
      F(k) = [θ_eq(k)]² / [θ_obs(k)]²
      θ(k) = i·kx·fx + i·ky·fy + |k|·fz

    Target: I=0° (equator), declination unchanged.
    Amplitude clipping is an **implementation stabilisation**, not a publication parameter.
    """
    work, valid, prep = _prepare_fft(grid, mask, nodata)
    ny, nx = work.shape
    KX, KY, K = _wavenumbers(ny, nx, dy, dx)
    I = math.radians(inclination_deg)
    D = math.radians(declination_deg)
    fx = np.cos(I) * np.cos(D)
    fy = np.cos(I) * np.sin(D)
    fz = np.sin(I)
    fx_e = math.cos(0.0) * math.cos(D)
    fy_e = math.cos(0.0) * math.sin(D)
    fz_e = 0.0

    with np.errstate(divide="ignore", invalid="ignore"):
        obs = (1j * KX * fx + 1j * KY * fy + K * fz) ** 2
        equ = (1j * KX * fx_e + 1j * KY * fy_e + K * fz_e) ** 2
        denom = np.where(np.abs(obs) < 1e-10, 1e-10 + 0j, obs)
        filt = equ / denom
        filt[0, 0] = 1.0 + 0j
        mag = np.abs(filt)
        n_clipped = 0
        clip_limit = None if amplitude_clip is None or amplitude_clip <= 0 else float(amplitude_clip)
        if clip_limit is not None:
            too = mag > clip_limit
            n_clipped = int(np.count_nonzero(too))
            filt_clipped = filt.copy()
            filt_clipped[too] = filt_clipped[too] * (clip_limit / mag[too])
        else:
            filt_clipped = filt

    spec = np.fft.fft2(work)
    out_clipped = np.real(np.fft.ifft2(spec * filt_clipped)).astype(np.float64)
    out_raw = np.real(np.fft.ifft2(spec * filt)).astype(np.float64)

    result = np.full(grid.shape, nodata, dtype=np.float32)
    result[valid] = out_clipped[valid].astype(np.float32)

    # Compare clipped vs unclipped on valid cells
    v_clip = out_clipped[valid]
    v_raw = out_raw[valid]
    diff = v_clip - v_raw
    comparison = {
        "clip_applied": clip_limit is not None,
        "amplitude_clip_limit": clip_limit,
        "coefficients_clipped": n_clipped,
        "coefficients_total": int(filt.size),
        "fraction_clipped": float(n_clipped / filt.size) if filt.size else 0.0,
        "valid_cell_rmse_clipped_vs_unclipped": float(np.sqrt(np.mean(diff**2))),
        "valid_cell_max_abs_diff": float(np.max(np.abs(diff))) if diff.size else 0.0,
        "unclipped_valid_min": float(np.min(v_raw)),
        "unclipped_valid_max": float(np.max(v_raw)),
        "clipped_valid_min": float(np.min(v_clip)),
        "clipped_valid_max": float(np.max(v_clip)),
        "publication_parameter": False,
        "implementation_choice": True,
        "necessity_note": (
            "Near-equatorial RTE denominators can amplify noise; a finite amplitude "
            "cap is a numerical stabilisation. It is not reported in the Abeokuta "
            "publication and must not be treated as a paper parameter."
        ),
    }

    meta = {
        "operation": OPERATION_RTE,
        "inclination_deg": inclination_deg,
        "declination_deg": declination_deg,
        "target_inclination_deg": 0.0,
        "declination_convention": "degrees_east_of_north_unchanged_at_equator",
        "transfer_function": "F=(θ_eq)^2/(θ_obs)^2; θ=i*kx*fx+i*ky*fy+|k|*fz",
        "wavenumber_convention": "angular_rad_per_metre_fftfreq_times_2pi",
        "dc_component": "filter[0,0]=1 (passthrough)",
        "assumptions": [
            "Induced magnetization parallel to ambient field.",
            "2D Fourier-domain directional filter (Blakely-style).",
            "Target inclination 0° (magnetic equator), declination unchanged.",
        ],
        "publication_parameters": {
            "inclination_deg": inclination_deg,
            "declination_deg": declination_deg,
        },
        "implementation_choices": {
            "amplitude_clip": comparison,
            "fft_preparation": prep,
        },
        "dx_m": dx,
        "dy_m": dy,
        "units": "nT_equivalent_transformed",
        "scientific_validation_status": "NOT_VALIDATED",
    }
    return result, meta


def gaussian_filter_grid(
    grid: np.ndarray,
    mask: np.ndarray,
    *,
    dx: float,
    dy: float,
    wavelength_m: float,
    sigma: float,
    nodata: float = -9999.0,
    mode: str = "low_pass",
) -> tuple[np.ndarray, dict[str, Any]]:
    """Frequency-domain Gaussian filter.

    Publication cites central wavelength 2000 m and σ=0.5 without stating
    low-pass vs high-pass. Default ``low_pass``::

        H(k) = exp(-0.5 * ((|k|/k_c)/σ)^2),  k_c = 2π/λ

    ``high_pass`` returns residual T − low_pass(T).
    ``band`` is not implemented without further publication detail.
    """
    work, valid, prep = _prepare_fft(grid, mask, nodata)
    ny, nx = work.shape
    _, _, K = _wavenumbers(ny, nx, dy, dx)
    if wavelength_m <= 0:
        raise ValueError("gaussian wavelength must be positive")
    k_c = 2.0 * math.pi / float(wavelength_m)
    sig = max(float(sigma), 1e-6)
    H_lp = np.exp(-0.5 * ((K / max(k_c, 1e-12)) / sig) ** 2)
    H_lp[0, 0] = 1.0
    mode_l = (mode or "low_pass").strip().lower()
    if mode_l in {"high_pass", "residual", "highpass"}:
        H = 1.0 - H_lp
        H[0, 0] = 0.0
        response = "high_pass_residual"
        formula = "H_hp = 1 - exp(-0.5*((|k|/k_c)/σ)^2)"
    else:
        H = H_lp
        response = "low_pass"
        formula = "H_lp = exp(-0.5*((|k|/k_c)/σ)^2), k_c=2π/λ"

    out = np.real(np.fft.ifft2(np.fft.fft2(work) * H)).astype(np.float32)
    result = np.full_like(out, nodata)
    result[valid] = out[valid]
    # Frequency response samples for documentation
    k_samp = np.array([0.0, 0.25, 0.5, 1.0, 2.0, 4.0]) * k_c
    h_samp = np.exp(-0.5 * ((k_samp / max(k_c, 1e-12)) / sig) ** 2)
    meta = {
        "operation": OPERATION_GAUSSIAN,
        "gaussian_central_wavelength_m": wavelength_m,
        "gaussian_std": sigma,
        "response_type": response,
        "formula": formula,
        "cutoff_definition": "k_c = 2π / λ_central; σ dimensionless scale on |k|/k_c",
        "wavenumber_convention": "angular_rad_per_metre",
        "spatial_sampling_m": {"dx": dx, "dy": dy},
        "publication_parameters": {
            "gaussian_central_wavelength_m": wavelength_m,
            "gaussian_std": sigma,
        },
        "implementation_choices": {
            "default_response": IMPL_GAUSSIAN_RESPONSE,
            "selected_mode": mode_l,
            "ambiguity_note": (
                "Publication lists central wavelength and σ but does not unambiguously "
                "state low-pass vs residual/high-pass. Default is low-pass; high_pass "
                "mode available for comparison. Exact reproduction not claimed."
            ),
            "fft_preparation": prep,
            "low_pass_response_samples": {
                "k_over_kc": [0.0, 0.25, 0.5, 1.0, 2.0, 4.0],
                "H_lp": [float(x) for x in h_samp],
            },
        },
        "dx_m": dx,
        "dy_m": dy,
        "units": "nT",
        "scientific_validation_status": "NOT_VALIDATED",
    }
    return result, meta


def _horizontal_derivatives(
    grid: np.ndarray, mask: np.ndarray, *, dx: float, dy: float, nodata: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    work, valid, prep = _prepare_fft(grid, mask, nodata)
    ny, nx = work.shape
    KX, KY, _ = _wavenumbers(ny, nx, dy, dx)
    spec = np.fft.fft2(work)
    # ∂/∂x ↔ i·kx ; image row increase is −y in map space, but KY from fftfreq(dy)
    # with north-up grid (row 0 = north) already uses ymax-origin sampling.
    dx_g = np.real(np.fft.ifft2(spec * (1j * KX))).astype(np.float32)
    dy_g = np.real(np.fft.ifft2(spec * (1j * KY))).astype(np.float32)
    return dx_g, dy_g, valid, prep


def first_horizontal_derivative(
    grid: np.ndarray,
    mask: np.ndarray,
    *,
    dx: float,
    dy: float,
    nodata: float = -9999.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Total horizontal gradient THG = sqrt((∂T/∂x)² + (∂T/∂y)²).

    Named ``first_horizontal_derivative`` in the UI for publication parity; the
    stored product is THG (common aeromagnetic horizontal derivative product),
    not a single-axis ∂T/∂x. Units: nT/m.
    """
    dx_g, dy_g, valid, prep = _horizontal_derivatives(grid, mask, dx=dx, dy=dy, nodata=nodata)
    thg = np.sqrt(dx_g.astype(np.float64) ** 2 + dy_g.astype(np.float64) ** 2).astype(np.float32)
    result = np.full_like(thg, nodata)
    result[valid] = thg[valid]
    return result, {
        "operation": OPERATION_FHD,
        "definition": "THG = sqrt((dT/dx)^2 + (dT/dy)^2)",
        "product_name": "total_horizontal_gradient",
        "sign_convention": "magnitude_nonnegative",
        "units": "nT_per_m",
        "fourier_operators": "dT/dx ↔ i*kx, dT/dy ↔ i*ky",
        "implementation_choices": {
            "definition": IMPL_FHD_DEFINITION,
            "note": "Not single-axis ∂T/∂x; THG is the conventional horizontal derivative amplitude.",
            "fft_preparation": prep,
        },
        "dx_m": dx,
        "dy_m": dy,
        "scientific_validation_status": "NOT_VALIDATED",
    }


def first_vertical_derivative(
    grid: np.ndarray,
    mask: np.ndarray,
    *,
    dx: float,
    dy: float,
    nodata: float = -9999.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """First vertical derivative: ∂T/∂z ≈ IFFT(|k| · FFT(T)). Units: nT/m."""
    work, valid, prep = _prepare_fft(grid, mask, nodata)
    ny, nx = work.shape
    _, _, K = _wavenumbers(ny, nx, dy, dx)
    out = np.real(np.fft.ifft2(np.fft.fft2(work) * K)).astype(np.float32)
    result = np.full_like(out, nodata)
    result[valid] = out[valid]
    return result, {
        "operation": OPERATION_FVD,
        "definition": "dT/dz ≈ IFFT(|k| · FFT(T))",
        "units": "nT_per_m",
        "sign_convention": "positive_upward_continuation_of_short_wavelengths_enhancement",
        "fourier_operator": "|k| = sqrt(kx^2+ky^2), kx=2π*fftfreq",
        "implementation_choices": {"fft_preparation": prep},
        "dx_m": dx,
        "dy_m": dy,
        "scientific_validation_status": "NOT_VALIDATED",
    }


def analytic_signal(
    grid: np.ndarray,
    mask: np.ndarray,
    *,
    dx: float,
    dy: float,
    nodata: float = -9999.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """3D analytic-signal amplitude (Nabighian / Roest-style).

    AS = sqrt((∂T/∂x)² + (∂T/∂y)² + (∂T/∂z)²)

    The vertical term uses the Fourier |k| operator for ∂T/∂z on a 2D grid
    (potential-field approximation). Units: nT/m.
    """
    dx_g, dy_g, valid, prep = _horizontal_derivatives(grid, mask, dx=dx, dy=dy, nodata=nodata)
    work, _, prep2 = _prepare_fft(grid, mask, nodata)
    ny, nx = work.shape
    _, _, K = _wavenumbers(ny, nx, dy, dx)
    dz = np.real(np.fft.ifft2(np.fft.fft2(work) * K)).astype(np.float32)
    ams = np.sqrt(
        dx_g.astype(np.float64) ** 2 + dy_g.astype(np.float64) ** 2 + dz.astype(np.float64) ** 2
    ).astype(np.float32)
    result = np.full_like(ams, nodata)
    result[valid] = ams[valid]
    return result, {
        "operation": OPERATION_ANALYTIC_SIGNAL,
        "definition": "AS = sqrt((dT/dx)^2 + (dT/dy)^2 + (dT/dz)^2)",
        "vertical_term_interpretation": (
            "dT/dz approximated by Fourier multiplication with |k| on a 2D total-field grid "
            "(standard potential-field AS amplitude)."
        ),
        "units": "nT_per_m",
        "implementation_choices": {"fft_preparation": prep, "fft_preparation_vertical": prep2},
        "dx_m": dx,
        "dy_m": dy,
        "scientific_validation_status": "NOT_VALIDATED",
    }


def tilt_derivative(
    grid: np.ndarray,
    mask: np.ndarray,
    *,
    dx: float,
    dy: float,
    nodata: float = -9999.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Tilt derivative TDR = atan2(∂T/∂z, THG). Units: radians ∈ [-π/2, π/2]."""
    dx_g, dy_g, valid, prep = _horizontal_derivatives(grid, mask, dx=dx, dy=dy, nodata=nodata)
    work, valid, prep2 = _prepare_fft(grid, mask, nodata)
    ny, nx = work.shape
    _, _, K = _wavenumbers(ny, nx, dy, dx)
    dz = np.real(np.fft.ifft2(np.fft.fft2(work) * K)).astype(np.float64)
    thg = np.sqrt(dx_g.astype(np.float64) ** 2 + dy_g.astype(np.float64) ** 2)
    # atan2(y,x) with y=dT/dz, x=THG≥0 → stable when THG→0 (returns ±π/2)
    tilt = np.arctan2(dz, thg).astype(np.float32)
    result = np.full_like(tilt, nodata)
    result[valid] = tilt[valid]
    zero_thg = int(np.count_nonzero((thg[valid] == 0) | ~np.isfinite(thg[valid])))
    return result, {
        "operation": OPERATION_TILT,
        "definition": "TDR = atan2(dT/dz, THG)",
        "units": "radians",
        "range": "[-pi/2, pi/2]",
        "zero_horizontal_gradient_handling": (
            "atan2(dT/dz, 0) → ±π/2; no epsilon floor required for atan2"
        ),
        "zero_thg_valid_cells": zero_thg,
        "implementation_choices": {"fft_preparation": prep, "fft_preparation_vertical": prep2},
        "dx_m": dx,
        "dy_m": dy,
        "scientific_validation_status": "NOT_VALIDATED",
    }


def radially_averaged_power_spectrum(
    grid: np.ndarray,
    mask: np.ndarray,
    *,
    dx: float,
    dy: float,
    nodata: float = -9999.0,
    n_bins: int = 64,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Radially averaged 2D power spectrum.

    - Angular wavenumber k [rad/m]; also cycles/m = k/(2π); wavelength λ=2π/k.
    - DC excluded from annular averages.
    - Mean removed before FFT (simple detrend).
    - No Hann window (documented); no source-depth claim without explicit slope fit.
    """
    work, valid, prep = _prepare_fft(grid, mask, nodata)
    # Detrend: remove mean of work (already mean-filled nodata)
    work = work - float(np.mean(work))
    ny, nx = work.shape
    _, _, K = _wavenumbers(ny, nx, dy, dx)
    spec = np.fft.fft2(work)
    # Normalise by cell count for comparable power density
    power = (np.abs(spec) ** 2) / float(nx * ny)
    k_flat = K.ravel()
    p_flat = power.ravel()
    sel = k_flat > 0
    k_flat = k_flat[sel]
    p_flat = p_flat[sel]
    if k_flat.size == 0:
        raise ValueError("No wavenumbers available for power spectrum.")
    k_max = float(np.max(k_flat))
    bins = np.linspace(0.0, k_max, n_bins + 1)
    centers = 0.5 * (bins[:-1] + bins[1:])
    sums = np.zeros(n_bins, dtype=np.float64)
    counts = np.zeros(n_bins, dtype=np.int64)
    inds = np.digitize(k_flat, bins) - 1
    for i, pval in zip(inds, p_flat):
        if 0 <= i < n_bins:
            sums[i] += pval
            counts[i] += 1
    mean_p = np.full(n_bins, np.nan, dtype=np.float64)
    nonempty = counts > 0
    mean_p[nonempty] = sums[nonempty] / counts[nonempty]
    with np.errstate(divide="ignore", invalid="ignore"):
        log_p = np.where(mean_p > 0, np.log10(mean_p), np.nan)
    cycles = centers / (2.0 * math.pi)
    wavelength_m = np.where(centers > 0, 2.0 * math.pi / centers, np.nan)
    payload = {
        "wavenumber_rad_per_m": centers.tolist(),
        "wavenumber_cycles_per_m": cycles.tolist(),
        "wavelength_m": [
            None if (isinstance(v, float) and math.isnan(v)) else float(v) for v in wavelength_m
        ],
        "mean_power": [
            None if (isinstance(v, float) and math.isnan(v)) else float(v) for v in mean_p
        ],
        "log10_power": [
            None if (isinstance(v, float) and math.isnan(v)) else float(v) for v in log_p
        ],
        "bin_counts": counts.tolist(),
        "n_bins": n_bins,
        "power_normalisation": "abs(FFT)^2 / (nx*ny)",
        "dc_excluded": True,
        "depth_interpretation": {
            "claimed": False,
            "note": (
                "No source-depth estimate is derived. Spector–Grant or similar slope "
                "fitting would require an explicit method, wavenumber band, and assumptions."
            ),
        },
    }
    meta = {
        "operation": OPERATION_RAPS,
        "definition": "Radial average of |FFT(T)|^2/(nx*ny) over annular |k| bins",
        "wavenumber_convention": "angular_rad_per_m; cycles_per_m = k/(2π); λ=2π/k",
        "detrend": "remove_global_mean",
        "windowing": "none",
        "implementation_choices": {
            "fft_preparation": prep,
            "annular_bins": "linear_in_|k|_from_0_to_kmax",
            "dc_treatment": "excluded_from_radial_average",
        },
        "dx_m": dx,
        "dy_m": dy,
        "n_bins": n_bins,
        "scientific_validation_status": "NOT_VALIDATED",
    }
    return payload, meta


def write_geotiff(
    path: Path,
    grid: np.ndarray,
    meta: dict[str, Any],
    *,
    crs: str,
    nodata: float,
    tags: dict[str, str] | None = None,
) -> None:
    import rasterio
    from rasterio.transform import from_origin

    path.parent.mkdir(parents=True, exist_ok=True)
    dx = float(meta.get("resolution_x_m") or meta.get("dx_m") or meta["resolution"])
    dy = float(meta.get("resolution_y_m") or meta.get("dy_m") or dx)
    transform = from_origin(float(meta["xmin"]), float(meta["ymax"]), dx, dy)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=grid.shape[0],
        width=grid.shape[1],
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(np.asarray(grid, dtype=np.float32), 1)
        base_tags = {
            "MEASUREMENT": MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
            "SOFTWARE": SOFTWARE_ID,
            "SOFTWARE_VERSION": SOFTWARE_VERSION,
        }
        if tags:
            base_tags.update({k: str(v) for k, v in tags.items()})
        dst.update_tags(**base_tags)


def write_preview_png(
    path: Path,
    grid: np.ndarray,
    mask: np.ndarray,
    *,
    title: str,
    cmap: str = "RdBu_r",
    units: str | None = None,
) -> dict[str, Any]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.ma.array(grid, mask=~mask)
    fig, ax = plt.subplots(figsize=(6, 5), dpi=120)
    im = ax.imshow(data, cmap=cmap, origin="upper", aspect="equal")
    ax.set_title(title, fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    if units:
        cbar.set_label(units, fontsize=7)
    cbar.ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return grid_stats(grid, mask)


def write_raps_chart_png(path: Path, payload: dict[str, Any]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    waves = payload.get("wavelength_m") or []
    logp = payload.get("log10_power") or []
    xs: list[float] = []
    ys: list[float] = []
    for w, lp in zip(waves, logp):
        if w is None or lp is None:
            continue
        if float(w) <= 0:
            continue
        xs.append(float(w))
        ys.append(float(lp))
    fig, ax = plt.subplots(figsize=(6.5, 4.2), dpi=120)
    if xs:
        ax.plot(xs, ys, color="#1f4e5f", linewidth=1.4)
        ax.set_xscale("log")
    ax.set_xlabel("Wavelength (m)")
    ax.set_ylabel("log10(power)")
    ax.set_title("Radially averaged power spectrum (no depth claim)")
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def grid_stats(grid: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    valid = grid[mask]
    if valid.size == 0:
        return {"count": 0, "min": None, "max": None, "mean": None, "stdev": None}
    return {
        "count": int(valid.size),
        "min": float(np.min(valid)),
        "max": float(np.max(valid)),
        "mean": float(np.mean(valid)),
        "stdev": float(np.std(valid)),
        "p01": float(np.percentile(valid, 1)),
        "p50": float(np.percentile(valid, 50)),
        "p99": float(np.percentile(valid, 99)),
    }


def build_operation_provenance(
    *,
    operation: str,
    op_meta: dict[str, Any],
    params: dict[str, Any],
    input_artifact: str,
    input_checksum: str | None,
    output_artifacts: dict[str, str | None],
    output_checksums: dict[str, str | None],
    source_crs: str | None,
    processing_crs: str | None,
    grid_spacing: dict[str, float],
    nodata_policy: dict[str, Any],
    statistics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pub_keys = {
        "inclination_deg",
        "declination_deg",
        "average_igrf_nT",
        "gaussian_central_wavelength_m",
        "gaussian_std",
    }
    publication_params = {k: params.get(k) for k in pub_keys if k in params}
    impl = dict(op_meta.get("implementation_choices") or {})
    if "rte_amplitude_clip" in params:
        impl["rte_amplitude_clip_requested"] = params.get("rte_amplitude_clip")
    return {
        "operation": operation,
        "at": _utc_now(),
        "algorithm": SOFTWARE_ID,
        "software_version": SOFTWARE_VERSION,
        "input_artifact": input_artifact,
        "input_checksum_sha256": input_checksum,
        "output_artifacts": output_artifacts,
        "output_checksums_sha256": output_checksums,
        "source_crs": source_crs,
        "processing_crs": processing_crs,
        "grid_spacing_m": grid_spacing,
        "nodata_interpolation_policy": nodata_policy,
        "publication_parameters": publication_params,
        "implementation_choices": impl,
        "op_meta": op_meta,
        "statistics": statistics,
        "scientific_validation_status": "NOT_VALIDATED",
        "not_hazard_labels": True,
    }


def run_magnetic_operation(
    operation: str,
    grid: np.ndarray,
    mask: np.ndarray,
    *,
    dx: float,
    dy: float,
    params: dict[str, Any],
    nodata: float = -9999.0,
) -> tuple[np.ndarray | dict[str, Any], dict[str, Any]]:
    op = (operation or "").strip().lower()
    if op not in SUPPORTED_OPERATIONS:
        raise ValueError(
            f"Unsupported magnetic operation '{operation}'. "
            f"Supported: {', '.join(SUPPORTED_OPERATIONS)}"
        )
    if not mask.any():
        raise ValueError("No valid cells for magnetic processing.")
    if op != OPERATION_TMI and (dx <= 0 or dy <= 0):
        raise ValueError("FFT-based filters require positive metric grid spacing.")

    if op == OPERATION_TMI:
        return grid.copy(), {
            "operation": OPERATION_TMI,
            "definition": "Total Magnetic Intensity grid (no transform)",
            "units": "nT",
            "dx_m": dx,
            "dy_m": dy,
            "scientific_validation_status": "NOT_VALIDATED",
        }
    if op == OPERATION_RTE:
        clip = params.get("rte_amplitude_clip", IMPL_RTE_AMPLITUDE_CLIP)
        return reduction_to_equator(
            grid,
            mask,
            dx=dx,
            dy=dy,
            inclination_deg=float(params["inclination_deg"]),
            declination_deg=float(params["declination_deg"]),
            nodata=nodata,
            amplitude_clip=None if clip in (None, "", "none") else float(clip),
        )
    if op == OPERATION_GAUSSIAN:
        return gaussian_filter_grid(
            grid,
            mask,
            dx=dx,
            dy=dy,
            wavelength_m=float(params["gaussian_central_wavelength_m"]),
            sigma=float(params["gaussian_std"]),
            nodata=nodata,
            mode=str(params.get("gaussian_mode") or "low_pass"),
        )
    if op == OPERATION_ANALYTIC_SIGNAL:
        return analytic_signal(grid, mask, dx=dx, dy=dy, nodata=nodata)
    if op == OPERATION_FVD:
        return first_vertical_derivative(grid, mask, dx=dx, dy=dy, nodata=nodata)
    if op == OPERATION_FHD:
        return first_horizontal_derivative(grid, mask, dx=dx, dy=dy, nodata=nodata)
    if op == OPERATION_TILT:
        return tilt_derivative(grid, mask, dx=dx, dy=dy, nodata=nodata)
    if op == OPERATION_RAPS:
        return radially_averaged_power_spectrum(grid, mask, dx=dx, dy=dy, nodata=nodata)
    raise ValueError(f"Unhandled operation {op}")


def publication_comparison_notes() -> dict[str, Any]:
    return {
        "status": "NOT_VALIDATED",
        "exact_map_reproduction": False,
        "note": (
            "Compare generated maps and statistics against the publication qualitatively. "
            "Do not claim exact reproduction without original processed grids or "
            "sufficiently detailed reference figures."
        ),
        "published_interpretation_themes": [
            "Low magnetic zones associated with sedimentary formations",
            "Intermediate magnetic zones associated with transition geology",
            "High magnetic zones associated with basement complex",
            "Predominantly NE-SW structural trends",
        ],
        "not_ground_truth_labels": True,
        "not_hazard_labels": True,
    }


def operation_catalog() -> list[dict[str, Any]]:
    """UI-facing descriptions for each operation."""
    return [
        {
            "operation": OPERATION_TMI,
            "title": "Total Magnetic Intensity",
            "summary": "Gridded TMI observations (nT). No magnetic transform.",
            "units": "nT",
        },
        {
            "operation": OPERATION_RTE,
            "title": "Reduction to Magnetic Equator",
            "summary": (
                "Fourier-domain RTE to I=0° using publication inclination/declination. "
                "Amplitude clipping is an implementation stabilisation, not a paper parameter."
            ),
            "units": "nT (transformed)",
        },
        {
            "operation": OPERATION_GAUSSIAN,
            "title": "Gaussian filter",
            "summary": (
                "Frequency-domain Gaussian with λ=2000 m, σ=0.5. Default low-pass; "
                "publication response type is ambiguous."
            ),
            "units": "nT",
        },
        {
            "operation": OPERATION_ANALYTIC_SIGNAL,
            "title": "Analytic signal",
            "summary": "AS = sqrt((∂T/∂x)²+(∂T/∂y)²+(∂T/∂z)²) with Fourier |k| vertical term.",
            "units": "nT/m",
        },
        {
            "operation": OPERATION_FVD,
            "title": "First vertical derivative",
            "summary": "∂T/∂z ≈ IFFT(|k|·FFT(T)).",
            "units": "nT/m",
        },
        {
            "operation": OPERATION_FHD,
            "title": "First horizontal derivative (THG)",
            "summary": "Total horizontal gradient sqrt((∂T/∂x)²+(∂T/∂y)²).",
            "units": "nT/m",
        },
        {
            "operation": OPERATION_TILT,
            "title": "Tilt derivative",
            "summary": "atan2(∂T/∂z, THG); stable at zero horizontal gradient.",
            "units": "radians",
        },
        {
            "operation": OPERATION_RAPS,
            "title": "Radially averaged power spectrum",
            "summary": (
                "Annular average of normalised 2D power. No source-depth claim without "
                "explicit slope fitting."
            ),
            "units": "log10(power) vs wavelength",
        },
    ]


def append_processing_history(path: Path, entry: dict[str, Any]) -> list[dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    history: list[dict[str, Any]] = []
    if path.exists():
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []
    history.append(entry)
    path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return history
