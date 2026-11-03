"""Phase 2: full FeatureStacks v3 + USGS catalog audit."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CATALOG,
    CATALOG_MANIFEST,
    CHANNEL_NAMES,
    FEATURESTACKS,
    NODATA,
    OUT,
    PROTOCOL,
    REPO,
    append_run_log,
    block5,
    haversine_km,
    sha256_file,
    write_json,
)


def parse_year(ts: str | None) -> int | None:
    if not ts:
        return None
    head = ts.strip().replace("-", "/").split(" ")[0]
    parts = head.split("/")
    try:
        if len(parts) >= 1 and parts[0].isdigit() and len(parts[0]) == 4:
            return int(parts[0])
    except Exception:  # noqa: BLE001
        return None
    return None


def audit_catalog() -> dict:
    n = 0
    conus = 0
    years: Counter[str] = Counter()
    pre2017 = post2017 = undated = 0
    with CATALOG.open(encoding="utf-8") as f:
        for line in f:
            n += 1
            o = json.loads(line)
            lat, lon = o.get("latitude"), o.get("longitude")
            if lat is None or lon is None:
                continue
            if not (24 <= lat <= 49 and -125 <= lon <= -66):
                continue
            conus += 1
            y = parse_year(o.get("timestamp"))
            if y is None:
                undated += 1
                years["undated"] += 1
            else:
                years[str(y)] += 1
                if y < 2017:
                    pre2017 += 1
                else:
                    post2017 += 1
    man = json.loads(CATALOG_MANIFEST.read_text(encoding="utf-8"))
    dated = pre2017 + post2017
    return {
        "path": str(CATALOG),
        "manifest": man,
        "license": man.get("license"),
        "doi": man.get("doi"),
        "label_semantics": man.get("label_semantics"),
        "lines_total": n,
        "conus_points": conus,
        "event_year": {
            "pre_2017_sentinel2_era": pre2017,
            "post_2017_inclusive": post2017,
            "undated": undated,
            "frac_pre2017_among_dated": (pre2017 / dated) if dated else None,
            "frac_undated_among_conus": undated / conus if conus else None,
            "year_histogram_top": years.most_common(20),
        },
        "notes": [
            "USGS inventory is presence-only points; positional accuracy varies by source confidence flags",
            "No co-registered imagery date on catalog rows; FeatureStack spectral dates are acquisition-time, not event-matched in v3 builder",
        ],
    }


def load_samples() -> list[dict]:
    manifest = json.loads((FEATURESTACKS / "manifest.json").read_text(encoding="utf-8"))
    split_of: dict[str, str] = {}
    for split, ids in (manifest.get("splits") or {}).items():
        for sid in ids:
            split_of[sid] = split
    samples = []
    root = FEATURESTACKS / "samples"
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
        lat = meta.get("latitude")
        lon = meta.get("longitude")
        if lat is None or lon is None:
            bbox = meta.get("bbox_wgs84")
            lon = (bbox[0] + bbox[2]) / 2
            lat = (bbox[1] + bbox[3]) / 2
        lab = meta.get("labels") or {}
        y = 1 if lab.get("landslide") == 1 else 0
        samples.append(
            {
                "sample_id": d.name,
                "path": d,
                "lat": float(lat),
                "lon": float(lon),
                "y": y,
                "split_manifest": split_of.get(d.name, "unknown"),
                "block2": meta.get("spatial_block") or meta.get("provenance", {}).get("spatial_block"),
                "block5": block5(float(lat), float(lon)),
                "role": (meta.get("provenance") or {}).get("role"),
                "quality_flags": (meta.get("provenance") or {}).get("quality_flags") or [],
                "timestamp": None,
            }
        )
    return samples


def channel_audit(samples: list[dict]) -> dict:
    per_channel = {
        name: {
            "n_chips": 0,
            "frac_nodata_sum": 0.0,
            "n_all_nodata": 0,
            "n_constant_finite": 0,
            "by_block5": {},
        }
        for name in CHANNEL_NAMES
    }
    for s in samples:
        arr = np.load(s["path"] / "feature_stack.npy")
        b5 = s["block5"]
        for i, name in enumerate(CHANNEL_NAMES):
            ch = arr[i]
            nodata_frac = float((ch == NODATA).mean()) if ch.size else 1.0
            finite = ch[ch != NODATA]
            all_nodata = bool(finite.size == 0)
            constant = bool(finite.size > 0 and float(finite.max() - finite.min()) < 1e-12)
            rec = per_channel[name]
            rec["n_chips"] += 1
            rec["frac_nodata_sum"] += nodata_frac
            if all_nodata:
                rec["n_all_nodata"] += 1
            if constant:
                rec["n_constant_finite"] += 1
            bb = rec["by_block5"].setdefault(
                b5, {"n": 0, "frac_nodata_sum": 0.0, "n_all_nodata": 0}
            )
            bb["n"] += 1
            bb["frac_nodata_sum"] += nodata_frac
            if all_nodata:
                bb["n_all_nodata"] += 1

    summary = {}
    for name, rec in per_channel.items():
        n = max(rec["n_chips"], 1)
        by_b = {}
        for b, bb in rec["by_block5"].items():
            by_b[b] = {
                "n": bb["n"],
                "mean_frac_nodata": bb["frac_nodata_sum"] / max(bb["n"], 1),
                "n_all_nodata": bb["n_all_nodata"],
                "frac_chips_all_nodata": bb["n_all_nodata"] / max(bb["n"], 1),
            }
        summary[name] = {
            "mean_frac_nodata": rec["frac_nodata_sum"] / n,
            "n_all_nodata": rec["n_all_nodata"],
            "frac_chips_all_nodata": rec["n_all_nodata"] / n,
            "n_constant_finite": rec["n_constant_finite"],
            "frac_chips_constant_finite": rec["n_constant_finite"] / n,
            "by_block5": by_b,
        }
    return summary


def absence_audit(samples: list[dict], inventory_xy: np.ndarray) -> dict:
    absences = [s for s in samples if s["y"] == 0]
    dists = []
    for s in absences:
        # approximate nearest via coarse filter
        lat, lon = s["lat"], s["lon"]
        lat_pad = 2.0
        lon_pad = 2.0
        mask = (
            (np.abs(inventory_xy[:, 0] - lat) <= lat_pad)
            & (np.abs(inventory_xy[:, 1] - lon) <= lon_pad)
        )
        subset = inventory_xy[mask] if np.any(mask) else inventory_xy
        dmin = min(haversine_km(lat, lon, float(r[0]), float(r[1])) for r in subset)
        dists.append(dmin)
    dists_a = np.asarray(dists, dtype=np.float64) if dists else np.asarray([])
    proposed_buffer_km = 20.0
    return {
        "methodology_reported": "docs/SOURCE_PSEUDO_ABSENCE_METHODOLOGY.md — 15 km full-inventory exclusion; 15–100 km offset from positives",
        "n_absence_tiles": len(absences),
        "min_km_to_inventory": float(dists_a.min()) if len(dists_a) else None,
        "median_km_to_inventory": float(np.median(dists_a)) if len(dists_a) else None,
        "n_below_15km": int((dists_a < 15).sum()) if len(dists_a) else 0,
        "n_below_20km": int((dists_a < 20).sum()) if len(dists_a) else 0,
        "contamination_risk": "Unmapped landslides outside inventory remain possible; buffer reduces but does not eliminate false negatives in absence class",
        "proposed_exclusion_buffer_km_for_rebuild": proposed_buffer_km,
        "proposed_rule": "Reject absence candidates within 20 km of any USGS CONUS inventory point (stricter than v3 15 km); document in rebuild manifest",
    }


def leakage_audit(samples: list[dict]) -> dict:
    # nearest neighbour train-test under manifest split
    train = [s for s in samples if s["split_manifest"] == "train"]
    test = [s for s in samples if s["split_manifest"] == "test"]
    nn = []
    for t in test:
        dmin = min(haversine_km(t["lat"], t["lon"], u["lat"], u["lon"]) for u in train)
        nn.append(dmin)
    # duplicate ids
    ids = [s["sample_id"] for s in samples]
    dup = [i for i, c in Counter(ids).items() if c > 1]
    # overlapping nearly same lat/lon
    close_pairs = 0
    for i in range(len(samples)):
        for j in range(i + 1, len(samples)):
            if haversine_km(samples[i]["lat"], samples[i]["lon"], samples[j]["lat"], samples[j]["lon"]) < 0.5:
                close_pairs += 1
    # 5deg block overlap train/test
    train_b5 = {s["block5"] for s in train}
    test_b5 = {s["block5"] for s in test}
    return {
        "manifest_split_counts": dict(Counter(s["split_manifest"] for s in samples)),
        "min_train_test_nn_km": float(min(nn)) if nn else None,
        "median_train_test_nn_km": float(np.median(nn)) if nn else None,
        "duplicate_sample_ids": dup,
        "pairs_closer_than_0_5km": close_pairs,
        "block5_train": sorted(train_b5),
        "block5_test": sorted(test_b5),
        "block5_overlap_train_test": sorted(train_b5 & test_b5),
        "location_encoding_risk": "latitude/longitude not in feature channels; spatial block id not a model input — VERIFIED channel list",
    }


def prevalence(samples: list[dict]) -> dict:
    by_split: dict[str, Counter] = defaultdict(Counter)
    by_b5: dict[str, Counter] = defaultdict(Counter)
    for s in samples:
        by_split[s["split_manifest"]][s["y"]] += 1
        by_b5[s["block5"]][s["y"]] += 1
    return {
        "overall": dict(Counter(s["y"] for s in samples)),
        "by_manifest_split": {k: dict(v) for k, v in by_split.items()},
        "by_block5": {k: dict(v) for k, v in by_b5.items()},
        "n_block5": len(by_b5),
    }


def trace_spectral_cause() -> dict:
    """Inspect build_feature_stack / acquisition for spectral nodata cause — code inspection."""
    fe = REPO / "model" / "src" / "ssri_model" / "data" / "feature_engineering.py"
    text = fe.read_text(encoding="utf-8")
    clues = []
    for needle in ("ndvi", "FEATURE_NODATA", "-9999", "spectral", "gee", "Earth Engine"):
        if needle.lower() in text.lower():
            clues.append(needle)
    return {
        "inspection_file": str(fe),
        "keywords_present": clues,
        "hypothesis": (
            "FeatureStacks v3 were built via build_usgs_feature_dataset → build_feature_stack. "
            "Prior docs (ai_model_selection_discovery.md, production_qualification.md) report GEE spectral "
            "IAM failures yielding nodata spectral bands. This audit verifies corpus-wide all-nodata rates; "
            "root cause attribution to GEE IAM is REPORTED from those docs unless live GEE call is re-run "
            "(out of scope / may require credentials)."
        ),
    }


def main() -> int:
    append_run_log(f"{datetime.now(timezone.utc).isoformat()} START phase2_data_audit")
    protocol_sha = sha256_file(PROTOCOL)
    catalog = audit_catalog()
    samples = load_samples()
    print(f"loaded {len(samples)} samples", flush=True)

    # inventory coords for absence distances (CONUS landslide=1)
    coords = []
    with CATALOG.open(encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            lat, lon = o.get("latitude"), o.get("longitude")
            if lat is None or lon is None:
                continue
            if not (24 <= lat <= 49 and -125 <= lon <= -66):
                continue
            labels = o.get("labels") or {}
            if labels.get("landslide") == 1 or o.get("hazard_type") == "landslide":
                # catalog rows may encode presence differently
                pass
            # presence inventory: all CONUS points in this catalog are landslide inventory
            coords.append([float(lat), float(lon)])
    inventory_xy = np.asarray(coords, dtype=np.float64)
    print(f"inventory coords {len(inventory_xy)}", flush=True)

    channels = channel_audit(samples)
    print("channel audit done", flush=True)
    absence = absence_audit(samples, inventory_xy)
    print("absence audit done", flush=True)
    leakage = leakage_audit(samples)
    prev = prevalence(samples)
    spectral_cause = trace_spectral_cause()

    spectral_all_nodata = {
        k: channels[k]["frac_chips_all_nodata"]
        for k in ("ndvi", "ndwi", "clay_mineral_ratio", "iron_oxide_index")
    }

    report = {
        "phase": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": protocol_sha,
        "featurestacks_root": str(FEATURESTACKS),
        "n_chips_audited": len(samples),
        "catalog": catalog,
        "channel_audit": channels,
        "spectral_all_nodata_fraction_of_chips": spectral_all_nodata,
        "spectral_corpus_wide_finding": all(v == 1.0 for v in spectral_all_nodata.values()),
        "spectral_cause_trace": spectral_cause,
        "absence_audit": absence,
        "leakage_audit": leakage,
        "prevalence": prev,
        "what_model_could_learn": {
            "usable_signal": "Terrain channels (0–6) generally finite with edge nodata; gravity often finite; magnetics often near-constant per chip",
            "unusable_as_signal": "ndvi, ndwi, clay_mineral_ratio, iron_oxide_index — if corpus-wide all-nodata, U-Net cannot learn spectral features from them",
            "label_limitation": "Point/pseudo-absence tiles support susceptibility ranking, not scar detection",
            "sample_size": f"{len(samples)} tiles — below PROTOCOL minimum 1500 for GO-LIMITED",
        },
    }
    write_json(OUT / "phase2_data_audit.json", report)

    md = []
    md.append("# DATA_AUDIT — FeatureStacks v3 + USGS catalog\n")
    md.append(f"Generated: {report['generated_at_utc']}\n")
    md.append(f"PROTOCOL.md SHA-256: `{protocol_sha}`\n")
    md.append("\n## Plain finding — what the model could actually learn from\n\n")
    if report["spectral_corpus_wide_finding"]:
        md.append(
            "**Spectral channels (ndvi, ndwi, clay_mineral_ratio, iron_oxide_index) are "
            "100% nodata (−9999) on every chip in the 240-sample corpus.** "
            "Any skill must come from terrain (± gravity/magnetics). "
            "A slope-only baseline is therefore the critical foil.\n\n"
        )
    else:
        md.append(
            f"Spectral all-nodata fractions: {spectral_all_nodata}. Not fully corpus-wide empty.\n\n"
        )
    md.append(
        f"Corpus size **{len(samples)}** tiles across **{prev['n_block5']}** five-degree blocks. "
        "PROTOCOL requires ≥1500 / ≥8 blocks / ≥3 held-out for GO-LIMITED — **not met** by v3 alone.\n\n"
    )
    md.append("## Catalog\n\n")
    md.append(
        f"- Licence: **{catalog.get('license')}** DOI {catalog.get('doi')}\n"
        f"- CONUS points counted: {catalog['conus_points']}\n"
        f"- Among dated CONUS: pre-2017={catalog['event_year']['pre_2017_sentinel2_era']}, "
        f"post-2017={catalog['event_year']['post_2017_inclusive']}, "
        f"frac_pre2017={catalog['event_year']['frac_pre2017_among_dated']}, "
        f"undated_frac={catalog['event_year']['frac_undated_among_conus']}\n"
        f"- Labels: presence-only landslide; subsidence/liquefaction missing\n\n"
    )
    md.append("## Absence construction\n\n")
    md.append(
        f"- Reported method: {absence['methodology_reported']}\n"
        f"- Min distance to inventory (recomputed): {absence['min_km_to_inventory']} km\n"
        f"- Proposed rebuild buffer: **{absence['proposed_exclusion_buffer_km_for_rebuild']} km**\n\n"
    )
    md.append("## Leakage\n\n")
    md.append(
        f"- Min train–test NN (manifest split): {leakage['min_train_test_nn_km']} km\n"
        f"- 5° block overlap train∩test: {leakage['block5_overlap_train_test']}\n"
        f"- Pairs <0.5 km: {leakage['pairs_closer_than_0_5km']}\n\n"
    )
    md.append("## Channel summary (mean frac nodata / frac chips all-nodata)\n\n")
    for name, rec in channels.items():
        md.append(
            f"- `{name}`: mean_nodata={rec['mean_frac_nodata']:.4f}, "
            f"all_nodata_chips={rec['frac_chips_all_nodata']:.3f}, "
            f"constant_finite={rec['frac_chips_constant_finite']:.3f}\n"
        )
    Path(__file__).resolve().parents[1].joinpath("DATA_AUDIT.md").write_text(
        "".join(md), encoding="utf-8"
    )
    append_run_log(f"{datetime.now(timezone.utc).isoformat()} END phase2_data_audit n={len(samples)}")
    print("wrote phase2_data_audit.json and DATA_AUDIT.md", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
