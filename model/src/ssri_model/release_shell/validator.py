"""Release-shell upload validator: PASS/WARN/FAIL per check."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.ml.constants import FEATURE_NODATA, LABEL_NODATA
from ssri_model.ml.labels import label_class_names
from ssri_model.release_shell.channel_schema import (
    OVERBURDEN_THICKNESS,
    normalize_layer_name,
    schema_from_manifest,
)
from ssri_model.release_shell.point_grid_csv import ingest_point_grid_csv
from ssri_model.release_shell.flags import (
    release_shell_block_size_deg,
    release_shell_block_size_km,
    release_shell_buffer_km,
    release_shell_min_blocks,
    release_shell_min_held_out_blocks,
    release_shell_min_tiles,
)
from ssri_model.release_shell.spatial_split import (
    LOCAL_EVIDENCE_LIMITATION,
    TileGeo,
    block5,
    block_id,
    haversine_km,
    is_local_block_size,
    resolve_block_size_deg,
    split_by_blocks,
)


@dataclass
class CheckResult:
    name: str
    status: str  # PASS | WARN | FAIL
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HazardGatePreview:
    hazard: str
    labelled_tiles: int
    blocks_with_labels: int
    status: str  # ENABLED | DISABLED
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sample_dirs(root: Path) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for split in ("train", "validation", "test"):
        d = root / split
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.is_dir():
                out.append((split, p))
    return out


def _read_meta(sample_dir: Path) -> dict[str, Any]:
    path = sample_dir / "metadata.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def validate_release_shell_dataset(dataset_root: Path | str) -> dict[str, Any]:
    """Run release-shell checks; training must refuse on any FAIL."""
    root = Path(dataset_root)
    checks: list[CheckResult] = []
    hazards = list(label_class_names())
    min_tiles = release_shell_min_tiles()
    min_blocks = release_shell_min_blocks()
    min_held = release_shell_min_held_out_blocks()
    buffer_km = release_shell_buffer_km()
    size_deg = resolve_block_size_deg(
        block_size_deg=release_shell_block_size_deg(),
        block_size_km=release_shell_block_size_km(),
    )
    manifest: dict[str, Any] = {}
    man_path = root / "manifest.json"
    if man_path.exists():
        try:
            manifest = json.loads(man_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
    schema = schema_from_manifest(manifest)
    channel_names = list(schema.channel_names)
    channel_count = schema.channel_count

    if not root.is_dir():
        return {
            "overall": "FAIL",
            "can_train": False,
            "checks": [
                CheckResult(
                    "dataset_exists", "FAIL", f"Dataset directory missing: {root}"
                ).to_dict()
            ],
            "hazards": [],
            "minimums": {
                "tiles_per_hazard": min_tiles,
                "blocks": min_blocks,
                "held_out_blocks": min_held,
            },
        }

    samples = _sample_dirs(root)
    if not samples:
        checks.append(CheckResult("samples_present", "FAIL", "No sample folders found."))
    else:
        checks.append(
            CheckResult(
                "samples_present",
                "PASS",
                f"Found {len(samples)} sample folders.",
                {"n": len(samples)},
            )
        )

    # Schema / channels / shapes
    channel_fail = 0
    shape_fail = 0
    dtype_notes: list[str] = []
    crs_missing = 0
    coords_missing = 0
    tiles: list[TileGeo] = []
    channel_stats: dict[str, dict[str, float]] = {
        name: {"nodata_frac": 0.0, "constant_frac": 0.0, "n": 0} for name in channel_names
    }
    overburden_negative = 0
    label_counts: dict[str, Counter] = {h: Counter() for h in hazards}
    hazard_blocks: dict[str, set[str]] = {h: set() for h in hazards}
    synthetic_flags: list[bool] = []
    dates_warn = 0
    centroids: list[tuple[float, float]] = []
    sample_ids: list[str] = []

    for split, sdir in samples:
        sid = sdir.name
        sample_ids.append(sid)
        feat_path = sdir / "feature_stack.npy"
        label_path = sdir / "label.tif"
        meta = _read_meta(sdir)
        synthetic_flags.append(bool(meta.get("synthetic") or "SYNTHETIC" in sid.upper()))

        if not feat_path.exists():
            channel_fail += 1
            continue
        arr = np.load(feat_path)
        if arr.ndim != 3 or arr.shape[0] != channel_count:
            shape_fail += 1
            continue
        for i, name in enumerate(channel_names):
            ch = arr[i].astype(np.float64)
            nodata_m = ~np.isfinite(ch) | (ch == FEATURE_NODATA)
            frac_nd = float(nodata_m.mean()) if ch.size else 1.0
            finite = ch[~nodata_m]
            const = float(finite.size == 0 or (np.nanmax(finite) - np.nanmin(finite)) < 1e-12)
            st = channel_stats[name]
            st["nodata_frac"] = (st["nodata_frac"] * st["n"] + frac_nd) / (st["n"] + 1)
            st["constant_frac"] = (st["constant_frac"] * st["n"] + const) / (st["n"] + 1)
            st["n"] += 1
            if name == OVERBURDEN_THICKNESS and finite.size and float(np.nanmin(finite)) < 0:
                overburden_negative += 1

        crs = None
        lat = meta.get("centroid_lat", meta.get("lat"))
        lon = meta.get("centroid_lon", meta.get("lon"))
        if label_path.exists():
            with rasterio.open(label_path) as ds:
                crs = str(ds.crs) if ds.crs else None
                lab = ds.read(1)
                if lat is None or lon is None:
                    # approximate from transform center
                    try:
                        r, c = lab.shape[0] // 2, lab.shape[1] // 2
                        lon, lat = ds.xy(r, c)
                    except Exception:  # noqa: BLE001
                        pass
                for cls_i, hname in enumerate(hazards):
                    if np.any(lab == cls_i):
                        label_counts[hname]["tiles"] += 1
                        if lat is not None and lon is not None:
                            hazard_blocks[hname].add(
                                block_id(float(lat), float(lon), size_deg=size_deg)
                            )
                        label_counts[hname]["pixels"] += int((lab == cls_i).sum())
                if np.any(lab == LABEL_NODATA):
                    label_counts.setdefault("_nodata", Counter())["_nodata"] += 1
        else:
            shape_fail += 1

        if not crs:
            crs_missing += 1
        if lat is None or lon is None:
            coords_missing += 1
        else:
            tiles.append(
                TileGeo(sample_id=sid, lat=float(lat), lon=float(lon), crs=crs)
            )
            centroids.append((float(lat), float(lon)))

        img_date = meta.get("imagery_date")
        lab_date = meta.get("label_date")
        if img_date and lab_date and str(img_date) != str(lab_date):
            dates_warn += 1

    # Checks
    if channel_fail or shape_fail:
        checks.append(
            CheckResult(
                "schema_shapes",
                "FAIL",
                f"Invalid feature/label samples: channel/layout issues={channel_fail}, "
                f"shape issues={shape_fail}. Expected feature_stack.npy shape "
                f"({channel_count},H,W) for schema {schema.version} "
                f"with channels {channel_names}.",
            )
        )
    else:
        checks.append(CheckResult("schema_shapes", "PASS", "Channel count and shapes OK."))

    if coords_missing:
        checks.append(
            CheckResult(
                "coordinates",
                "FAIL",
                f"{coords_missing} sample(s) lack coordinates (centroid_lat/lon or "
                "georeferenced label.tif). Spatial block splitting requires coordinates "
                "and CRS — training refuses until these are present.",
            )
        )
    else:
        checks.append(CheckResult("coordinates", "PASS", "All samples have coordinates."))

    if crs_missing == len(samples) and samples:
        checks.append(
            CheckResult(
                "crs",
                "FAIL",
                "No sample has a CRS on label.tif. Provide georeferenced labels "
                "(EPSG code required) before training.",
            )
        )
    elif crs_missing:
        checks.append(
            CheckResult(
                "crs",
                "WARN",
                f"{crs_missing} sample(s) missing CRS; others OK.",
            )
        )
    else:
        checks.append(CheckResult("crs", "PASS", "CRS present on labels."))

    # Per-channel nodata / constant (known -9999 bug)
    bad_channels = []
    for name, st in channel_stats.items():
        if st["n"] == 0:
            continue
        if st["nodata_frac"] >= 0.999:
            bad_channels.append(f"{name}: ~100% nodata/sentinel ({FEATURE_NODATA})")
        elif st["constant_frac"] >= 0.999:
            bad_channels.append(f"{name}: effectively constant")
    if bad_channels:
        checks.append(
            CheckResult(
                "channel_quality",
                "FAIL",
                "One or more channels are all-sentinel or constant "
                "(known failure mode for ndvi/ndwi/clay/iron when filled with -9999). "
                + "; ".join(bad_channels),
                {"channels": channel_stats},
            )
        )
    else:
        checks.append(
            CheckResult(
                "channel_quality",
                "PASS",
                "No channel is entirely nodata/constant.",
                {"channels": channel_stats},
            )
        )

    if overburden_negative:
        checks.append(
            CheckResult(
                "overburden_units",
                "WARN",
                f"{overburden_negative} sample(s) have negative overburden_thickness "
                "values. Thickness should be ≥ 0 metres; confirm units and whether "
                "negatives are sentinels.",
            )
        )

    total_labelled_tiles = sum(int(label_counts[h]["tiles"]) for h in hazards)
    if samples and total_labelled_tiles == 0:
        checks.append(
            CheckResult(
                "labels_present",
                "FAIL",
                "No labelled pixels found for any hazard. Training refuses without labels. "
                "Upload a label inventory or labelled tiles (classes 0/1/2).",
            )
        )
    else:
        checks.append(
            CheckResult(
                "labels_present",
                "PASS" if total_labelled_tiles > 0 else "WARN",
                f"Labelled tiles across hazards: {total_labelled_tiles}.",
            )
        )

    # Duplicates / overlaps
    id_counts = Counter(sample_ids)
    dups = [k for k, v in id_counts.items() if v > 1]
    if dups:
        checks.append(
            CheckResult("duplicates", "FAIL", f"Duplicate sample ids: {dups[:10]}")
        )
    else:
        checks.append(CheckResult("duplicates", "PASS", "Sample ids unique."))

    nn_km = None
    if len(centroids) >= 2:
        dists = []
        for i, (la, lo) in enumerate(centroids):
            best = min(
                haversine_km(la, lo, lb, lob)
                for j, (lb, lob) in enumerate(centroids)
                if i != j
            )
            dists.append(best)
        nn_km = float(np.median(dists))
        checks.append(
            CheckResult(
                "nearest_neighbour",
                "WARN" if nn_km < 1.0 else "PASS",
                f"Median nearest-neighbour distance ≈ {nn_km:.2f} km.",
                {"median_nn_km": nn_km},
            )
        )

    # Spatial split feasibility
    split_info: dict[str, Any] | None = None
    if tiles and coords_missing == 0 and crs_missing < len(samples):
        try:
            distinct = {
                block_id(t.lat, t.lon, size_deg=size_deg) for t in tiles
            }
            split = split_by_blocks(
                tiles,
                buffer_km=buffer_km,
                min_held_out_blocks=min(min_held, max(1, len(distinct) // 3)),
                block_size_deg=size_deg,
            )
            split_info = split.to_dict()
            msg = (
                f"Valid block split: train={len(split.train_blocks)} "
                f"val={len(split.validation_blocks)} test={len(split.test_blocks)} "
                f"blocks at {size_deg:g}°; buffer={buffer_km} km."
            )
            if split.local_evidence_only:
                msg += f" {LOCAL_EVIDENCE_LIMITATION}."
            checks.append(
                CheckResult(
                    "spatial_split",
                    "PASS",
                    msg,
                    split_info,
                )
            )
        except ValueError as exc:
            checks.append(CheckResult("spatial_split", "FAIL", str(exc)))
    else:
        checks.append(
            CheckResult(
                "spatial_split",
                "FAIL",
                "Cannot build spatial split without coordinates and CRS.",
            )
        )

    if dates_warn:
        checks.append(
            CheckResult(
                "label_vs_imagery_dates",
                "WARN",
                f"{dates_warn} sample(s) have differing imagery_date vs label_date.",
            )
        )
    else:
        checks.append(
            CheckResult(
                "label_vs_imagery_dates",
                "PASS",
                "No label/imagery date mismatches flagged (or dates absent).",
            )
        )

    # Pseudo-absence distance (informational from metadata)
    checks.append(
        CheckResult(
            "pseudo_absence",
            "WARN",
            "Pseudo-absence distance to positives is not encoded in Stage 2.5 tiles; "
            "operators should document absence design outside this ZIP.",
        )
    )

    if any(synthetic_flags):
        checks.append(
            CheckResult(
                "synthetic_label",
                "WARN",
                "Dataset contains SYNTHETIC samples — for shell demos only, not real geography.",
            )
        )

    # Per-hazard minimums
    hazard_rows: list[HazardGatePreview] = []
    for h in hazards:
        n_tiles = int(label_counts[h].get("tiles", 0))
        n_blocks = len(hazard_blocks[h])
        if n_tiles >= min_tiles and n_blocks >= min_blocks:
            hazard_rows.append(
                HazardGatePreview(
                    h, n_tiles, n_blocks, "ENABLED", "Meets default minimums."
                )
            )
        else:
            hazard_rows.append(
                HazardGatePreview(
                    h,
                    n_tiles,
                    n_blocks,
                    "DISABLED",
                    f"insufficient labelled data (need ≥{min_tiles} tiles across "
                    f"≥{min_blocks} blocks with ≥{min_held} held out; "
                    f"found tiles={n_tiles}, blocks={n_blocks})",
                )
            )

    enabled = [h for h in hazard_rows if h.status == "ENABLED"]
    if not enabled:
        checks.append(
            CheckResult(
                "hazard_minimums",
                "WARN",
                "All hazards are DISABLED for skill claims (below minimum labelled data). "
                "Training may still run for shell demos if schema checks PASS, but "
                "gate status cannot reach 'evaluated'.",
                {"minimums_prominence": {
                    "tiles_per_hazard": min_tiles,
                    "blocks": min_blocks,
                    "held_out_blocks": min_held,
                }},
            )
        )
    else:
        checks.append(
            CheckResult(
                "hazard_minimums",
                "PASS",
                f"{len(enabled)} hazard(s) meet minimum labelled-data sizes.",
            )
        )

    fails = [c for c in checks if c.status == "FAIL"]
    # Schema FAIL blocks train; hazard DISABLED alone does not if user only wants a dry-run —
    # but acceptance wants training to refuse on broken ZIP. Soft: can_train if no FAIL.
    can_train = len(fails) == 0
    overall = "FAIL" if fails else ("WARN" if any(c.status == "WARN" for c in checks) else "PASS")

    return {
        "overall": overall,
        "can_train": can_train,
        "scientific_validation_status": "NOT_VALIDATED",
        "checks": [c.to_dict() for c in checks],
        "hazards": [h.to_dict() for h in hazard_rows],
        "label_pixel_counts": {h: dict(label_counts[h]) for h in hazards},
        "minimums": {
            "tiles_per_hazard": min_tiles,
            "blocks": min_blocks,
            "held_out_blocks": min_held,
            "buffer_km": buffer_km,
            "note": "Shown prominently: defaults 300 tiles / 8 blocks / 3 held out.",
        },
        "spatial_split": split_info,
        "n_samples": len(samples),
        "median_nn_km": nn_km,
        "score_framing": "relative susceptibility rankings (not probabilities or risk)",
    }


def validate_point_grid_layer(
    content: bytes,
    *,
    filename: str,
    layer_name: str,
    crs: str,
    working_crs: str | None = None,
) -> dict[str, Any]:
    """Validate a single declared feature-layer upload (point-grid CSV).

    Always FEATURE_LAYER_ONLY — a single layer cannot supervise training.
    Surfaces a visible ``unit_sanity`` WARN/FAIL (for example negative
    ``overburden_thickness``) instead of hiding it inside a free-text message.
    """
    checks: list[CheckResult] = []
    try:
        layer = ingest_point_grid_csv(
            content,
            filename=filename,
            layer_name=layer_name,
            crs=crs,
            working_crs=working_crs,
        )
    except ManualTrainingError as exc:
        code = exc.code
        status = "FAIL"
        checks.append(CheckResult("crs_declared", status, exc.message, {"code": code}))
        return {
            "overall": "FAIL",
            "can_train": False,
            "layer_name": normalize_layer_name(layer_name) or layer_name,
            "checks": [c.to_dict() for c in checks],
            "messages": [],
            "status": "FEATURE_LAYER_ONLY",
            "trainable": False,
            "scientific_validation_status": "NOT_VALIDATED",
        }

    checks.append(
        CheckResult(
            "crs_declared",
            "PASS",
            f"Declared CRS '{layer.crs}' parsed; working CRS '{layer.working_crs}'.",
            {"crs": layer.crs, "working_crs": layer.working_crs},
        )
    )
    checks.append(
        CheckResult(
            "grid_regular",
            "PASS",
            f"Regular grid {len(layer.xs)} x {len(layer.ys)}; "
            f"spacing X={layer.x_spacing:g} Y={layer.y_spacing:g}.",
            {"x_spacing": layer.x_spacing, "y_spacing": layer.y_spacing},
        )
    )
    if layer.missing_cells:
        checks.append(
            CheckResult(
                "gaps",
                "WARN",
                f"{layer.missing_cells} missing grid cell(s). SSRI does not fill gaps; "
                "provide complete cells or a mask before training.",
                {"missing_cells": layer.missing_cells},
            )
        )
    else:
        checks.append(CheckResult("gaps", "PASS", "No missing grid cells."))

    # Unit sanity: a declared thickness cannot be negative.
    unit_messages = [m for m in layer.messages if "UNIT_SANITY" in m]
    if unit_messages:
        checks.append(
            CheckResult(
                "unit_sanity",
                "WARN",
                unit_messages[0],
                {"value_min": layer.value_min, "value_max": layer.value_max},
            )
        )
    else:
        checks.append(
            CheckResult(
                "unit_sanity",
                "PASS",
                f"No negative {layer.name} values; "
                f"range {layer.value_min} … {layer.value_max}.",
                {"value_min": layer.value_min, "value_max": layer.value_max},
            )
        )

    fails = [c for c in checks if c.status == "FAIL"]
    overall = "FAIL" if fails else ("WARN" if any(c.status == "WARN" for c in checks) else "PASS")
    return {
        "overall": overall,
        "can_train": False,
        "layer_name": layer.name,
        "checks": [c.to_dict() for c in checks],
        "messages": list(layer.messages),
        "row_count": layer.row_count,
        "missing_cells": layer.missing_cells,
        "value_min": layer.value_min,
        "value_max": layer.value_max,
        "status": layer.status,
        "trainable": layer.trainable,
        "scientific_validation_status": "NOT_VALIDATED",
    }
