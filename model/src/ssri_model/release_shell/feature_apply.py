"""Apply lineament / overburden layers onto Stage 2.5 feature stacks (schema v2).

These helpers turn owner-supplied conditioning data into the three v2 channels
``overburden_thickness``, ``lineament_density``, ``lineament_distance`` and rewrite
``manifest.json`` / per-sample metadata so train/assess see a consistent schema.

Never fabricates missing science: empty lineaments → nodata rasters; overburden
cells outside the supplied grid stay FEATURE_NODATA.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import rasterio

from ssri_model.ml.constants import CHANNEL_COUNT, FEATURE_NODATA
from ssri_model.release_shell.channel_schema import (
    CHANNEL_NAMES_V1,
    CHANNEL_NAMES_V2,
    LINEAMENT_DENSITY,
    LINEAMENT_DISTANCE,
    OVERBURDEN_THICKNESS,
    SCHEMA_V2,
)
from ssri_model.release_shell.lineaments import (
    DEFAULT_WINDOW_M,
    LineamentMethod,
    derive_lineament_rasters,
)
from ssri_model.release_shell.point_grid_csv import PointGridLayer


def _sample_dirs(root: Path) -> list[Path]:
    out: list[Path] = []
    for split in ("train", "validation", "test"):
        d = root / split
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.is_dir() and (p / "feature_stack.npy").exists():
                out.append(p)
    return out


def _grid_from_label(sample_dir: Path) -> tuple[list[float], list[float], str | None]:
    """Build cell-centre xs/ys (map units) from label.tif geotransform."""
    label_path = sample_dir / "label.tif"
    if not label_path.exists():
        raise FileNotFoundError(f"Sample {sample_dir.name} is missing label.tif")
    with rasterio.open(label_path) as ds:
        h, w = ds.height, ds.width
        xs: list[float] = []
        ys: list[float] = []
        for c in range(w):
            x, _ = ds.xy(0, c)
            xs.append(float(x))
        for r in range(h):
            _, y = ds.xy(r, 0)
            ys.append(float(y))
        # derive_lineament_rasters expects ys south→north; it reverses internally.
        # label rows are north→south when using north-up GeoTIFFs; convert to ascending Y.
        ys_asc = list(reversed(ys)) if (len(ys) >= 2 and ys[0] > ys[-1]) else ys
        crs = str(ds.crs) if ds.crs else None
    return xs, ys_asc, crs


def _ensure_v2_stack(arr: np.ndarray) -> np.ndarray:
    """Return a (16, H, W) stack; pad from v1 with nodata; reject other ranks."""
    if arr.ndim != 3:
        raise ValueError(f"feature_stack must be (C,H,W); got shape {arr.shape}")
    c, h, w = arr.shape
    if c == len(CHANNEL_NAMES_V2):
        return arr.astype(np.float32, copy=True)
    if c == CHANNEL_COUNT or c == len(CHANNEL_NAMES_V1):
        out = np.full((len(CHANNEL_NAMES_V2), h, w), FEATURE_NODATA, dtype=np.float32)
        out[:c] = arr.astype(np.float32)
        return out
    raise ValueError(
        f"Cannot apply v2 channels to a stack with {c} channels "
        f"(expected {CHANNEL_COUNT} or {len(CHANNEL_NAMES_V2)})."
    )


def _write_v2_manifest(root: Path, *, extras: dict[str, Any] | None = None) -> dict[str, Any]:
    man_path = root / "manifest.json"
    manifest: dict[str, Any] = {}
    if man_path.exists():
        try:
            manifest = json.loads(man_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
    manifest["channel_schema_version"] = SCHEMA_V2
    manifest["channel_names"] = list(CHANNEL_NAMES_V2)
    manifest["channels"] = list(CHANNEL_NAMES_V2)
    manifest["channel_schema"] = {
        "version": SCHEMA_V2,
        "channel_names": list(CHANNEL_NAMES_V2),
        "channel_count": len(CHANNEL_NAMES_V2),
    }
    if extras:
        manifest.setdefault("conditioning_layers", {}).update(extras)
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _update_sample_meta(sample_dir: Path, **fields: Any) -> None:
    path = sample_dir / "metadata.json"
    meta: dict[str, Any] = {}
    if path.exists():
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}
    meta["channel_schema_version"] = SCHEMA_V2
    meta["channel_names"] = list(CHANNEL_NAMES_V2)
    meta.update(fields)
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def apply_lineaments_to_dataset(
    dataset_root: Path | str,
    segments: Sequence[tuple[float, float, float, float]],
    *,
    window_m: float = DEFAULT_WINDOW_M,
    lineament_crs: str | None = None,
) -> dict[str, Any]:
    """Derive density/distance per tile and write channels 14–15 (0-based 14,15)."""
    root = Path(dataset_root)
    samples = _sample_dirs(root)
    if not samples:
        raise FileNotFoundError(f"No sample folders with feature_stack.npy under {root}")

    method = LineamentMethod(window_m=window_m)
    updated = 0
    for sdir in samples:
        xs, ys, tile_crs = _grid_from_label(sdir)
        density, distance, _ = derive_lineament_rasters(
            xs, ys, segments, window_m=window_m
        )
        stack = _ensure_v2_stack(np.load(sdir / "feature_stack.npy"))
        # CHANNEL_NAMES_V2 indices: 13 overburden, 14 density, 15 distance
        idx_d = CHANNEL_NAMES_V2.index(LINEAMENT_DENSITY)
        idx_dist = CHANNEL_NAMES_V2.index(LINEAMENT_DISTANCE)
        stack[idx_d] = density.astype(np.float32)
        stack[idx_dist] = distance.astype(np.float32)
        np.save(sdir / "feature_stack.npy", stack)
        _update_sample_meta(
            sdir,
            lineament_method=method.to_dict(),
            lineament_crs=lineament_crs or tile_crs,
        )
        updated += 1

    manifest = _write_v2_manifest(
        root,
        extras={
            "lineaments": {
                "n_segments": len(segments),
                "method": method.to_dict(),
                "crs": lineament_crs,
                "samples_updated": updated,
            }
        },
    )
    return {
        "overall": "PASS",
        "samples_updated": updated,
        "method": method.to_dict(),
        "channel_schema_version": SCHEMA_V2,
        "manifest_channels": manifest.get("channel_names"),
        "note": (
            "lineament_density / lineament_distance written into every feature_stack. "
            "Coordinates must already be in the same projected metres CRS as the tiles."
        ),
    }


def _sample_grid_layer(
    layer: PointGridLayer,
    xs: Sequence[float],
    ys_asc: Sequence[float],
) -> np.ndarray:
    """Nearest-neighbour sample of a point-grid layer onto tile cell centres.

    ``ys_asc`` is south→north; returned array is north-up (row 0 = north) to match
    feature_stack / label GeoTIFF convention.
    """
    h, w = len(ys_asc), len(xs)
    north_ys = list(reversed(list(ys_asc)))
    out = np.full((h, w), FEATURE_NODATA, dtype=np.float32)
    # Build lookup with quantized keys matching PointGridLayer._key behaviour
    from ssri_model.release_shell.point_grid_csv import _key

    for r, y in enumerate(north_ys):
        for c, x in enumerate(xs):
            val = layer.values.get((_key(float(x)), _key(float(y))))
            if val is None:
                # nearest neighbour in layer grid
                if not layer.xs or not layer.ys:
                    continue
                ix = min(range(len(layer.xs)), key=lambda i: abs(layer.xs[i] - x))
                iy = min(range(len(layer.ys)), key=lambda i: abs(layer.ys[i] - y))
                # only accept if within half a cell of spacing
                if abs(layer.xs[ix] - x) > layer.x_spacing * 0.6:
                    continue
                if abs(layer.ys[iy] - y) > layer.y_spacing * 0.6:
                    continue
                val = layer.values.get((_key(layer.xs[ix]), _key(layer.ys[iy])))
            if val is None:
                continue
            out[r, c] = float(val)
    return out


def apply_overburden_to_dataset(
    dataset_root: Path | str,
    layer: PointGridLayer,
    *,
    measurement_type: str,
    units: str,
) -> dict[str, Any]:
    """Write overburden_thickness channel from a validated point-grid layer.

    ``measurement_type`` must be ``thickness``. Depth-to-interface uploads must use
    layer name ``depth_to_bedrock`` and are **not** written into the v2 thickness
    channel (no silent conversion).
    """
    mt = (measurement_type or "").strip().lower()
    if mt not in {"thickness", "overburden_thickness"}:
        raise ValueError(
            f"measurement_type={measurement_type!r} cannot be written to the "
            f"{OVERBURDEN_THICKNESS} channel. Use measurement_type='thickness', "
            "or declare depth-to-interface as depth_to_bedrock (not auto-converted)."
        )
    if layer.name != OVERBURDEN_THICKNESS:
        raise ValueError(
            f"Layer name is '{layer.name}', expected '{OVERBURDEN_THICKNESS}'. "
            "Depth-to-bedrock is a different quantity and is not auto-converted."
        )

    root = Path(dataset_root)
    samples = _sample_dirs(root)
    if not samples:
        raise FileNotFoundError(f"No sample folders with feature_stack.npy under {root}")

    updated = 0
    idx = CHANNEL_NAMES_V2.index(OVERBURDEN_THICKNESS)
    for sdir in samples:
        xs, ys_asc, _crs = _grid_from_label(sdir)
        sampled = _sample_grid_layer(layer, xs, ys_asc)
        stack = _ensure_v2_stack(np.load(sdir / "feature_stack.npy"))
        stack[idx] = sampled
        np.save(sdir / "feature_stack.npy", stack)
        _update_sample_meta(
            sdir,
            overburden_measurement_type="thickness",
            overburden_units=units,
            overburden_crs=layer.working_crs,
        )
        updated += 1

    manifest = _write_v2_manifest(
        root,
        extras={
            "overburden": {
                "measurement_type": "thickness",
                "units": units,
                "crs": layer.working_crs,
                "declared_crs": layer.crs,
                "value_min": layer.value_min,
                "value_max": layer.value_max,
                "samples_updated": updated,
                "messages": list(layer.messages),
            }
        },
    )
    return {
        "overall": "PASS",
        "samples_updated": updated,
        "measurement_type": "thickness",
        "units": units,
        "channel_schema_version": SCHEMA_V2,
        "manifest_channels": manifest.get("channel_names"),
        "layer_messages": list(layer.messages),
    }
