"""Extend v2 corpus: slope-matched absences + sealed fresh holdout blocks."""
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
    CORPUS,
    FEATURE_NAMES,
    OUT,
    PROTOCOL_V3,
    REPO,
    SEALED_FRESH,
    SPENT_V2_TEST,
    V2,
    append_log,
    block5,
    haversine_km,
    load_jsonl,
    sha256_file,
    write_json,
)

# Load v2 build_corpus helpers without shadowing this package's common.py.
# v3 already imported `common`; clear the cache so v2 gets its own common.
import importlib.util

_v3_common = sys.modules["common"]
_v2_scripts = str(V2 / "scripts")
sys.path.insert(0, _v2_scripts)
del sys.modules["common"]
_v2_path = V2 / "scripts" / "build_corpus.py"
_spec = importlib.util.spec_from_file_location("v2_build_corpus", _v2_path)
_v2 = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_v2)
# Keep v2's common under an alias; restore v3 as `common` for this package.
sys.modules["v2_common"] = sys.modules.pop("common")
sys.modules["common"] = _v3_common
compute_features_from_dem = _v2.compute_features_from_dem
fetch_dem_window = _v2.fetch_dem_window
load_catalog_points = _v2.load_catalog_points
thin_km = _v2.thin_km
inventory_xy = _v2.inventory_xy
min_dist_km = _v2.min_dist_km


def enrich(samples: list[dict]) -> tuple[list[dict], dict]:
    ok, fail, void = [], 0, 0
    for i, s in enumerate(samples):
        got = fetch_dem_window(s["lat"], s["lon"])
        if got is None:
            fail += 1
            continue
        dem, res = got
        feats = compute_features_from_dem(dem, res)
        if feats is None:
            void += 1
            continue
        row = dict(s)
        for k in FEATURE_NAMES:
            row[f"f_{k}"] = feats[k]
        row["void_frac"] = feats["void_frac"]
        ok.append(row)
        if (i + 1) % 40 == 0:
            print(f"  features {i+1}/{len(samples)} ok={len(ok)} fail={fail}", flush=True)
    return ok, {"fail": fail, "void": void, "ok": len(ok)}


def sample_slope_matched(
    presences: list[dict],
    absence_pool: list[dict],
    n_target: int,
    rng: np.random.Generator,
) -> list[dict]:
    """Resample existing absences so slope bins match presence slope distribution.

    Uses already-enriched DEM features only (no new network DEM fetches). Protocol
    requires slope-distribution matching via terrain bins; distance scheme is separate.
    """
    pos_slopes = np.asarray([float(p["f_slope"]) for p in presences if "f_slope" in p], float)
    if len(pos_slopes) < 20:
        return []
    bins = np.unique(np.quantile(pos_slopes, np.linspace(0, 1, 6)))
    if len(bins) < 3:
        bins = np.array([0.0, 5.0, 10.0, 20.0, 90.0])
    edges = bins[1:-1]

    pos_bin = np.digitize(pos_slopes, edges, right=True)
    target_per = Counter(pos_bin.tolist())
    total = sum(target_per.values()) or 1
    for k in list(target_per):
        target_per[k] = max(1, int(round(n_target * target_per[k] / total)))

    pool_by_bin: dict[int, list[dict]] = defaultdict(list)
    for a in absence_pool:
        if a.get("y") != 0 or "f_slope" not in a:
            continue
        bidx = int(np.digitize([float(a["f_slope"])], edges, right=True)[0])
        pool_by_bin[bidx].append(a)

    out: list[dict] = []
    for bidx, need in sorted(target_per.items()):
        pool = pool_by_bin.get(bidx, [])
        if not pool:
            continue
        replace = len(pool) < need
        pick = rng.choice(len(pool), size=need, replace=replace)
        for j, idx in enumerate(pick):
            src = pool[int(idx)]
            row = dict(src)
            row["sample_id"] = f"abs-slope-{bidx}-{j:04d}-{src.get('sample_id', 'x')}"
            row["y"] = 0
            row["source"] = "pseudo_slope_matched_resample"
            row["absence_scheme"] = "SLOPE_MATCHED"
            row["split"] = "lobo"
            out.append(row)
    print(
        f"  slope-matched resampled {len(out)} from pool={len(absence_pool)} "
        f"bins={dict(target_per)} available={[len(pool_by_bin[k]) for k in sorted(target_per)]}",
        flush=True,
    )
    return out

def build_fresh_holdout(rng: np.random.Generator) -> tuple[list[dict], dict]:
    """Populate sealed blocks from catalog + NEAR absences."""
    catalog = load_catalog_points()
    # include AK/HI/PR ranges in catalog load — load_catalog_points is CONUS-only!
    # Extend: read catalog with wider bounds for sealed blocks
    extra = []
    with CATALOG.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            o = json.loads(line)
            lat, lon = o.get("latitude"), o.get("longitude")
            if lat is None or lon is None:
                continue
            b = block5(float(lat), float(lon))
            if b not in SEALED_FRESH:
                continue
            q = "|".join(o.get("quality_flags") or [])
            if "confidence=1" in q or "confidence=2" in q:
                continue
            extra.append(
                {
                    "sample_id": o.get("sample_id") or f"fresh-{i}",
                    "lat": float(lat),
                    "lon": float(lon),
                    "y": 1,
                    "block": b,
                    "source": "usgs",
                    "absence_scheme": None,
                    "timestamp": o.get("timestamp"),
                    "split": "sealed_fresh",
                }
            )
    # also CONUS sealed from filtered catalog
    for p in catalog:
        if p["block"] in SEALED_FRESH:
            extra.append(
                {
                    **{k: p[k] for k in ("sample_id", "lat", "lon", "y", "block", "source", "timestamp")},
                    "absence_scheme": None,
                    "split": "sealed_fresh",
                }
            )
    # dedupe by sample_id
    by_id = {p["sample_id"]: p for p in extra}
    extra = list(by_id.values())
    thinned = thin_km(extra, 1.0, rng)
    # cap per block
    by_b = defaultdict(list)
    for p in thinned:
        by_b[p["block"]].append(p)
    presences = []
    for b, pts in by_b.items():
        if len(pts) > 80:
            pick = rng.choice(len(pts), size=80, replace=False)
            pts = [pts[i] for i in pick]
        for p in pts:
            p["split"] = "sealed_fresh"
            p["absence_scheme"] = None
            p["y"] = 1
        presences.extend(pts)

    # NEAR absences inside sealed blocks
    inv = inventory_xy(thinned) if thinned else np.zeros((0, 2))
    absences = []
    for b, pts in by_b.items():
        if not pts:
            continue
        lats = [p["lat"] for p in pts]
        lons = [p["lon"] for p in pts]
        west, south, east, north = min(lons) - 0.3, min(lats) - 0.3, max(lons) + 0.3, max(lats) + 0.3
        n_abs = min(len(pts), 80)
        tries = 0
        while len([a for a in absences if a["block"] == b]) < n_abs and tries < n_abs * 80:
            tries += 1
            lat = float(rng.uniform(south, north))
            lon = float(rng.uniform(west, east))
            if block5(lat, lon) != b:
                continue
            if len(inv) and min_dist_km(lat, lon, inv) < 5:
                continue
            if len(inv):
                d = min_dist_km(lat, lon, inv)
                if not (5 <= d <= 20):
                    continue
            absences.append(
                {
                    "sample_id": f"fresh-abs-{b}-{tries}",
                    "lat": lat,
                    "lon": lon,
                    "y": 0,
                    "block": b,
                    "source": "pseudo_near_fresh",
                    "absence_scheme": "NEAR",
                    "timestamp": None,
                    "split": "sealed_fresh",
                }
            )

    samples = presences + absences
    print(f"fresh candidates before DEM: {len(samples)} blocks={sorted({s['block'] for s in samples})}", flush=True)
    feat, log = enrich(samples)
    # require both classes per block
    usable_blocks = []
    for b in sorted({s["block"] for s in feat}):
        sub = [s for s in feat if s["block"] == b]
        if sum(s["y"] for s in sub) > 0 and sum(1 - s["y"] for s in sub) > 0:
            usable_blocks.append(b)
    feat = [s for s in feat if s["block"] in usable_blocks]
    meta = {
        "requested_blocks": SEALED_FRESH,
        "populated_blocks": usable_blocks,
        "n": len(feat),
        "feature_log": log,
        "meets_tier_b_min": len(usable_blocks) >= 3 and len(feat) >= 150,
    }
    return feat, meta


def main() -> int:
    append_log("START extend_corpus")
    rng = np.random.default_rng(42)
    v2_near = load_jsonl(V2 / "corpus" / "samples_near.jsonl")
    v2_far = load_jsonl(V2 / "corpus" / "samples_far.jsonl")
    # Tag schemes
    for r in v2_near:
        if r["y"] == 1:
            r["absence_scheme"] = None
            r["scheme_set"] = "NEAR"
        else:
            r["absence_scheme"] = "NEAR"
            r["scheme_set"] = "NEAR"
        r["role_pool"] = "lobo" if r["block"] not in SPENT_V2_TEST else "spent_v2_test"
        # keep original split for exploratory
        r["v2_split"] = r.get("split")
    for r in v2_far:
        if r["y"] == 0:
            r["absence_scheme"] = "FAR"
            r["scheme_set"] = "FAR"
        else:
            r["scheme_set"] = "FAR"
        r["role_pool"] = "lobo" if r["block"] not in SPENT_V2_TEST else "spent_v2_test"
        r["v2_split"] = r.get("split")

    print("building slope-matched absences...", flush=True)
    # Use NEAR presence rows for slope matching targets
    pres = [r for r in v2_near if r["y"] == 1 and r["role_pool"] == "lobo"]
    # Resample from already-enriched NEAR+FAR absences (no new DEM)
    abs_pool = [r for r in v2_near + v2_far if r["y"] == 0]
    slope_abs = sample_slope_matched(pres, abs_pool, n_target=min(800, len(pres)), rng=rng)
    for r in slope_abs:
        r["scheme_set"] = "SLOPE_MATCHED"
        r["role_pool"] = "lobo" if r["block"] not in SPENT_V2_TEST else "spent_v2_test"
        r["v2_split"] = None
        r["split"] = "lobo"
    print(f"slope-matched absences: {len(slope_abs)}", flush=True)

    print("building sealed fresh holdout...", flush=True)
    fresh, fresh_meta = build_fresh_holdout(rng)
    print(f"fresh meta: {fresh_meta}", flush=True)

    # Write scheme tables for LOBO (exclude sealed from LOBO)
    def write_scheme(name: str, rows: list[dict], path: Path):
        with path.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    near_lobo = [r for r in v2_near if r["role_pool"] == "lobo"]
    far_lobo = [r for r in v2_far if r["role_pool"] == "lobo"]
    # slope-matched: presences from near_lobo + slope abs
    slope_lobo = [r for r in near_lobo if r["y"] == 1] + slope_abs

    write_scheme("NEAR", near_lobo, CORPUS / "lobo_near.jsonl")
    write_scheme("FAR", far_lobo, CORPUS / "lobo_far.jsonl")
    write_scheme("SLOPE_MATCHED", slope_lobo, CORPUS / "lobo_slope_matched.jsonl")
    write_scheme("SPENT", [r for r in v2_near if r["role_pool"] == "spent_v2_test"], CORPUS / "spent_v2_near.jsonl")
    write_scheme("SEALED", fresh, CORPUS / "sealed_fresh.jsonl")

    # Channel audit on near_lobo
    channel_audit = {}
    for name in FEATURE_NAMES:
        vals = np.asarray([r[f"f_{name}"] for r in near_lobo], float)
        channel_audit[name] = {
            "frac_nan": float(np.isnan(vals).mean()),
            "frac_constant": float((np.nanmax(vals) - np.nanmin(vals)) < 1e-12) if len(vals) else 1.0,
            "mean": float(np.nanmean(vals)),
            "std": float(np.nanstd(vals)),
        }

    files = {
        "lobo_near.jsonl": sha256_file(CORPUS / "lobo_near.jsonl"),
        "lobo_far.jsonl": sha256_file(CORPUS / "lobo_far.jsonl"),
        "lobo_slope_matched.jsonl": sha256_file(CORPUS / "lobo_slope_matched.jsonl"),
        "spent_v2_near.jsonl": sha256_file(CORPUS / "spent_v2_near.jsonl"),
        "sealed_fresh.jsonl": sha256_file(CORPUS / "sealed_fresh.jsonl"),
        "PROTOCOL_v3.md": sha256_file(PROTOCOL_V3),
    }
    manifest = {
        "protocol_v3_sha256": files["PROTOCOL_v3.md"],
        "v2_manifest_sha256": sha256_file(V2 / "corpus" / "manifest.json"),
        "n_lobo_near": len(near_lobo),
        "n_lobo_far": len(far_lobo),
        "n_lobo_slope_matched": len(slope_lobo),
        "n_spent_v2": sum(1 for r in v2_near if r["role_pool"] == "spent_v2_test"),
        "fresh_holdout": fresh_meta,
        "lobo_blocks": sorted({r["block"] for r in near_lobo}),
        "spent_blocks": sorted(SPENT_V2_TEST),
        "channel_audit_lobo_near": channel_audit,
        "file_hashes": files,
        "environment_layers": {
            "status": "NOT_ATTACHED_IN_BUILD",
            "note": "Layer rasters evaluated in train_eval only if free STAC fetch succeeds; otherwise layer steps BLOCKED with exact error",
        },
    }
    write_json(CORPUS / "manifest.json", manifest)
    write_json(OUT / "phase2_corpus.json", manifest)
    append_log(f"END extend_corpus fresh_ok={fresh_meta.get('meets_tier_b_min')}")
    print(json.dumps({"n_near": len(near_lobo), "n_slope": len(slope_lobo), "fresh": fresh_meta}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
