"""Build terrain-first CONUS susceptibility corpus from USGS + Copernicus DEM."""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CATALOG,
    CONFIG,
    CORPUS,
    FEATURE_NAMES,
    OUT,
    PROTOCOL_V2,
    append_log,
    block5,
    haversine_km,
    sha256_file,
    write_json,
)


def load_catalog_points() -> list[dict]:
    rows = []
    with CATALOG.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            o = json.loads(line)
            lat, lon = o.get("latitude"), o.get("longitude")
            if lat is None or lon is None:
                continue
            c = CONFIG["conus"]
            if not (c["lat_min"] <= lat <= c["lat_max"] and c["lon_min"] <= lon <= c["lon_max"]):
                continue
            q = "|".join(o.get("quality_flags") or [])
            # skip lowest confidence if flagged
            if "confidence=1" in q or "confidence=2" in q:
                continue
            source = None
            for flag in o.get("quality_flags") or []:
                if flag.startswith("src=") or flag.startswith("source="):
                    source = flag.split("=", 1)[1]
            if source is None:
                source = str(o.get("inventory_id") or o.get("dataset_name") or "unknown")
            rows.append(
                {
                    "sample_id": o.get("sample_id") or f"usgs-{i}",
                    "lat": float(lat),
                    "lon": float(lon),
                    "y": 1,
                    "source": source,
                    "timestamp": o.get("timestamp"),
                    "block": block5(float(lat), float(lon)),
                }
            )
    return rows


def thin_km(points: list[dict], min_km: float, rng: np.random.Generator) -> list[dict]:
    """Greedy thinning with grid index (~1 km cells) for speed."""
    order = rng.permutation(len(points))
    kept: list[dict] = []
    # cell size ~ min_km in degrees (lat)
    cell = max(min_km / 111.0, 0.005)
    grid: dict[tuple[int, int], list[tuple[float, float]]] = defaultdict(list)
    for idx in order:
        p = points[idx]
        gi, gj = int(math.floor(p["lat"] / cell)), int(math.floor(p["lon"] / cell))
        ok = True
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for lat, lon in grid.get((gi + di, gj + dj), []):
                    if haversine_km(p["lat"], p["lon"], lat, lon) < min_km:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            kept.append(p)
            grid[(gi, gj)].append((p["lat"], p["lon"]))
    return kept


def cap_source_share(points: list[dict], max_share: float, rng: np.random.Generator) -> list[dict]:
    by_b: dict[str, list[dict]] = defaultdict(list)
    for p in points:
        by_b[p["block"]].append(p)
    out: list[dict] = []
    for b, pts in by_b.items():
        by_s: dict[str, list[dict]] = defaultdict(list)
        for p in pts:
            by_s[p["source"]].append(p)
        capped: list[dict] = []
        n = len(pts)
        limit = max(1, int(math.floor(max_share * n)))
        for src, sp in by_s.items():
            if len(sp) <= limit:
                capped.extend(sp)
            else:
                pick = rng.choice(len(sp), size=limit, replace=False)
                capped.extend([sp[i] for i in pick])
        out.extend(capped)
    return out


def inventory_xy(points: list[dict]) -> np.ndarray:
    return np.asarray([[p["lat"], p["lon"]] for p in points], dtype=np.float64)


def min_dist_km(lat: float, lon: float, xy: np.ndarray) -> float:
    # coarse filter
    lat_pad = 1.5
    lon_pad = 1.5
    mask = (np.abs(xy[:, 0] - lat) <= lat_pad) & (np.abs(xy[:, 1] - lon) <= lon_pad)
    subset = xy[mask] if np.any(mask) else xy[:5000]  # fallback subsample
    if len(subset) == 0:
        subset = xy
    return min(haversine_km(lat, lon, float(r[0]), float(r[1])) for r in subset)


def block_footprint(presences: list[dict], block: str) -> tuple[float, float, float, float]:
    pts = [p for p in presences if p["block"] == block]
    if not pts:
        # parse block bounds
        la, lo = (int(x) for x in block.split("_"))
        return float(lo), float(la), float(lo + 5), float(la + 5)
    lats = [p["lat"] for p in pts]
    lons = [p["lon"] for p in pts]
    # expand 0.3 deg
    return min(lons) - 0.3, min(lats) - 0.3, max(lons) + 0.3, max(lats) + 0.3


def sample_absences(
    presences: list[dict],
    full_inventory: np.ndarray,
    scheme: str,
    n_target: int,
    rng: np.random.Generator,
) -> list[dict]:
    near = CONFIG["absence_near_km"]
    far_min = CONFIG["absence_far_min_km"]
    blocks = sorted({p["block"] for p in presences})
    out: list[dict] = []
    attempts = 0
    max_attempts = n_target * 80
    while len(out) < n_target and attempts < max_attempts:
        attempts += 1
        b = blocks[int(rng.integers(0, len(blocks)))]
        west, south, east, north = block_footprint(presences, b)
        lat = float(rng.uniform(south, north))
        lon = float(rng.uniform(west, east))
        if block5(lat, lon) != b:
            continue
        d = min_dist_km(lat, lon, full_inventory)
        if scheme == "NEAR" and not (near[0] <= d <= near[1]):
            continue
        if scheme == "FAR" and d < far_min:
            continue
        out.append(
            {
                "sample_id": f"abs-{scheme.lower()}-{len(out):05d}",
                "lat": lat,
                "lon": lon,
                "y": 0,
                "source": f"pseudo_{scheme.lower()}",
                "timestamp": None,
                "block": b,
                "dist_to_inventory_km": d,
                "absence_scheme": scheme,
            }
        )
    return out


def assign_splits(blocks: list[str], rng: np.random.Generator) -> dict[str, str]:
    """Assign whole 5° cells to train/val/test."""
    blocks = sorted(blocks)
    rng.shuffle(blocks)
    n = len(blocks)
    if n < 8:
        raise RuntimeError(f"Need >=8 populated blocks, got {n}")
    n_test = max(3, int(round(0.25 * n)))
    n_val = max(1, int(round(0.15 * n)))
    n_train = n - n_test - n_val
    if n_train < 3:
        n_test = 3
        n_val = max(1, n - n_test - 3)
        n_train = n - n_test - n_val
    roles = (
        ["test"] * n_test + ["validation"] * n_val + ["train"] * n_train
    )
    rng.shuffle(roles)
    # ensure counts
    while len(roles) < n:
        roles.append("train")
    roles = roles[:n]
    return {b: roles[i] for i, b in enumerate(blocks)}


def apply_buffer(samples: list[dict], split_of: dict[str, str]) -> tuple[list[dict], dict]:
    buf = CONFIG["train_test_buffer_km"]
    test = [s for s in samples if split_of[s["block"]] == "test"]
    kept = []
    dropped_trainval = 0
    dropped_test = 0
    for s in samples:
        role = split_of[s["block"]]
        if role == "test":
            # drop test if too close to any train/val that we will keep — first pass keep all non-test filtered
            kept.append(s)
            continue
        too_close = any(
            haversine_km(s["lat"], s["lon"], t["lat"], t["lon"]) < buf for t in test
        )
        if too_close:
            dropped_trainval += 1
            continue
        kept.append(s)
    # second pass: drop test samples too close to remaining train/val
    trainval = [s for s in kept if split_of[s["block"]] != "test"]
    final = []
    for s in kept:
        if split_of[s["block"]] != "test":
            final.append(s)
            continue
        too_close = any(
            haversine_km(s["lat"], s["lon"], t["lat"], t["lon"]) < buf for t in trainval
        )
        if too_close:
            dropped_test += 1
            continue
        final.append(s)
    return final, {
        "buffer_km": buf,
        "dropped_trainval": dropped_trainval,
        "dropped_test": dropped_test,
        "n_before": len(samples),
        "n_after": len(final),
    }


def compute_features_from_dem(dem: np.ndarray, res_m: float) -> dict[str, float] | None:
    """dem: 2D float with nan for voids; center pixel is point."""
    if dem.ndim != 2:
        return None
    valid = np.isfinite(dem)
    void_frac = 1.0 - valid.mean()
    if void_frac > CONFIG["max_void_frac"]:
        return None
    # fill nan with nanmean for gradient stability but track
    fill = np.nanmean(dem)
    if not np.isfinite(fill):
        return None
    z = np.where(valid, dem, fill)
    gy, gx = np.gradient(z, res_m, res_m)
    slope_rad = np.arctan(np.hypot(gx, gy))
    slope_deg = np.degrees(slope_rad)
    aspect = np.arctan2(-gx, gy)
    # curvatures (Zevenbergen-Thorne-ish simple)
    zyy, zyx = np.gradient(gy, res_m, res_m)
    zxy, zxx = np.gradient(gx, res_m, res_m)
    p = gx
    q = gy
    plan = np.zeros_like(z)
    profile = np.zeros_like(z)
    denom = np.maximum(p * p + q * q, 1e-12)
    plan = -(zxx * q * q - 2 * zxy * p * q + zyy * p * p) / np.power(denom, 1.5)
    profile = -(zxx * p * p + 2 * zxy * p * q + zyy * q * q) / (
        denom * np.power(1 + denom, 1.5)
    )
    # TWI approx
    # local upstream proxy: relative elevation inverted
    a = (np.nanmax(z) - z + 1.0)
    twi = np.log(np.maximum(a, 1e-3) / np.maximum(np.tan(slope_rad), 1e-6))
    cy, cx = dem.shape[0] // 2, dem.shape[1] // 2
    elev = float(dem[cy, cx]) if np.isfinite(dem[cy, cx]) else float(z[cy, cx])
    return {
        "elevation": elev,
        "slope": float(slope_deg[cy, cx]),
        "aspect_sin": float(np.sin(aspect[cy, cx])),
        "aspect_cos": float(np.cos(aspect[cy, cx])),
        "plan_curvature": float(plan[cy, cx]),
        "profile_curvature": float(profile[cy, cx]),
        "twi": float(twi[cy, cx]),
        "relative_relief_1km": float(np.nanmax(dem) - np.nanmin(dem)),
        "valley_depth": float(elev - np.nanmin(dem)),
        "tpi": float(elev - np.nanmean(dem)),
        "void_frac": float(void_frac),
    }


_TILE_SRC: dict[str, object] = {}
_STAC = None


def _stac():
    global _STAC
    if _STAC is None:
        import planetary_computer
        import pystac_client

        _STAC = pystac_client.Client.open(
            CONFIG["stac_url"],
            modifier=planetary_computer.sign_inplace,
        )
    return _STAC


def _open_dem_tile(lat: float, lon: float):
    """Open (and cache) the Copernicus DEM COG covering this point."""
    import rasterio

    # GLO-30 tiles are 1°; use floor
    tlat, tlon = math.floor(lat), math.floor(lon)
    key = f"{tlat}_{tlon}"
    if key in _TILE_SRC:
        return _TILE_SRC[key]
    bbox = (tlon + 0.1, tlat + 0.1, tlon + 0.9, tlat + 0.9)
    items = list(
        _stac().search(collections=[CONFIG["dem_collection"]], bbox=bbox, max_items=3).items()
    )
    if not items:
        _TILE_SRC[key] = None
        return None
    asset = items[0].assets.get("data") or next(iter(items[0].assets.values()))
    src = rasterio.open(asset.href)
    _TILE_SRC[key] = src
    return src


def fetch_dem_window(lat: float, lon: float) -> tuple[np.ndarray, float] | None:
    """Return (dem_array, res_m) centered on lon/lat via Planetary Computer."""
    from rasterio.warp import transform as warp_xy
    from rasterio.windows import Window

    half = CONFIG["window_half_m"]
    res = CONFIG["dem_resolution_m"]
    n = int(round(2 * half / res))
    try:
        src = _open_dem_tile(lat, lon)
        if src is None:
            return None
        xs, ys = warp_xy("EPSG:4326", src.crs, [lon], [lat])
        row, col = src.index(xs[0], ys[0])
        r0 = int(row) - n // 2
        c0 = int(col) - n // 2
        r0 = max(0, min(r0, src.height - n))
        c0 = max(0, min(c0, src.width - n))
        if n > src.height or n > src.width:
            return None
        window = Window(c0, r0, n, n)
        dem = src.read(1, window=window).astype(np.float64)
        nodata = src.nodata
        if nodata is not None:
            dem[dem == nodata] = np.nan
        dem[~np.isfinite(dem)] = np.nan
        dem[(dem < -500) | (dem > 9000)] = np.nan
        return dem, res
    except Exception as exc:  # noqa: BLE001
        append_log(f"DEM_FAIL {lat},{lon} {type(exc).__name__}: {exc}")
        return None


def enrich_features(samples: list[dict]) -> tuple[list[dict], dict]:
    ok = []
    failed = 0
    void_drop = 0
    for i, s in enumerate(samples):
        got = fetch_dem_window(s["lat"], s["lon"])
        if got is None:
            failed += 1
            continue
        dem, res = got
        feats = compute_features_from_dem(dem, res)
        if feats is None:
            void_drop += 1
            continue
        row = dict(s)
        row["features"] = {k: feats[k] for k in FEATURE_NAMES}
        row["void_frac"] = feats["void_frac"]
        ok.append(row)
        if (i + 1) % 50 == 0:
            print(f"features {i+1}/{len(samples)} ok={len(ok)} fail={failed} void={void_drop}", flush=True)
    return ok, {"dem_fail": failed, "void_drop": void_drop, "n_ok": len(ok)}


def main() -> int:
    append_log("START build_corpus")
    rng = np.random.default_rng(CONFIG["seed"])
    protocol_sha = sha256_file(PROTOCOL_V2)
    print("loading catalog...", flush=True)
    catalog = load_catalog_points()
    n0 = len(catalog)
    print(f"catalog conus filtered {n0}", flush=True)

    # subsample candidates before expensive thinning if huge
    if n0 > 50000:
        idx = rng.choice(n0, size=50000, replace=False)
        catalog = [catalog[i] for i in idx]
    n_before_thin = len(catalog)
    thinned = thin_km(catalog, CONFIG["min_presence_separation_km"], rng)
    capped = cap_source_share(thinned, CONFIG["max_source_share_per_block"], rng)
    # target presence count
    if len(capped) > CONFIG["target_n_presence"]:
        pick = rng.choice(len(capped), size=CONFIG["target_n_presence"], replace=False)
        presences = [capped[i] for i in pick]
    else:
        presences = capped
    for p in presences:
        p["absence_scheme"] = None
        p["role_label"] = "presence"

    print(
        f"presence before_thin={n_before_thin} after_thin={len(thinned)} "
        f"after_cap={len(capped)} selected={len(presences)}",
        flush=True,
    )

    # full inventory for distance (use thinned+original subsample for speed)
    full_xy = inventory_xy(thinned if len(thinned) > 1000 else catalog)
    print("sampling NEAR absences...", flush=True)
    abs_near = sample_absences(presences, full_xy, "NEAR", CONFIG["target_n_absence_near"], rng)
    print(f"NEAR absences {len(abs_near)}", flush=True)
    print("sampling FAR absences...", flush=True)
    abs_far = sample_absences(presences, full_xy, "FAR", CONFIG["target_n_absence_far"], rng)
    print(f"FAR absences {len(abs_far)}", flush=True)

    # Primary corpus = presence + NEAR; FAR stored separately for dual eval
    primary = presences + abs_near
    blocks = sorted({p["block"] for p in primary})
    print(f"populated blocks {len(blocks)}", flush=True)
    if len(blocks) < 8:
        write_json(
            OUT / "phase2_build.json",
            {
                "status": "BLOCKED",
                "reason": f"Only {len(blocks)} populated 5° blocks (<8)",
                "n_presence": len(presences),
                "n_near": len(abs_near),
            },
        )
        append_log("BLOCKED too_few_blocks")
        return 2

    split_of = assign_splits(blocks, rng)
    buffered, buffer_log = apply_buffer(primary, split_of)
    print(f"after buffer {len(buffered)} log={buffer_log}", flush=True)

    # Also attach FAR with same split map for secondary eval (buffer separately)
    far_buffered, far_buf_log = apply_buffer(presences + abs_far, split_of)

    # Features for primary and far sets
    print("fetching DEM + features (primary)...", flush=True)
    primary_feat, feat_log = enrich_features(buffered)
    print("fetching DEM + features (FAR set)...", flush=True)
    far_feat, far_feat_log = enrich_features(far_buffered)

    # Assign split labels
    for s in primary_feat + far_feat:
        s["split"] = split_of[s["block"]]

    # Disjointness checks
    roles = defaultdict(set)
    for s in primary_feat:
        roles[s["split"]].add(s["block"])
    overlap_tv = roles["train"] & roles["validation"]
    overlap_tt = roles["train"] & roles["test"]
    overlap_vt = roles["validation"] & roles["test"]
    assert not overlap_tt, f"train/test block overlap {overlap_tt}"
    assert not overlap_vt, f"val/test block overlap {overlap_vt}"

    # min NN train-test
    train_pts = [s for s in primary_feat if s["split"] == "train"]
    test_pts = [s for s in primary_feat if s["split"] == "test"]
    nn = []
    for t in test_pts:
        dmin = min(haversine_km(t["lat"], t["lon"], u["lat"], u["lon"]) for u in train_pts) if train_pts else None
        if dmin is not None:
            nn.append(dmin)
    min_nn = float(min(nn)) if nn else None
    assert min_nn is None or min_nn >= CONFIG["train_test_buffer_km"] - 1e-6, min_nn

    # Persist tables
    def rows_for(samples: list[dict]) -> list[dict]:
        out = []
        for s in samples:
            out.append(
                {
                    "sample_id": s["sample_id"],
                    "lat": s["lat"],
                    "lon": s["lon"],
                    "y": s["y"],
                    "block": s["block"],
                    "split": s["split"],
                    "source": s.get("source"),
                    "absence_scheme": s.get("absence_scheme"),
                    "timestamp": s.get("timestamp"),
                    "void_frac": s.get("void_frac"),
                    **{f"f_{k}": s["features"][k] for k in FEATURE_NAMES},
                }
            )
        return out

    primary_path = CORPUS / "samples_near.jsonl"
    far_path = CORPUS / "samples_far.jsonl"
    with primary_path.open("w", encoding="utf-8") as f:
        for row in rows_for(primary_feat):
            f.write(json.dumps(row) + "\n")
    with far_path.open("w", encoding="utf-8") as f:
        for row in rows_for(far_feat):
            f.write(json.dumps(row) + "\n")

    # channel audit
    channel_audit = {}
    for name in FEATURE_NAMES:
        vals = np.asarray([s["features"][name] for s in primary_feat], dtype=np.float64)
        channel_audit[name] = {
            "n": int(len(vals)),
            "frac_nan": float(np.isnan(vals).mean()) if len(vals) else 1.0,
            "frac_constant": float(np.nanmax(vals) - np.nanmin(vals) < 1e-12) if len(vals) else 1.0,
            "mean": float(np.nanmean(vals)) if len(vals) else None,
            "std": float(np.nanstd(vals)) if len(vals) else None,
        }

    prev_by_split = defaultdict(Counter)
    prev_by_block = defaultdict(Counter)
    for s in primary_feat:
        prev_by_split[s["split"]][s["y"]] += 1
        prev_by_block[s["block"]][s["y"]] += 1

    dated = sum(1 for s in primary_feat if s["y"] == 1 and s.get("timestamp"))
    n_pos = sum(1 for s in primary_feat if s["y"] == 1)

    status = "OK"
    if len(primary_feat) < CONFIG["min_total_after_filters"]:
        status = "BELOW_MINIMUM"
    if len({s["block"] for s in primary_feat}) < 8:
        status = "BLOCKED_BLOCKS"
    if len({s["block"] for s in primary_feat if s["split"] == "test"}) < 3:
        status = "BLOCKED_TEST_BLOCKS"

    file_hashes = {
        "samples_near.jsonl": sha256_file(primary_path),
        "samples_far.jsonl": sha256_file(far_path),
        "PROTOCOL_v2.md": protocol_sha,
        "config.json": sha256_file(Path(__file__).resolve().parents[1] / "config.json"),
    }

    manifest = {
        "status": status,
        "protocol_v2_sha256": protocol_sha,
        "n_primary": len(primary_feat),
        "n_far_set": len(far_feat),
        "counts": {
            "catalog_filtered": n0,
            "before_thin": n_before_thin,
            "after_thin": len(thinned),
            "after_source_cap": len(capped),
            "presence_selected": len(presences),
            "absence_near_sampled": len(abs_near),
            "absence_far_sampled": len(abs_far),
            "after_buffer_primary": buffer_log,
            "feature_log_primary": feat_log,
            "feature_log_far": far_feat_log,
        },
        "split_of_blocks": split_of,
        "blocks_by_split": {k: sorted(v) for k, v in roles.items()},
        "min_train_test_nn_km": min_nn,
        "channel_audit": channel_audit,
        "prevalence_by_split": {k: dict(v) for k, v in prev_by_split.items()},
        "prevalence_by_block": {k: dict(v) for k, v in prev_by_block.items()},
        "frac_presences_dated": (dated / n_pos) if n_pos else None,
        "dropped_features": [
            "ndvi",
            "ndwi",
            "clay_mineral_ratio",
            "iron_oxide_index",
            "gravity",
            "magnetics",
            "sentinel",
            "event_date_features",
        ],
        "file_hashes": file_hashes,
        "primary_absence_scheme": "NEAR",
    }
    write_json(CORPUS / "manifest.json", manifest)
    write_json(OUT / "phase2_build.json", manifest)
    # freeze copy
    write_json(OUT / "phase2_corpus_freeze.json", {
        "frozen": True,
        "manifest_sha256": sha256_file(CORPUS / "manifest.json"),
        **file_hashes,
        "status": status,
        "n_primary": len(primary_feat),
    })
    append_log(f"END build_corpus status={status} n={len(primary_feat)}")
    print(json.dumps({"status": status, "n_primary": len(primary_feat), "min_nn": min_nn, "blocks": len(blocks)}, indent=2))
    return 0 if status in ("OK", "BELOW_MINIMUM") else 2


if __name__ == "__main__":
    raise SystemExit(main())
