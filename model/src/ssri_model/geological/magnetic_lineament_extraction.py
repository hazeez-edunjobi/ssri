"""Candidate magnetic lineament extraction from gridded aeromagnetic products.

Scientific boundary
-------------------
Outputs are **candidate magnetic lineaments** derived from edge-enhanced TMI
grids. They are NOT confirmed faults, fractures, or geological structures.
Publication-guided NE–SW themes remain contextual interpretation only.

Method (documented, testable)
-----------------------------
1. Prefer total horizontal gradient (first_horizontal_derivative); fallback
   analytic_signal when THG is unavailable.
2. Optional residual enhancement: |TMI − Gaussian low-pass| blended with THG
   when both residual and THG exist (edge emphasis on residual field).
3. Percentile threshold on valid enhancement cells (default P92).
4. Morphological cleaning (binary opening/closing) then skeletonisation.
5. Connected-component tracing into polylines; short segments discarded.
6. Orientation (0–180°) and length statistics; density/distance rasters via
   existing ``release_shell.lineaments.derive_lineament_rasters``.

Never injects channels into Stage 2.5 inference. Status stays NOT_VALIDATED.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from scipy import ndimage

from ssri_model.ml.constants import FEATURE_NODATA
from ssri_model.release_shell.lineaments import DEFAULT_WINDOW_M

SOFTWARE_ID = "ssri_model.geological.magnetic_lineament_extraction"
SOFTWARE_VERSION = "1.0.0"

DEFAULT_PERCENTILE = 92.0
DEFAULT_MIN_LENGTH_CELLS = 4
DEFAULT_MIN_COMPONENT_CELLS = 6
SCIENTIFIC_CLASS = "candidate_magnetic_lineament"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class ExtractionParams:
    percentile: float = DEFAULT_PERCENTILE
    min_length_cells: int = DEFAULT_MIN_LENGTH_CELLS
    min_component_cells: int = DEFAULT_MIN_COMPONENT_CELLS
    density_window_m: float = DEFAULT_WINDOW_M
    use_residual_blend: bool = True
    residual_weight: float = 0.35

    def to_dict(self) -> dict[str, Any]:
        return {
            "percentile": self.percentile,
            "min_length_cells": self.min_length_cells,
            "min_component_cells": self.min_component_cells,
            "density_window_m": self.density_window_m,
            "use_residual_blend": self.use_residual_blend,
            "residual_weight": self.residual_weight,
            "notes": (
                "Threshold = percentile of valid enhancement magnitudes. "
                "Skeletonised ridges traced to polylines. "
                "Outputs are candidate magnetic lineaments, not confirmed faults."
            ),
        }


def select_enhancement_grid(
    *,
    thg: np.ndarray | None,
    analytic: np.ndarray | None,
    tmi: np.ndarray | None,
    gaussian: np.ndarray | None,
    mask: np.ndarray,
    params: ExtractionParams,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Build a non-negative enhancement field for ridge detection."""
    sources: list[str] = []
    if thg is not None:
        base = np.abs(np.asarray(thg, dtype=np.float64))
        sources.append("first_horizontal_derivative")
    elif analytic is not None:
        base = np.abs(np.asarray(analytic, dtype=np.float64))
        sources.append("analytic_signal")
    else:
        raise ValueError(
            "Need first_horizontal_derivative or analytic_signal for lineament extraction."
        )

    enhancement = base.copy()
    residual_used = False
    if (
        params.use_residual_blend
        and tmi is not None
        and gaussian is not None
        and thg is not None
    ):
        residual = np.abs(
            np.asarray(tmi, dtype=np.float64) - np.asarray(gaussian, dtype=np.float64)
        )
        # Scale residual to THG magnitude scale before blending.
        thg_valid = base[mask]
        res_valid = residual[mask]
        if thg_valid.size and res_valid.size and np.nanmax(res_valid) > 0:
            scale = float(np.nanpercentile(thg_valid, 95) / max(np.nanpercentile(res_valid, 95), 1e-12))
            blended = (1.0 - params.residual_weight) * base + params.residual_weight * (
                residual * scale
            )
            enhancement = blended
            residual_used = True
            sources.append("tmi_minus_gaussian_residual_blend")

    enhancement = np.where(mask, enhancement, np.nan)
    meta = {
        "enhancement_sources": sources,
        "residual_blend_used": residual_used,
        "definition": (
            "Non-negative edge enhancement for candidate ridge extraction. "
            "THG preferred; optional residual blend emphasises residual anomalies."
        ),
    }
    return enhancement, meta


def threshold_ridges(
    enhancement: np.ndarray,
    mask: np.ndarray,
    *,
    percentile: float,
) -> tuple[np.ndarray, float]:
    valid = enhancement[mask & np.isfinite(enhancement)]
    if valid.size == 0:
        raise ValueError("No valid enhancement cells for thresholding.")
    thr = float(np.nanpercentile(valid, percentile))
    binary = mask & np.isfinite(enhancement) & (enhancement >= thr)
    return binary.astype(bool), thr


def skeletonize_binary(binary: np.ndarray) -> np.ndarray:
    """Thin binary ridges with morphological skeletonisation."""
    cleaned = ndimage.binary_opening(binary, structure=np.ones((3, 3), dtype=bool))
    cleaned = ndimage.binary_closing(cleaned, structure=np.ones((3, 3), dtype=bool))
    try:
        from skimage.morphology import skeletonize  # type: ignore

        return skeletonize(cleaned).astype(bool)
    except Exception:
        # Fallback: iterative morphological thinning without skimage.
        return _morphological_thinning(cleaned)


def _morphological_thinning(binary: np.ndarray, max_iter: int = 64) -> np.ndarray:
    """Zhang-Suen-like thinning using neighbourhood counts (numpy/scipy only)."""
    img = binary.astype(np.uint8)
    for _ in range(max_iter):
        changed = False
        for phase in (0, 1):
            neighbors = _neighbor_count(img)
            crossings = _crossing_number(img)
            # Candidate removal: boundary pixels with 2–6 neighbours.
            candidates = (
                (img == 1)
                & (neighbors >= 2)
                & (neighbors <= 6)
                & (crossings == 1)
            )
            if phase == 0:
                # south/east bias
                south = np.roll(img, -1, axis=0)
                east = np.roll(img, -1, axis=1)
                north = np.roll(img, 1, axis=0)
                west = np.roll(img, 1, axis=1)
                candidates &= (south * east * north == 0) | (east * west * south == 0)
            else:
                north = np.roll(img, 1, axis=0)
                west = np.roll(img, 1, axis=1)
                south = np.roll(img, -1, axis=0)
                east = np.roll(img, -1, axis=1)
                candidates &= (north * west * south == 0) | (west * east * north == 0)
            if not candidates.any():
                continue
            img = img.copy()
            img[candidates] = 0
            changed = True
        if not changed:
            break
    return img.astype(bool)


def _neighbor_count(img: np.ndarray) -> np.ndarray:
    kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], dtype=np.uint8)
    return ndimage.convolve(img.astype(np.uint8), kernel, mode="constant", cval=0)


def _crossing_number(img: np.ndarray) -> np.ndarray:
    """Approximate A(p) crossing count for thinning."""
    p2 = np.roll(img, 1, axis=0)
    p3 = np.roll(np.roll(img, 1, axis=0), -1, axis=1)
    p4 = np.roll(img, -1, axis=1)
    p5 = np.roll(np.roll(img, -1, axis=0), -1, axis=1)
    p6 = np.roll(img, -1, axis=0)
    p7 = np.roll(np.roll(img, -1, axis=0), 1, axis=1)
    p8 = np.roll(img, 1, axis=1)
    p9 = np.roll(np.roll(img, 1, axis=0), 1, axis=1)
    seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
    crossings = np.zeros(img.shape, dtype=np.int16)
    for a, b in zip(seq[:-1], seq[1:]):
        crossings += ((a == 0) & (b == 1)).astype(np.int16)
    return crossings


def _cell_centres(
    rows: Sequence[int],
    cols: Sequence[int],
    *,
    xmin: float,
    ymax: float,
    dx: float,
    dy: float,
) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for r, c in zip(rows, cols):
        x = xmin + (float(c) + 0.5) * dx
        y = ymax - (float(r) + 0.5) * dy
        pts.append((x, y))
    return pts


def _polyline_length(coords: Sequence[tuple[float, float]]) -> float:
    total = 0.0
    for i in range(len(coords) - 1):
        total += math.hypot(coords[i + 1][0] - coords[i][0], coords[i + 1][1] - coords[i][1])
    return total


def _azimuth_deg(coords: Sequence[tuple[float, float]]) -> float | None:
    if len(coords) < 2:
        return None
    x0, y0 = coords[0]
    x1, y1 = coords[-1]
    dx, dy = x1 - x0, y1 - y0
    if dx == 0 and dy == 0:
        return None
    # Geographic azimuth from north, folded to 0–180 (undirected).
    az = math.degrees(math.atan2(dx, dy)) % 180.0
    return float(az)


def _order_component_points(
    rows: np.ndarray,
    cols: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Order skeleton pixels along the principal axis for a polyline."""
    if rows.size <= 2:
        return rows, cols
    pts = np.column_stack([cols.astype(np.float64), rows.astype(np.float64)])
    mean = pts.mean(axis=0)
    centered = pts - mean
    # PCA via SVD
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    axis = vt[0]
    proj = centered @ axis
    order = np.argsort(proj)
    return rows[order], cols[order]


def extract_polylines_from_skeleton(
    skeleton: np.ndarray,
    *,
    xmin: float,
    ymax: float,
    dx: float,
    dy: float,
    params: ExtractionParams,
) -> list[dict[str, Any]]:
    labeled, nlab = ndimage.label(skeleton, structure=np.ones((3, 3), dtype=bool))
    features: list[dict[str, Any]] = []
    min_len_m = float(params.min_length_cells) * max(dx, dy)
    for lab in range(1, nlab + 1):
        ys, xs = np.where(labeled == lab)
        if ys.size < params.min_component_cells:
            continue
        ys_o, xs_o = _order_component_points(ys, xs)
        coords = _cell_centres(ys_o.tolist(), xs_o.tolist(), xmin=xmin, ymax=ymax, dx=dx, dy=dy)
        # Decimate to reduce zig-zag: keep endpoints + every Nth
        if len(coords) > 8:
            step = max(1, len(coords) // 12)
            slim = coords[::step]
            if slim[-1] != coords[-1]:
                slim.append(coords[-1])
            coords = slim
        length = _polyline_length(coords)
        if length < min_len_m:
            continue
        az = _azimuth_deg(coords)
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[float(x), float(y)] for x, y in coords],
                },
                "properties": {
                    "scientific_class": SCIENTIFIC_CLASS,
                    "not_confirmed_fault": True,
                    "not_confirmed_fracture": True,
                    "length_m": round(length, 3),
                    "azimuth_deg": None if az is None else round(az, 2),
                    "n_vertices": len(coords),
                    "component_id": int(lab),
                    "interpretation": (
                        "Candidate magnetic lineament from edge-enhanced TMI. "
                        "Not an independently validated geological structure."
                    ),
                },
            }
        )
    return features


def orientation_statistics(features: Sequence[dict[str, Any]]) -> dict[str, Any]:
    az = [
        float(f["properties"]["azimuth_deg"])
        for f in features
        if f.get("properties", {}).get("azimuth_deg") is not None
    ]
    lengths = [float(f["properties"]["length_m"]) for f in features]
    if not az:
        return {
            "n_lineaments": len(features),
            "mean_azimuth_deg": None,
            "circular_mean_azimuth_deg": None,
            "dominant_bin_deg": None,
            "rose_bins_15deg": [],
            "length_m": {
                "count": len(lengths),
                "min": min(lengths) if lengths else None,
                "max": max(lengths) if lengths else None,
                "mean": float(np.mean(lengths)) if lengths else None,
                "median": float(np.median(lengths)) if lengths else None,
                "total": float(np.sum(lengths)) if lengths else 0.0,
            },
            "ne_sw_theme_note": (
                "Publication-guided NE–SW structural theme is contextual only; "
                "candidate azimuths are not validated faults."
            ),
        }
    # Undirected circular mean: double angle
    ang = np.deg2rad(np.asarray(az) * 2.0)
    mean = 0.5 * math.degrees(math.atan2(float(np.sin(ang).mean()), float(np.cos(ang).mean())))
    mean = mean % 180.0
    bins = np.arange(0, 180, 15)
    hist, edges = np.histogram(az, bins=np.append(bins, 180))
    dominant_i = int(np.argmax(hist)) if hist.size else 0
    rose = [
        {"bin_start_deg": float(edges[i]), "bin_end_deg": float(edges[i + 1]), "count": int(hist[i])}
        for i in range(len(hist))
    ]
    return {
        "n_lineaments": len(features),
        "mean_azimuth_deg": float(np.mean(az)),
        "circular_mean_azimuth_deg": round(mean, 2),
        "dominant_bin_deg": [float(edges[dominant_i]), float(edges[dominant_i + 1])],
        "rose_bins_15deg": rose,
        "length_m": {
            "count": len(lengths),
            "min": float(min(lengths)),
            "max": float(max(lengths)),
            "mean": float(np.mean(lengths)),
            "median": float(np.median(lengths)),
            "total": float(np.sum(lengths)),
        },
        "ne_sw_theme_note": (
            "Publication-guided NE–SW (~45°) theme is contextual interpretation. "
            "Compare rose bins qualitatively; do not claim confirmed fault mapping."
        ),
    }


def build_geojson(
    features: Sequence[dict[str, Any]],
    *,
    crs: str,
    params: ExtractionParams,
    enhancement_meta: dict[str, Any],
    threshold: float,
) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": crs}},
        "properties": {
            "scientific_class": SCIENTIFIC_CLASS,
            "scientific_validation_status": "NOT_VALIDATED",
            "not_confirmed_faults_or_fractures": True,
            "software": SOFTWARE_ID,
            "software_version": SOFTWARE_VERSION,
            "extraction_params": params.to_dict(),
            "enhancement": enhancement_meta,
            "threshold_value": threshold,
            "created_at": _utc_now(),
        },
        "features": list(features),
    }


def segments_from_features(
    features: Sequence[dict[str, Any]],
) -> list[tuple[float, float, float, float]]:
    segs: list[tuple[float, float, float, float]] = []
    for feat in features:
        coords = (feat.get("geometry") or {}).get("coordinates") or []
        for i in range(len(coords) - 1):
            x1, y1 = float(coords[i][0]), float(coords[i][1])
            x2, y2 = float(coords[i + 1][0]), float(coords[i + 1][1])
            segs.append((x1, y1, x2, y2))
    return segs


def grid_axes(
    *,
    xmin: float,
    ymax: float,
    dx: float,
    dy: float,
    height: int,
    width: int,
) -> tuple[list[float], list[float]]:
    xs = [xmin + (c + 0.5) * dx for c in range(width)]
    # derive_lineament_rasters expects ys south→north then reverses to north-up.
    ys_s_to_n = [ymax - (height - 0.5 - r) * dy for r in range(height)]
    return xs, ys_s_to_n


def run_candidate_lineament_extraction(
    *,
    thg: np.ndarray | None,
    analytic: np.ndarray | None,
    tmi: np.ndarray | None,
    gaussian: np.ndarray | None,
    mask: np.ndarray,
    xmin: float,
    ymax: float,
    dx: float,
    dy: float,
    processing_crs: str,
    params: ExtractionParams | None = None,
    nodata: float = FEATURE_NODATA,
) -> dict[str, Any]:
    """Run full extraction; return arrays + geojson + stats (no I/O)."""
    params = params or ExtractionParams()
    enhancement, enh_meta = select_enhancement_grid(
        thg=thg,
        analytic=analytic,
        tmi=tmi,
        gaussian=gaussian,
        mask=mask,
        params=params,
    )
    binary, threshold = threshold_ridges(
        enhancement, mask, percentile=params.percentile
    )
    skeleton = skeletonize_binary(binary)
    features = extract_polylines_from_skeleton(
        skeleton,
        xmin=xmin,
        ymax=ymax,
        dx=dx,
        dy=dy,
        params=params,
    )
    geojson = build_geojson(
        features,
        crs=processing_crs,
        params=params,
        enhancement_meta=enh_meta,
        threshold=threshold,
    )
    stats = orientation_statistics(features)
    height, width = mask.shape
    density, distance, method = density_distance_from_skeleton(
        skeleton,
        segments=segments_from_features(features),
        dx=dx,
        dy=dy,
        window_m=params.density_window_m,
        nodata=nodata,
    )
    # Mask density/distance outside survey mask
    density = np.where(mask, density, nodata)
    distance = np.where(mask, distance, nodata)
    ridge_mask = skeleton.astype(np.uint8)
    return {
        "geojson": geojson,
        "features": features,
        "statistics": stats,
        "threshold": threshold,
        "enhancement_meta": enh_meta,
        "params": params.to_dict(),
        "density": density,
        "distance": distance,
        "ridge_mask": ridge_mask,
        "enhancement": np.where(np.isfinite(enhancement), enhancement, nodata),
        "method": method,
        "grid_meta": {
            "xmin": xmin,
            "ymax": ymax,
            "dx_m": dx,
            "dy_m": dy,
            "height": height,
            "width": width,
            "processing_crs": processing_crs,
        },
        "scientific_validation_status": "NOT_VALIDATED",
        "not_confirmed_faults_or_fractures": True,
        "used_in_inference": False,
        "software": SOFTWARE_ID,
        "software_version": SOFTWARE_VERSION,
        "created_at": _utc_now(),
    }


def density_distance_from_skeleton(
    skeleton: np.ndarray,
    *,
    segments: Sequence[tuple[float, float, float, float]],
    dx: float,
    dy: float,
    window_m: float,
    nodata: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Fast density/distance using EDT + box-filter length accumulation.

    Distance: Euclidean distance transform from skeleton cells (metres).
    Density: approximate total skeleton length in a square window / window area
    by counting skeleton pixels in the window × mean cell edge length.
    """
    del segments  # retained for API compatibility / future exact clip method
    cell_m = 0.5 * (abs(dx) + abs(dy))
    sk = skeleton.astype(bool)
    # Distance to nearest ridge (cells → metres). Invert skeleton for EDT.
    dist_cells = ndimage.distance_transform_edt(~sk)
    distance = dist_cells * cell_m
    # Approximate length per skeleton cell as cell_m (undercounts diagonals slightly).
    length_grid = sk.astype(np.float64) * cell_m
    # Window in cells (odd size).
    half = max(1, int(round((window_m / 2.0) / max(cell_m, 1e-6))))
    win = 2 * half + 1
    kernel = np.ones((win, win), dtype=np.float64)
    length_sum = ndimage.convolve(length_grid, kernel, mode="constant", cval=0.0)
    area = float(window_m * window_m)
    density = length_sum / area if area > 0 else np.zeros_like(length_sum)
    method = {
        "window_m": window_m,
        "density_units": "m_per_m2",
        "distance_units": "m",
        "algorithm": "edt_plus_box_filter_skeleton_length",
        "notes": (
            "Distance = EDT from skeleton cells × mean cell size. "
            "Density ≈ sum(skeleton cell lengths in window) / window area. "
            "Faster than exact segment clipping; suitable for candidate analytics."
        ),
        "window_cells": win,
        "cell_m": cell_m,
    }
    return density.astype(np.float64), distance.astype(np.float64), method


def write_extraction_outputs(
    result: dict[str, Any],
    out_dir: Path,
    *,
    nodata: float = FEATURE_NODATA,
) -> dict[str, Any]:
    """Persist GeoJSON, rasters, QC report under ``out_dir``."""
    from ssri_model.geological.magnetic_processing import write_geotiff, write_preview_png

    out_dir.mkdir(parents=True, exist_ok=True)
    gmeta = result["grid_meta"]
    crs = gmeta["processing_crs"]
    meta = {
        "xmin": gmeta["xmin"],
        "ymax": gmeta["ymax"],
        "resolution_x_m": gmeta["dx_m"],
        "resolution_y_m": gmeta["dy_m"],
        "resolution": gmeta["dx_m"],
        "dx_m": gmeta["dx_m"],
        "dy_m": gmeta["dy_m"],
    }
    geo_path = out_dir / "candidate_lineaments.geojson"
    geo_path.write_text(json.dumps(result["geojson"], indent=2), encoding="utf-8")

    dens_tif = out_dir / "lineament_density.tif"
    dist_tif = out_dir / "lineament_distance.tif"
    enh_tif = out_dir / "lineament_enhancement.tif"
    ridge_tif = out_dir / "lineament_ridge_mask.tif"
    write_geotiff(
        dens_tif,
        result["density"],
        meta,
        crs=crs,
        nodata=nodata,
        tags={"LAYER": "candidate_lineament_density", "USED_IN_INFERENCE": "false"},
    )
    write_geotiff(
        dist_tif,
        result["distance"],
        meta,
        crs=crs,
        nodata=nodata,
        tags={"LAYER": "candidate_lineament_distance", "USED_IN_INFERENCE": "false"},
    )
    write_geotiff(
        enh_tif,
        result["enhancement"],
        meta,
        crs=crs,
        nodata=nodata,
        tags={"LAYER": "lineament_enhancement"},
    )
    write_geotiff(
        ridge_tif,
        result["ridge_mask"].astype(np.float32),
        meta,
        crs=crs,
        nodata=0.0,
        tags={"LAYER": "lineament_ridge_mask"},
    )

    # Valid survey approx: finite enhancement
    survey = np.isfinite(result["enhancement"]) & (result["enhancement"] != nodata)
    write_preview_png(
        out_dir / "candidate_lineaments_preview.png",
        result["enhancement"],
        survey,
        title="Candidate magnetic lineament enhancement",
        cmap="inferno",
        units="enhancement",
    )

    qc = {
        "software": SOFTWARE_ID,
        "software_version": SOFTWARE_VERSION,
        "created_at": _utc_now(),
        "scientific_validation_status": "NOT_VALIDATED",
        "scientific_class": SCIENTIFIC_CLASS,
        "not_confirmed_faults_or_fractures": True,
        "used_in_inference": False,
        "params": result["params"],
        "enhancement": result["enhancement_meta"],
        "threshold": result["threshold"],
        "statistics": result["statistics"],
        "grid_meta": gmeta,
        "density_method": result["method"],
        "artifacts": {
            "geojson": "candidate_lineaments.geojson",
            "density_tif": "lineament_density.tif",
            "distance_tif": "lineament_distance.tif",
            "enhancement_tif": "lineament_enhancement.tif",
            "ridge_mask_tif": "lineament_ridge_mask.tif",
            "preview_png": "candidate_lineaments_preview.png",
        },
        "checksums_sha256": {
            "geojson": sha256_file(geo_path),
            "density_tif": sha256_file(dens_tif),
            "distance_tif": sha256_file(dist_tif),
            "enhancement_tif": sha256_file(enh_tif),
            "ridge_mask_tif": sha256_file(ridge_tif),
        },
        "quality_limitations": [
            "Candidates follow magnetic gradient ridges; they are not mapped faults.",
            "100 m TMI gridding limits resolvable structure length and continuity.",
            "Percentile thresholding is heuristic; alternate thresholds change density.",
            "Skeletonisation can fragment or join nearby ridges.",
            "Publication NE–SW theme is contextual, not independent field validation.",
        ],
        "additional_data_required_for_validation": [
            "Mapped fault/fracture inventories with CRS and confidence attributes",
            "Ground-truth structural geology overlays for the same AOI",
            "Optionally higher-resolution aeromagnetic or ground magnetic surveys",
        ],
    }
    qc_path = out_dir / "lineament_extraction_qc.json"
    qc_path.write_text(json.dumps(qc, indent=2), encoding="utf-8")
    qc["checksums_sha256"]["qc_json"] = sha256_file(qc_path)
    qc_path.write_text(json.dumps(qc, indent=2), encoding="utf-8")
    return qc
