"""Improved USGS FeatureStack dataset builder (v3 sampling + audit hooks).

Presence samples: stratified by 2° blocks from USGS catalog (CONUS only),
with minimum separation between selected positives.

Pseudo-absences: land-biased offsets from inventory positives, required to
remain outside an exclusion buffer of the **full CONUS inventory** (not only
the selected subset), with minimum inter-absence separation. Documented as
pseudo-absences — not field-confirmed.

Supports ``--reuse-from`` to hardlink/copy existing FeatureStacks (e.g. v2)
when sample_ids match, avoiding duplicate live extractions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import random
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

import numpy as np
from dotenv import load_dotenv

from ssri_model.data.feature_engineering import build_feature_stack
from ssri_model.ingestion.schema import HazardLabelSet

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CATALOG = REPO_ROOT / "data" / "catalogs" / "usgs_landslide_v3" / "catalog.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "datasets" / "usgs_landslide_featurestacks" / "v3"

CONUS_BOUNDS = (-125.0, 24.0, -66.0, 50.0)
HALF_SIDE_DEG = 0.009
BLOCK_DEG = 2.0


@dataclass(frozen=True)
class TrainingPoint:
    sample_id: str
    latitude: float
    longitude: float
    landslide: int
    provenance: dict[str, Any]


def _in_conus(lat: float, lon: float) -> bool:
    west, south, east, north = CONUS_BOUNDS
    return south <= lat <= north and west <= lon <= east


def _spatial_block_id(lat: float, lon: float, block_deg: float = BLOCK_DEG) -> str:
    lat_i = int(math.floor(lat / block_deg))
    lon_i = int(math.floor(lon / block_deg))
    return f"b{lat_i}_{lon_i}"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _min_distance_km(lat: float, lon: float, refs: Sequence[tuple[float, float]]) -> float:
    if not refs:
        return float("inf")
    return min(_haversine_km(lat, lon, rlat, rlon) for rlat, rlon in refs)


def iter_catalog_positives(catalog_path: Path) -> Iterator[dict[str, Any]]:
    with catalog_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def load_conus_inventory_coords(catalog_path: Path) -> np.ndarray:
    """Return ``(N, 2)`` array of CONUS inventory ``[lat, lon]``."""
    coords: list[list[float]] = []
    for row in iter_catalog_positives(catalog_path):
        lat = float(row["latitude"])
        lon = float(row["longitude"])
        if not _in_conus(lat, lon):
            continue
        labels = row.get("labels") or {}
        if labels.get("landslide") != 1:
            continue
        coords.append([lat, lon])
    if not coords:
        raise RuntimeError(f"No CONUS inventory coordinates in {catalog_path}")
    return np.asarray(coords, dtype=np.float64)


def _too_close_to_inventory(
    lat: float,
    lon: float,
    inventory_xy: np.ndarray,
    *,
    min_km: float,
) -> bool:
    """Fast approximate filter then precise check on nearby candidates."""
    # ~1° lat ≈ 111 km; lon scaled by cos(lat)
    lat_pad = min_km / 111.0 * 1.25
    lon_pad = min_km / (111.0 * max(0.2, abs(math.cos(math.radians(lat))))) * 1.25
    lats = inventory_xy[:, 0]
    lons = inventory_xy[:, 1]
    mask = (
        (np.abs(lats - lat) <= lat_pad)
        & (np.abs(lons - lon) <= lon_pad)
    )
    if not np.any(mask):
        return False
    subset = inventory_xy[mask]
    for rlat, rlon in subset:
        if _haversine_km(lat, lon, float(rlat), float(rlon)) < min_km:
            return True
    return False


def stratified_positive_sample(
    catalog_path: Path,
    *,
    n_positives: int,
    seed: int,
    min_separation_km: float = 2.0,
    exclude_ids: set[str] | None = None,
) -> list[TrainingPoint]:
    """Stratify by 2° blocks; enforce min separation between selected positives."""
    exclude_ids = exclude_ids or set()
    by_block: dict[str, list[dict[str, Any]]] = {}
    for row in iter_catalog_positives(catalog_path):
        lat = float(row["latitude"])
        lon = float(row["longitude"])
        if not _in_conus(lat, lon):
            continue
        labels = row.get("labels") or {}
        if labels.get("landslide") != 1:
            continue
        sid = str(row["sample_id"])
        if sid in exclude_ids:
            continue
        block = _spatial_block_id(lat, lon)
        by_block.setdefault(block, []).append(row)

    if not by_block:
        raise RuntimeError(f"No CONUS landslide positives found in {catalog_path}")

    rng = random.Random(seed)
    blocks = sorted(by_block.keys())
    rng.shuffle(blocks)

    selected: list[TrainingPoint] = []
    selected_xy: list[tuple[float, float]] = []

    while len(selected) < n_positives:
        progressed = False
        for block in blocks:
            if len(selected) >= n_positives:
                break
            pool = [
                r
                for r in by_block[block]
                if r["sample_id"] not in {p.sample_id for p in selected}
            ]
            if not pool:
                continue
            rng.shuffle(pool)
            chosen = None
            for row in pool:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
                if selected_xy and _min_distance_km(lat, lon, selected_xy) < min_separation_km:
                    continue
                chosen = row
                break
            if chosen is None:
                continue
            lat = float(chosen["latitude"])
            lon = float(chosen["longitude"])
            selected.append(
                TrainingPoint(
                    sample_id=str(chosen["sample_id"]),
                    latitude=lat,
                    longitude=lon,
                    landslide=1,
                    provenance={
                        "role": "inventory_presence",
                        "dataset_name": chosen.get("dataset_name"),
                        "dataset_version": chosen.get("dataset_version"),
                        "spatial_block": block,
                        "quality_flags": chosen.get("quality_flags", []),
                        "min_separation_km": min_separation_km,
                    },
                )
            )
            selected_xy.append((lat, lon))
            progressed = True
        if not progressed:
            break

    if len(selected) < n_positives:
        logger.warning(
            "Only sampled %s/%s positives (block/separation constraints)",
            len(selected),
            n_positives,
        )
    return selected


def generate_pseudo_absences(
    positives: list[TrainingPoint],
    inventory_xy: np.ndarray,
    *,
    n_absences: int,
    seed: int,
    min_distance_km: float = 15.0,
    max_distance_km: float = 100.0,
    min_inter_absence_km: float = 5.0,
) -> list[TrainingPoint]:
    """Documented land-biased pseudo-absences with full-inventory exclusion.

    Rationale
    ---------
    USGS inventory is presence-only. Confirmed field absences are unavailable.
    Pseudo-absences are generated by offsetting from inventory positives so
    candidates remain in terrestrial landslide-reporting geography (avoiding
    oceans that broke OpenTopo/DEM). Candidates must be ≥ ``min_distance_km``
    from **any** CONUS inventory point (not only the selected subset) to reduce
    label contamination near unmapped events clustered with known landslides.
    Inter-absence separation reduces near-duplicates.

    These remain **pseudo-absences** (``pseudo_absence=true``), not surveys.
    """
    if not positives:
        raise RuntimeError("Cannot generate pseudo-absences without positives")

    rng = random.Random(seed + 17)
    absences: list[TrainingPoint] = []
    absence_xy: list[tuple[float, float]] = []
    attempts = 0
    max_attempts = n_absences * 800

    while len(absences) < n_absences and attempts < max_attempts:
        attempts += 1
        anchor = rng.choice(positives)
        bearing = rng.uniform(0.0, 2.0 * math.pi)
        dist_km = rng.uniform(min_distance_km, max_distance_km)
        dlat = (dist_km / 111.0) * math.cos(bearing)
        dlon = (
            dist_km
            / (111.0 * max(math.cos(math.radians(anchor.latitude)), 0.2))
        ) * math.sin(bearing)
        lat = anchor.latitude + dlat
        lon = anchor.longitude + dlon
        if not _in_conus(lat, lon):
            continue
        if _too_close_to_inventory(lat, lon, inventory_xy, min_km=min_distance_km):
            continue
        if absence_xy and _min_distance_km(lat, lon, absence_xy) < min_inter_absence_km:
            continue
        digest = hashlib.sha1(f"{lat:.6f},{lon:.6f},{seed}".encode()).hexdigest()[:10]
        sid = f"pseudo-absence-{digest}"
        if any(a.sample_id == sid for a in absences):
            continue
        absences.append(
            TrainingPoint(
                sample_id=sid,
                latitude=lat,
                longitude=lon,
                landslide=0,
                provenance={
                    "role": "pseudo_absence",
                    "method": "offset_from_inventory_positive_full_inventory_buffer",
                    "anchor_sample_id": anchor.sample_id,
                    "min_distance_km": min_distance_km,
                    "max_distance_km": max_distance_km,
                    "min_inter_absence_km": min_inter_absence_km,
                    "inventory_exclusion_scope": "all_conus_usgs_catalog_points",
                    "quality_flags": [
                        "pseudo_absence=true",
                        "not_field_confirmed_absence=true",
                        "land_biased_offset=true",
                        "full_inventory_exclusion_buffer=true",
                    ],
                    "spatial_block": _spatial_block_id(lat, lon),
                },
            )
        )
        absence_xy.append((lat, lon))

    if len(absences) < n_absences:
        raise RuntimeError(
            f"Could only place {len(absences)}/{n_absences} pseudo-absences "
            f"after {attempts} attempts"
        )
    return absences


def point_to_bbox(
    lat: float, lon: float, half_side_deg: float = HALF_SIDE_DEG
) -> tuple[float, float, float, float]:
    return (
        lon - half_side_deg,
        lat - half_side_deg,
        lon + half_side_deg,
        lat + half_side_deg,
    )


def export_sample(sample_dir: Path, point: TrainingPoint, stack: Any) -> None:
    sample_dir.mkdir(parents=True, exist_ok=True)
    stack.save_numpy(sample_dir / "feature_stack.npy")
    stack.save_manifest(sample_dir / "manifest.json")

    h, w = stack.grid_spec.height, stack.grid_spec.width
    nodata = float(stack.grid_spec.nodata)
    landslide_arr = np.full((h, w), float(point.landslide), dtype=np.float32)
    missing = np.full((h, w), nodata, dtype=np.float32)
    np.savez_compressed(
        sample_dir / "labels_multitask.npz",
        landslide=landslide_arr,
        subsidence=missing,
        liquefaction=missing,
        landslide_mask=np.ones((h, w), dtype=np.uint8),
        subsidence_mask=np.zeros((h, w), dtype=np.uint8),
        liquefaction_mask=np.zeros((h, w), dtype=np.uint8),
    )

    import rasterio

    profile = {
        "driver": "GTiff",
        "height": h,
        "width": w,
        "count": 1,
        "dtype": "float32",
        "crs": stack.grid_spec.crs,
        "transform": stack.grid_spec.transform,
        "nodata": nodata,
    }
    with rasterio.open(sample_dir / "label.tif", "w", **profile) as dst:
        dst.write(landslide_arr, 1)
        dst.set_band_description(1, "landslide")

    labels = HazardLabelSet(
        landslide=point.landslide,
        subsidence=None,
        liquefaction=None,
    )
    metadata = {
        "sample_id": point.sample_id,
        "latitude": point.latitude,
        "longitude": point.longitude,
        "bbox_wgs84": list(point_to_bbox(point.latitude, point.longitude)),
        "labels": labels.as_dict(),
        "provenance": point.provenance,
        "feature_shape": list(stack.feature_tensor.shape),
        "channel_names": list(stack.channel_names),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "spatial_block": point.provenance.get("spatial_block"),
    }
    (sample_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )


def spatial_block_split(
    points: list[TrainingPoint],
    *,
    seed: int,
    train_frac: float = 0.7,
    val_frac: float = 0.15,
) -> dict[str, list[str]]:
    """Hold out entire 2° blocks to reduce spatial leakage."""
    blocks: dict[str, list[TrainingPoint]] = {}
    for p in points:
        bid = str(
            p.provenance.get("spatial_block")
            or _spatial_block_id(p.latitude, p.longitude)
        )
        blocks.setdefault(bid, []).append(p)

    block_ids = sorted(blocks.keys())
    rng = random.Random(seed)
    rng.shuffle(block_ids)
    n = len(block_ids)
    n_train = max(1, int(n * train_frac))
    n_val = max(1, int(n * val_frac)) if n >= 3 else 0
    train_blocks = set(block_ids[:n_train])
    val_blocks = set(block_ids[n_train : n_train + n_val])
    test_blocks = set(block_ids[n_train + n_val :])
    if not test_blocks and block_ids and len(train_blocks) > 1:
        moved = block_ids[0]
        train_blocks.discard(moved)
        test_blocks.add(moved)

    splits: dict[str, list[str]] = {"train": [], "validation": [], "test": []}
    for bid, members in blocks.items():
        if bid in train_blocks:
            key = "train"
        elif bid in val_blocks:
            key = "validation"
        else:
            key = "test"
        splits[key].extend(p.sample_id for p in members)
    return splits


def configure_conus_geophysics() -> None:
    grav = REPO_ROOT / "data" / "geophysics" / "processed" / "wgm2012_bouguer_conus.tif"
    mag = REPO_ROOT / "data" / "geophysics" / "processed" / "emag2v3_conus.tif"
    os.environ.setdefault("GRAVITY_DATA_PATH", str(grav))
    os.environ.setdefault("MAGNETIC_DATA_PATH", str(mag))
    # Explicit: do not claim EIGEN-6C4 unless that raster is configured.
    os.environ.setdefault("SSRI_GRAVITY_SOURCE", "wgm2012_bouguer")


def write_sampling_audit(
    output_root: Path,
    points: list[TrainingPoint],
    splits: dict[str, list[str]],
    inventory_xy: np.ndarray,
    *,
    min_absence_km: float,
) -> dict[str, Any]:
    """Machine-readable audit of sampling and spatial split properties."""
    by_id = {p.sample_id: p for p in points}
    split_of = {}
    for name, ids in splits.items():
        for sid in ids:
            split_of[sid] = name

    positives = [p for p in points if p.landslide == 1]
    absences = [p for p in points if p.landslide == 0]

    # Nearest train↔test distances
    train_pts = [by_id[s] for s in splits.get("train", []) if s in by_id]
    test_pts = [by_id[s] for s in splits.get("test", []) if s in by_id]
    nn_train_test: list[float] = []
    for t in test_pts:
        if not train_pts:
            break
        nn_train_test.append(
            min(
                _haversine_km(t.latitude, t.longitude, tr.latitude, tr.longitude)
                for tr in train_pts
            )
        )

    # Absence distance to full inventory
    abs_to_inv = []
    for a in absences:
        # approximate via too_close helper inverted — compute min over nearby
        lat_pad = min_absence_km / 111.0 * 3
        lon_pad = min_absence_km / 50.0 * 3
        mask = (
            (np.abs(inventory_xy[:, 0] - a.latitude) <= lat_pad)
            & (np.abs(inventory_xy[:, 1] - a.longitude) <= lon_pad)
        )
        subset = inventory_xy[mask] if np.any(mask) else inventory_xy[:: max(1, len(inventory_xy)//5000)]
        dmin = min(
            (_haversine_km(a.latitude, a.longitude, float(r[0]), float(r[1])) for r in subset),
            default=float("inf"),
        )
        abs_to_inv.append(dmin)

    blocks = sorted({str(p.provenance.get("spatial_block")) for p in points})
    block_counts: dict[str, dict[str, int]] = {}
    for p in points:
        bid = str(p.provenance.get("spatial_block"))
        split = split_of.get(p.sample_id, "unassigned")
        block_counts.setdefault(bid, {"train": 0, "validation": 0, "test": 0, "pos": 0, "neg": 0})
        if split in block_counts[bid]:
            block_counts[bid][split] += 1
        if p.landslide == 1:
            block_counts[bid]["pos"] += 1
        else:
            block_counts[bid]["neg"] += 1

    # Pathological: same block in multiple splits should be 0 by construction
    multi_split_blocks = [
        bid
        for bid, c in block_counts.items()
        if sum(1 for k in ("train", "validation", "test") if c[k] > 0) > 1
    ]

    def _extent(pts: list[TrainingPoint]) -> dict[str, float] | None:
        if not pts:
            return None
        return {
            "min_lat": min(p.latitude for p in pts),
            "max_lat": max(p.latitude for p in pts),
            "min_lon": min(p.longitude for p in pts),
            "max_lon": max(p.longitude for p in pts),
        }

    audit = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "n_points": len(points),
        "n_positives": len(positives),
        "n_absences": len(absences),
        "class_balance": {
            "positive_fraction": len(positives) / max(len(points), 1),
            "negative_fraction": len(absences) / max(len(points), 1),
        },
        "n_spatial_blocks": len(blocks),
        "blocks": blocks,
        "block_counts": block_counts,
        "multi_split_blocks": multi_split_blocks,
        "split_counts": {k: len(v) for k, v in splits.items()},
        "split_class_counts": {
            name: {
                "positives": sum(1 for s in ids if by_id.get(s) and by_id[s].landslide == 1),
                "negatives": sum(1 for s in ids if by_id.get(s) and by_id[s].landslide == 0),
            }
            for name, ids in splits.items()
        },
        "geographic_extent": {
            "all": _extent(points),
            "train": _extent(train_pts),
            "validation": _extent([by_id[s] for s in splits.get("validation", []) if s in by_id]),
            "test": _extent(test_pts),
        },
        "nearest_train_test_km": {
            "n": len(nn_train_test),
            "min": min(nn_train_test) if nn_train_test else None,
            "median": float(np.median(nn_train_test)) if nn_train_test else None,
            "mean": float(np.mean(nn_train_test)) if nn_train_test else None,
        },
        "absence_to_inventory_km": {
            "n": len(abs_to_inv),
            "min": min(abs_to_inv) if abs_to_inv else None,
            "median": float(np.median(abs_to_inv)) if abs_to_inv else None,
            "below_exclusion_buffer": int(sum(1 for d in abs_to_inv if d < min_absence_km)),
        },
        "pseudo_absence_methodology": {
            "type": "documented_pseudo_absence",
            "method": "offset_from_inventory_positive_full_inventory_buffer",
            "min_distance_km": min_absence_km,
            "not_field_confirmed": True,
            "rationale": (
                "Presence-only inventory; absences are synthetic offsets outside "
                "a buffer of all CONUS USGS points to reduce contamination and "
                "ocean/DEM-void failures from uniform CONUS draws."
            ),
        },
    }
    (output_root / "sampling_audit.json").write_text(
        json.dumps(audit, indent=2),
        encoding="utf-8",
    )
    return audit


def _reuse_sample(src_root: Path, dst_dir: Path, sample_id: str) -> bool:
    src = src_root / "samples" / sample_id
    marker = src / "feature_stack.npy"
    if not marker.exists():
        return False
    dst_dir.parent.mkdir(parents=True, exist_ok=True)
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    try:
        shutil.copytree(src, dst_dir)
    except OSError:
        return False
    return (dst_dir / "feature_stack.npy").exists()


def build_dataset(args: argparse.Namespace) -> Path:
    load_dotenv(REPO_ROOT / ".env")
    configure_conus_geophysics()

    catalog = Path(args.catalog)
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    inventory_xy = load_conus_inventory_coords(catalog)
    logger.info("Loaded %s CONUS inventory coordinates for exclusion buffer", len(inventory_xy))

    positives = stratified_positive_sample(
        catalog,
        n_positives=args.n_positives,
        seed=args.seed,
        min_separation_km=args.min_positive_separation_km,
    )
    absences = generate_pseudo_absences(
        positives,
        inventory_xy,
        n_absences=args.n_absences,
        seed=args.seed,
        min_distance_km=args.min_absence_km,
        max_distance_km=args.max_absence_km,
        min_inter_absence_km=args.min_inter_absence_km,
    )
    points = positives + absences
    random.Random(args.seed).shuffle(points)

    selection_path = output_root / "selection.json"
    selection_path.write_text(
        json.dumps(
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "catalog": str(catalog),
                "version": "v3",
                "n_positives_requested": args.n_positives,
                "n_absences_requested": args.n_absences,
                "n_positives": len(positives),
                "n_absences": len(absences),
                "seed": args.seed,
                "min_absence_km": args.min_absence_km,
                "max_absence_km": args.max_absence_km,
                "min_inter_absence_km": args.min_inter_absence_km,
                "min_positive_separation_km": args.min_positive_separation_km,
                "half_side_deg": HALF_SIDE_DEG,
                "start_date": args.start_date,
                "end_date": args.end_date,
                "resolution_m": args.resolution_m,
                "reuse_from": str(args.reuse_from) if args.reuse_from else None,
                "absence_semantics": (
                    "Documented pseudo-absences: offsets from inventory positives, "
                    f"≥{args.min_absence_km} km from ALL CONUS USGS catalog points, "
                    f"≥{args.min_inter_absence_km} km apart. Not field-confirmed."
                ),
                "points": [asdict(p) for p in points],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    splits = spatial_block_split(points, seed=args.seed)
    write_sampling_audit(
        output_root,
        points,
        splits,
        inventory_xy,
        min_absence_km=args.min_absence_km,
    )

    samples_root = output_root / "samples"
    samples_root.mkdir(parents=True, exist_ok=True)
    reuse_root = Path(args.reuse_from) if args.reuse_from else None

    built: list[str] = []
    reused: list[str] = []
    failed: list[dict[str, str]] = []
    for idx, point in enumerate(points, start=1):
        sample_dir = samples_root / point.sample_id
        marker = sample_dir / "feature_stack.npy"
        if marker.exists() and not args.force:
            logger.info("[%s/%s] skip existing %s", idx, len(points), point.sample_id)
            built.append(point.sample_id)
            continue

        if reuse_root is not None and not args.force:
            if _reuse_sample(reuse_root, sample_dir, point.sample_id):
                logger.info("[%s/%s] reused %s from %s", idx, len(points), point.sample_id, reuse_root)
                # Refresh metadata/labels for v3 provenance if present in reuse
                built.append(point.sample_id)
                reused.append(point.sample_id)
                continue

        bbox = point_to_bbox(point.latitude, point.longitude)
        logger.info(
            "[%s/%s] building %s landslide=%s bbox=%s",
            idx,
            len(points),
            point.sample_id,
            point.landslide,
            bbox,
        )
        t0 = time.perf_counter()
        try:
            stack = build_feature_stack(
                bbox,
                args.start_date,
                args.end_date,
                resolution_m=args.resolution_m,
            )
            export_sample(sample_dir, point, stack)
            elapsed = time.perf_counter() - t0
            logger.info("  ok shape=%s in %.1fs", stack.feature_tensor.shape, elapsed)
            built.append(point.sample_id)
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - t0
            logger.exception("  FAILED after %.1fs: %s", elapsed, exc)
            failed.append({"sample_id": point.sample_id, "error": str(exc)})
            if sample_dir.exists():
                (sample_dir / "FAILED.json").write_text(
                    json.dumps({"error": str(exc)}, indent=2),
                    encoding="utf-8",
                )

    built_set = set(built)
    final_splits = {
        name: [sid for sid in ids if sid in built_set] for name, ids in splits.items()
    }
    stats = _compute_channel_stats(samples_root, final_splits.get("train", []))
    (output_root / "statistics.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    gravity_source = os.getenv("SSRI_GRAVITY_SOURCE", "wgm2012_bouguer")
    manifest = {
        "dataset_name": "usgs_landslide_featurestacks",
        "version": "v3",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_catalog": str(catalog),
        "n_requested": len(points),
        "n_built": len(built),
        "n_reused": len(reused),
        "n_failed": len(failed),
        "failed": failed,
        "splits": final_splits,
        "split_strategy": "spatial_block_2deg",
        "dem_provider": os.getenv("SSRI_DEM_PROVIDER", "auto"),
        "label_semantics": {
            "landslide": (
                "1=USGS inventory presence; 0=documented pseudo-absence "
                "(full-inventory exclusion buffer)"
            ),
            "subsidence": "missing (nodata / mask=0)",
            "liquefaction": "missing (nodata / mask=0)",
        },
        "gravity_source": gravity_source,
        "gravity_source_note": (
            "Not EIGEN-6C4 unless SSRI_GRAVITY_SOURCE=eigen6c4 and "
            "EIGEN6C4_DATA_PATH points to a real EIGEN-6C4 raster."
        ),
        "magnetic_source": "EMAG2v3 UC 4km (CONUS GeoTIFF clip)",
        "channel_count": 13,
        "resolution_m": args.resolution_m,
        "sampling": {
            "n_positives": len(positives),
            "n_absences": len(absences),
            "min_absence_km": args.min_absence_km,
            "max_absence_km": args.max_absence_km,
            "min_inter_absence_km": args.min_inter_absence_km,
            "min_positive_separation_km": args.min_positive_separation_km,
        },
        "notes": [
            "Expanded source pilot relative to v2 (n=80).",
            "Pseudo-absences use full CONUS inventory exclusion buffer.",
            "Baseline experiment 20260909T001911Z preserved; do not overwrite.",
        ],
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info(
        "Dataset complete: built=%s reused=%s failed=%s splits=%s",
        len(built),
        len(reused),
        len(failed),
        {k: len(v) for k, v in final_splits.items()},
    )
    return output_root


def _compute_channel_stats(samples_root: Path, train_ids: list[str]) -> dict[str, Any]:
    sums = None
    sq_sums = None
    counts = None
    for sid in train_ids:
        path = samples_root / sid / "feature_stack.npy"
        if not path.exists():
            continue
        arr = np.load(path)
        flat = arr.reshape(arr.shape[0], -1)
        valid = np.isfinite(flat)
        if sums is None:
            c = arr.shape[0]
            sums = np.zeros(c, dtype=np.float64)
            sq_sums = np.zeros(c, dtype=np.float64)
            counts = np.zeros(c, dtype=np.float64)
        for ch in range(arr.shape[0]):
            vals = flat[ch][valid[ch]]
            if vals.size == 0:
                continue
            sums[ch] += float(vals.sum())
            sq_sums[ch] += float((vals.astype(np.float64) ** 2).sum())
            counts[ch] += float(vals.size)
    if sums is None or counts is None or sq_sums is None:
        return {"channels": [], "mean": [], "std": []}
    mean = sums / np.maximum(counts, 1.0)
    var = sq_sums / np.maximum(counts, 1.0) - mean**2
    std = np.sqrt(np.maximum(var, 1e-12))
    from ssri_model.data.feature_engineering import CHANNEL_ORDER

    return {
        "channels": list(CHANNEL_ORDER),
        "mean": mean.tolist(),
        "std": std.tolist(),
        "count_pixels_per_channel": counts.tolist(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reuse-from", type=Path, default=None)
    parser.add_argument("--n-positives", type=int, default=120)
    parser.add_argument("--n-absences", type=int, default=120)
    parser.add_argument("--min-absence-km", type=float, default=15.0)
    parser.add_argument("--max-absence-km", type=float, default=100.0)
    parser.add_argument("--min-inter-absence-km", type=float, default=5.0)
    parser.add_argument("--min-positive-separation-km", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--start-date", default="2023-01-01")
    parser.add_argument("--end-date", default="2023-12-31")
    parser.add_argument("--resolution-m", type=float, default=30.0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    build_dataset(args)


if __name__ == "__main__":
    main()
