"""Construct independent USGS+STAC eval chips and run DeepSlide Gate A evaluation."""
from __future__ import annotations

import json
import math
import sys
import time
import traceback
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
POC = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
CHIPS = OUT / "chips"
CHIPS.mkdir(exist_ok=True)

sys.path.insert(0, str(POC))
from integration.deepslide_engine import (  # noqa: E402
    DeepSlideEngine,
    package_raw_stack,
    write_georef_prediction,
)

WEIGHTS = POC / "weights" / "mobilenetv2.pth"
CATALOG = REPO / "data" / "catalogs" / "usgs_landslide_v3" / "catalog.jsonl"
FS_SAMPLES = REPO / "data" / "datasets" / "usgs_landslide_featurestacks" / "v3" / "samples"
ACCEPT = json.loads((Path(__file__).parent / "acceptance.json").read_text(encoding="utf-8"))

PATCH = 128
RES_M = 10.0
BUFFER_M = 40.0
POS_PER_BLOCK = 4
NEG_PER_BLOCK = 4
TARGET_BLOCKS = 3


def spatial_block(lat: float, lon: float) -> str:
    return f"{int(math.floor(lat / 5.0) * 5)}_{int(math.floor(lon / 5.0) * 5)}"


def load_presence_candidates() -> list[dict]:
    rows = []
    with CATALOG.open(encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            lat, lon = o.get("latitude"), o.get("longitude")
            if lat is None or lon is None:
                continue
            if not (24 <= lat <= 49 and -125 <= lon <= -66):
                continue
            q = "|".join(o.get("quality_flags") or [])
            if "confidence=1" in q or "confidence=2" in q:
                continue
            ts = o.get("timestamp") or ""
            year = ts[:4]
            if year.isdigit() and int(year) < 2017:
                continue
            if year.isdigit() and int(year) > 2024:
                continue
            o["_block"] = spatial_block(lat, lon)
            o["_role"] = "presence"
            rows.append(o)
    return rows


def load_absence_candidates() -> list[dict]:
    """Catalog pseudo-absences; block ALWAYS from lat/lon (ignore metadata spatial_block)."""
    rows = []
    for d in FS_SAMPLES.iterdir():
        if not d.is_dir() or not d.name.startswith("pseudo-absence"):
            continue
        meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
        lat, lon = meta.get("latitude"), meta.get("longitude")
        if lat is None or lon is None:
            bbox = meta.get("bbox_wgs84")
            if not bbox:
                continue
            lon = (bbox[0] + bbox[2]) / 2
            lat = (bbox[1] + bbox[3]) / 2
        if not (24 <= lat <= 49 and -125 <= lon <= -66):
            continue
        rows.append(
            {
                "sample_id": meta.get("sample_id", d.name),
                "latitude": lat,
                "longitude": lon,
                "timestamp": None,
                "_block": spatial_block(lat, lon),
                "_role": "absence",
                "provenance": {"source": "featurestack_pseudo_absence", **(meta.get("provenance") or {})},
            }
        )
    return rows


def _min_haversine_km(lat: float, lon: float, points: list[tuple[float, float]]) -> float:
    """Rough great-circle distance to nearest inventory point (km)."""
    if not points:
        return 1e9
    rlat, rlon = math.radians(lat), math.radians(lon)
    best = 1e9
    for plat, plon in points:
        dlat = math.radians(plat - lat)
        dlon = math.radians(plon - lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(rlat) * math.cos(math.radians(plat)) * math.sin(dlon / 2) ** 2
        best = min(best, 6371.0 * 2 * math.asin(min(1.0, math.sqrt(a))))
    return best


def synthesize_in_block_absences(
    block: str,
    presence_rows: list[dict],
    all_presence: list[dict],
    n: int,
    rng: np.random.Generator,
) -> list[dict]:
    """Defensible pseudo-absences inside the same 5° block, ≥5 km from any USGS presence point."""
    inv_pts = [(r["latitude"], r["longitude"]) for r in all_presence]
    # Sample within the bounding box of presence in this block, expanded slightly
    lats = [r["latitude"] for r in presence_rows]
    lons = [r["longitude"] for r in presence_rows]
    lat0, lat1 = min(lats) - 0.4, max(lats) + 0.4
    lon0, lon1 = min(lons) - 0.4, max(lons) + 0.4
    # Clamp to block geographic bounds
    b_lat, b_lon = (int(x) for x in block.split("_"))
    lat0 = max(lat0, float(b_lat))
    lat1 = min(lat1, float(b_lat) + 5.0)
    lon0 = max(lon0, float(b_lon))
    lon1 = min(lon1, float(b_lon) + 5.0)
    out: list[dict] = []
    for attempt in range(5000):
        if len(out) >= n:
            break
        lat = float(rng.uniform(lat0, lat1))
        lon = float(rng.uniform(lon0, lon1))
        if spatial_block(lat, lon) != block:
            continue
        if _min_haversine_km(lat, lon, inv_pts) < 5.0:
            continue
        out.append(
            {
                "sample_id": f"synth-absence-{block}-{len(out):02d}",
                "latitude": lat,
                "longitude": lon,
                "timestamp": presence_rows[0].get("timestamp"),
                "_block": block,
                "_role": "absence",
                "provenance": {
                    "source": "gate_a_in_block_synthesis",
                    "rule": "uniform_in_block_bbox_min_5km_from_usgs_presence",
                    "attempts": attempt + 1,
                },
            }
        )
    return out


def select_balanced(presence: list[dict], absence: list[dict]) -> list[dict]:
    """Select POS/NEG per spatial block; absences must share the same geographic block."""
    rng = np.random.default_rng(42)
    by_p: dict[str, list] = defaultdict(list)
    by_a: dict[str, list] = defaultdict(list)
    for r in presence:
        by_p[r["_block"]].append(r)
    for r in absence:
        by_a[r["_block"]].append(r)

    eligible = sorted(
        [b for b in by_p if len(by_p[b]) >= POS_PER_BLOCK],
        key=lambda b: -len(by_p[b]),
    )
    selected: list[dict] = []
    filled_blocks: list[str] = []
    for block in eligible:
        if len(filled_blocks) >= TARGET_BLOCKS:
            break
        abs_pool = list(by_a.get(block, []))
        if len(abs_pool) < NEG_PER_BLOCK:
            abs_pool.extend(
                synthesize_in_block_absences(
                    block, by_p[block], presence, NEG_PER_BLOCK - len(abs_pool), rng
                )
            )
        if len(abs_pool) < NEG_PER_BLOCK:
            continue
        for r in by_p[block][:POS_PER_BLOCK]:
            r = dict(r)
            r["_eval_block"] = block
            selected.append(r)
        for r in abs_pool[:NEG_PER_BLOCK]:
            r = dict(r)
            r["_eval_block"] = block
            selected.append(r)
        filled_blocks.append(block)
    return selected


def parse_event_date(ts: str | None) -> datetime | None:
    if not ts:
        return None
    head = ts.strip().replace("-", "/").split(" ")[0]
    parts = head.split("/")
    try:
        if len(parts) >= 3:
            return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:  # noqa: BLE001
        return None
    return None


def fetch_raw_stack(lat: float, lon: float, event_dt: datetime | None) -> dict:
    import planetary_computer
    import pystac_client
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import transform as warp_xy
    from rasterio.windows import Window

    half = (PATCH * RES_M) / 2.0 / 111_320.0  # rough deg
    # better: use UTM window after finding item
    if event_dt is None:
        event_dt = datetime(2020, 6, 15)
    start = (event_dt - timedelta(days=60)).strftime("%Y-%m-%d")
    end = (event_dt + timedelta(days=180)).strftime("%Y-%m-%d")

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    bbox = (lon - 0.02, lat - 0.02, lon + 0.02, lat + 0.02)
    items = list(
        catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=bbox,
            datetime=f"{start}/{end}",
            query={"eo:cloud_cover": {"lt": 30}},
            max_items=12,
        ).items()
    )
    if not items:
        # widen time
        items = list(
            catalog.search(
                collections=["sentinel-2-l2a"],
                bbox=bbox,
                datetime="2018-01-01/2023-12-31",
                query={"eo:cloud_cover": {"lt": 20}},
                max_items=12,
            ).items()
        )
    if not items:
        return {"ok": False, "reason": "no_s2"}

    item = sorted(items, key=lambda it: it.properties.get("eo:cloud_cover", 100))[0]
    band_keys = [f"B{str(i).zfill(2)}" for i in range(1, 13)]

    with rasterio.open(item.assets["B04"].href) as ref:
        xs, ys = warp_xy("EPSG:4326", ref.crs, [lon], [lat])
        row, col = ref.index(xs[0], ys[0])
        r0 = int(row) - PATCH // 2
        c0 = int(col) - PATCH // 2
        r0 = max(0, min(r0, ref.height - PATCH))
        c0 = max(0, min(c0, ref.width - PATCH))
        window = Window(c0, r0, PATCH, PATCH)
        transform = ref.window_transform(window)
        crs = ref.crs
        raw = np.zeros((14, PATCH, PATCH), dtype=np.float64)
        b10_fill = False
        for i, key in enumerate(band_keys):
            arr = np.zeros((PATCH, PATCH), dtype=np.float64)
            if key in item.assets:
                with rasterio.open(item.assets[key].href) as src:
                    from rasterio.warp import reproject

                    reproject(
                        source=rasterio.band(src, 1),
                        destination=arr,
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=crs,
                        resampling=Resampling.bilinear,
                    )
                if arr.max() <= 1.5:
                    arr *= 10000.0
            else:
                b10_fill = True
            raw[i] = arr

    dem_items = list(catalog.search(collections=["cop-dem-glo-30"], bbox=bbox, max_items=3).items())
    if not dem_items:
        return {"ok": False, "reason": "no_dem"}
    dem = np.zeros((PATCH, PATCH), dtype=np.float64)
    dem_asset = dem_items[0].assets.get("data") or next(iter(dem_items[0].assets.values()))
    with rasterio.open(dem_asset.href) as src:
        from rasterio.warp import reproject

        reproject(
            source=rasterio.band(src, 1),
            destination=dem,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=crs,
            resampling=Resampling.bilinear,
        )
    gy, gx = np.gradient(dem, RES_M, RES_M)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    raw[12] = slope
    raw[13] = dem
    raw = np.nan_to_num(raw, nan=0.0)

    # center pixel of chip for buffer mask (point projected)
    # row/col of lat/lon in window
    xs, ys = warp_xy("EPSG:4326", crs, [lon], [lat])
    # map to window indices
    inv = ~transform
    c_f, r_f = inv * (xs[0], ys[0])
    return {
        "ok": True,
        "raw": raw,
        "crs": crs,
        "transform": transform,
        "s2_item": item.id,
        "s2_datetime": item.properties.get("datetime"),
        "cloud_cover": item.properties.get("eo:cloud_cover"),
        "dem_item": dem_items[0].id,
        "b10_zeros_fill": b10_fill,
        "center_rc": (float(r_f), float(c_f)),
    }


def make_buffer_mask(center_rc: tuple[float, float], positive: bool) -> np.ndarray:
    mask = np.zeros((PATCH, PATCH), dtype=np.uint8)
    if not positive:
        return mask
    cr, cc = center_rc
    rad_px = BUFFER_M / RES_M
    yy, xx = np.ogrid[:PATCH, :PATCH]
    dist = np.sqrt((yy - cr) ** 2 + (xx - cc) ** 2)
    mask[dist <= rad_px] = 1
    # ensure at least center pixel if center in bounds
    r_i, c_i = int(round(cr)), int(round(cc))
    if 0 <= r_i < PATCH and 0 <= c_i < PATCH:
        mask[r_i, c_i] = 1
    return mask


def chip_pred_positive(score: np.ndarray, gt: np.ndarray, role: str) -> bool:
    pred = score > 0.5
    if role == "presence":
        # any hit inside buffer
        return bool(np.logical_and(pred, gt.astype(bool)).any())
    # absence: any positive pixel is FP
    return bool(pred.any())


def slope_chip_baseline(raw: np.ndarray, role: str, gt: np.ndarray) -> bool:
    """Predict positive if mean slope in chip > 15 deg (terrain heuristic)."""
    slope = raw[12]
    flag = float(np.nanmean(slope)) > 15.0
    return flag


def metrics_from_counts(tp: int, fp: int, fn: int, tn: int) -> dict:
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    iou = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0
    return {
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "iou": iou,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
    }


def main() -> int:
    report: dict = {
        "gate": "A_build_eval",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "acceptance": ACCEPT,
        "repo": str(REPO),
    }
    if not CATALOG.exists():
        report["verdict"] = "BLOCKED"
        report["blocker"] = f"missing catalog {CATALOG}"
        (OUT / "gate_a_eval_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    presence = load_presence_candidates()
    absence = load_absence_candidates()
    selected = select_balanced(presence, absence)
    report["selection"] = {
        "presence_pool": len(presence),
        "absence_pool": len(absence),
        "selected": len(selected),
        "blocks": sorted({r["_eval_block"] for r in selected}),
        "n_presence": sum(1 for r in selected if r["_role"] == "presence"),
        "n_absence": sum(1 for r in selected if r["_role"] == "absence"),
    }
    (OUT / "selected_sites.json").write_text(
        json.dumps(
            [
                {
                    "sample_id": r.get("sample_id"),
                    "lat": r["latitude"],
                    "lon": r["longitude"],
                    "role": r["_role"],
                    "block": r["_eval_block"],
                    "timestamp": r.get("timestamp"),
                }
                for r in selected
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    engine = DeepSlideEngine(WEIGHTS, threshold=0.5)
    chip_records = []
    failures = []

    for i, site in enumerate(selected):
        sid = str(site.get("sample_id") or f"site_{i}")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in sid)[:80]
        event_dt = parse_event_date(site.get("timestamp"))
        try:
            fetched = fetch_raw_stack(site["latitude"], site["longitude"], event_dt)
        except Exception as exc:  # noqa: BLE001
            failures.append({"sample_id": sid, "error": str(exc), "traceback": traceback.format_exc()[:500]})
            continue
        if not fetched.get("ok"):
            failures.append({"sample_id": sid, "error": fetched.get("reason")})
            continue

        raw = fetched["raw"]
        gt = make_buffer_mask(fetched["center_rc"], positive=(site["_role"] == "presence"))
        packaged = package_raw_stack(raw)
        pred = engine.predict_packaged(packaged)

        chip_dir = CHIPS / safe
        chip_dir.mkdir(exist_ok=True)
        np.save(chip_dir / "raw.npy", raw.astype(np.float32))
        np.save(chip_dir / "packaged.npy", packaged)
        np.save(chip_dir / "mask_gt.npy", gt)
        np.save(chip_dir / "score.npy", pred["score"])
        np.save(chip_dir / "mask_pred.npy", pred["mask"])
        write_georef_prediction(
            chip_dir / "prediction.tif",
            pred["mask"],
            pred["score"],
            crs=fetched["crs"],
            transform=fetched["transform"],
            tags={"SAMPLE_ID": sid, "ROLE": site["_role"]},
        )
        # also write gt geotiff
        import rasterio

        profile = {
            "driver": "GTiff",
            "height": PATCH,
            "width": PATCH,
            "count": 1,
            "dtype": "uint8",
            "crs": fetched["crs"],
            "transform": fetched["transform"],
            "compress": "lzw",
        }
        with rasterio.open(chip_dir / "label_buffer.tif", "w", **profile) as dst:
            dst.write(gt, 1)
            dst.update_tags(LABEL="point_buffer_40m" if site["_role"] == "presence" else "all_zero_absence")

        meta = {
            "sample_id": sid,
            "role": site["_role"],
            "lat": site["latitude"],
            "lon": site["longitude"],
            "eval_block": site["_eval_block"],
            "inventory_timestamp": site.get("timestamp"),
            "s2_item": fetched["s2_item"],
            "s2_datetime": fetched["s2_datetime"],
            "cloud_cover": fetched["cloud_cover"],
            "dem_item": fetched["dem_item"],
            "b10_zeros_fill": fetched["b10_zeros_fill"],
            "crs": str(fetched["crs"]),
            "buffer_m": BUFFER_M,
            "gt_pos_pixels": int(gt.sum()),
            "pred_pos_pixels": int(pred["mask"].sum()),
            "score_max": pred["score_max"],
            "chip_pred_positive": chip_pred_positive(pred["score"], gt, site["_role"]),
            "slope_baseline_positive": slope_chip_baseline(raw, site["_role"], gt),
            "majority_baseline_positive": False,  # majority = always non-landslide
        }
        (chip_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        chip_records.append(meta)
        print(f"ok {i+1}/{len(selected)} {sid} role={site['_role']} pred_chip={meta['chip_pred_positive']}", flush=True)

    report["build"] = {
        "n_ok": len(chip_records),
        "n_failed": len(failures),
        "failures": failures[:20],
        "blocks": sorted({c["eval_block"] for c in chip_records}),
    }

    if len(chip_records) < ACCEPT["min_chips"] or len(report["build"]["blocks"]) < ACCEPT["min_regions"]:
        report["verdict"] = "BLOCKED"
        report["blocker"] = (
            f"Insufficient chips built: {len(chip_records)} chips / {len(report['build']['blocks'])} blocks "
            f"(need >= {ACCEPT['min_chips']} chips and >= {ACCEPT['min_regions']} regions). "
            f"Failures: {len(failures)}"
        )
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        (OUT / "gate_a_eval_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"verdict": report["verdict"], "blocker": report["blocker"]}, indent=2))
        return 2

    # Chip-level confusion
    def chip_conf(pred_key: str) -> dict:
        tp = fp = fn = tn = 0
        for c in chip_records:
            truth = c["role"] == "presence"
            pred_pos = c[pred_key]
            if truth and pred_pos:
                tp += 1
            elif not truth and pred_pos:
                fp += 1
            elif truth and not pred_pos:
                fn += 1
            else:
                tn += 1
        return metrics_from_counts(tp, fp, fn, tn)

    model_chip = chip_conf("chip_pred_positive")
    maj_chip = chip_conf("majority_baseline_positive")
    slope_chip = chip_conf("slope_baseline_positive")

    # Pixel metrics vs buffer (secondary)
    tp = fp = fn = tn = 0
    for c in chip_records:
        gt = np.load(CHIPS / "".join(x if x.isalnum() or x in "-_" else "_" for x in c["sample_id"])[:80] / "mask_gt.npy")
        # find dir - use glob
        pass
    # more robust path lookup
    tp = fp = fn = tn = 0
    for d in CHIPS.iterdir():
        if not d.is_dir():
            continue
        gt = np.load(d / "mask_gt.npy").astype(bool).ravel()
        pred = np.load(d / "mask_pred.npy").astype(bool).ravel()
        tp += int(np.logical_and(pred, gt).sum())
        fp += int(np.logical_and(pred, ~gt).sum())
        fn += int(np.logical_and(~pred, gt).sum())
        tn += int(np.logical_and(~pred, ~gt).sum())
    pixel = metrics_from_counts(tp, fp, fn, tn)

    by_block = {}
    for b in report["build"]["blocks"]:
        sub = [c for c in chip_records if c["eval_block"] == b]
        tp = fp = fn = tn = 0
        for c in sub:
            truth = c["role"] == "presence"
            pred_pos = c["chip_pred_positive"]
            if truth and pred_pos:
                tp += 1
            elif not truth and pred_pos:
                fp += 1
            elif truth and not pred_pos:
                fn += 1
            else:
                tn += 1
        by_block[b] = metrics_from_counts(tp, fp, fn, tn) | {"n": len(sub)}

    g1 = model_chip["f1"] > maj_chip["f1"]
    g2 = model_chip["f1"] > slope_chip["f1"]
    g3 = model_chip["f1"] >= float(ACCEPT["gates"]["min_chip_f1"])
    numeric_pass = g1 and g2 and g3

    report["evaluation"] = {
        "n_chips": len(chip_records),
        "class_prevalence_presence_chips": sum(1 for c in chip_records if c["role"] == "presence") / len(chip_records),
        "chip_model": model_chip,
        "chip_majority": maj_chip,
        "chip_slope": slope_chip,
        "pixel_vs_buffer_model": pixel,
        "per_block_chip_model": by_block,
        "gates": {
            "beat_majority": {"pass": g1, "model_f1": model_chip["f1"], "majority_f1": maj_chip["f1"]},
            "beat_slope": {"pass": g2, "model_f1": model_chip["f1"], "slope_f1": slope_chip["f1"]},
            "min_chip_f1": {"pass": g3, "model_f1": model_chip["f1"], "floor": ACCEPT["gates"]["min_chip_f1"]},
        },
        "numeric_pass": numeric_pass,
    }
    report["limitations"] = [
        "USGS points buffered to 40 m are not landslide scar polygons",
        "Copernicus DEM used instead of ALOS PALSAR",
        "Sentinel-2 L2A B10 zero-filled when absent",
        "Temporal match is nearest low-cloud scene in a window around inventory date, not guaranteed event-day imagery",
        "In-block absences may be catalog pseudo-absences or synthesized (≥5 km from USGS presence); not field-verified non-landslides",
        "Uncalibrated scores are not risk probabilities",
        "Per-block tags are true geographic 5° cells; absences are co-located in the same block as paired presence chips",
    ]
    report["scientific_validation"] = "UNRESOLVED"
    report["verdict"] = "PASS" if numeric_pass else "FAIL"
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    (OUT / "gate_a_eval_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUT / "chip_records.json").write_text(json.dumps(chip_records, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "n_chips": len(chip_records),
                "blocks": report["build"]["blocks"],
                "chip_f1_model": model_chip["f1"],
                "chip_f1_majority": maj_chip["f1"],
                "chip_f1_slope": slope_chip["f1"],
                "gates": report["evaluation"]["gates"],
            },
            indent=2,
        )
    )
    return 0 if numeric_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
