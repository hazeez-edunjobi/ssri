"""Phase 6: external transfer on NASA GLC (report-only; no retune)."""
from __future__ import annotations

import csv
import json
import pickle
import sys
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CONFIG,
    CORPUS,
    FEATURE_NAMES,
    OUT,
    append_log,
    bootstrap_block,
    delta_auc_boot,
    write_json,
)
from build_corpus import compute_features_from_dem, fetch_dem_window, haversine_km, block5  # noqa: E402

# NASA GLC (public) — try common raw github / data.gov mirrors
GLC_URLS = [
    "https://raw.githubusercontent.com/nasa/global-landslide-catalog/master/nasa_global_landslide_catalog.csv",
    "https://data.nasa.gov/api/views/h9rt-udyj/rows.csv?accessType=DOWNLOAD",
]


def try_download(dest: Path) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    for url in GLC_URLS:
        try:
            urllib.request.urlretrieve(url, dest)
            if dest.stat().st_size > 1000:
                return {"ok": True, "url": url, "bytes": dest.stat().st_size}
        except Exception as exc:  # noqa: BLE001
            errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
    return {"ok": False, "errors": errors}


def load_glc_points(path: Path, n_max: int = 400, seed: int = 42) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    with path.open(encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # flexible column names
            lat = row.get("latitude") or row.get("Latitude") or row.get("lat")
            lon = row.get("longitude") or row.get("Longitude") or row.get("lon")
            if lat is None or lon is None:
                continue
            try:
                lat_f, lon_f = float(lat), float(lon)
            except ValueError:
                continue
            # non-CONUS only for transfer
            if 24 <= lat_f <= 49 and -125 <= lon_f <= -66:
                continue
            if abs(lat_f) > 85:
                continue
            rows.append({"lat": lat_f, "lon": lon_f, "y": 1})
    if len(rows) > n_max:
        pick = rng.choice(len(rows), size=n_max, replace=False)
        rows = [rows[i] for i in pick]
    return rows


def main() -> int:
    append_log("START phase6_transfer")
    dest = CORPUS / "external" / "nasa_glc.csv"
    dl = try_download(dest)
    if not dl.get("ok"):
        write_json(
            OUT / "phase6_transfer.json",
            {
                "status": "BLOCKED",
                "reason": "Could not download NASA Global Landslide Catalog from free URLs",
                "download_errors": dl.get("errors"),
                "note": "Report-only phase; does not change Tier decision",
            },
        )
        append_log("phase6 BLOCKED download")
        print(json.dumps({"status": "BLOCKED", "errors": dl.get("errors")}, indent=2))
        return 0

    pres = load_glc_points(dest)
    # synthetic NEAR-like absences around non-CONUS points (5-20 km)
    rng = np.random.default_rng(42)
    absences = []
    for p in pres:
        for _ in range(20):
            # offset ~10 km
            dkm = float(rng.uniform(5, 20))
            bearing = float(rng.uniform(0, 2 * np.pi))
            dlat = (dkm / 111.0) * np.cos(bearing)
            dlon = (dkm / (111.0 * max(0.2, np.cos(np.radians(p["lat"]))))) * np.sin(bearing)
            absences.append({"lat": p["lat"] + dlat, "lon": p["lon"] + dlon, "y": 0})
            if len(absences) >= len(pres):
                break
        if len(absences) >= len(pres):
            break

    samples = pres + absences
    feat_rows = []
    fail = 0
    for s in samples:
        got = fetch_dem_window(s["lat"], s["lon"])
        if got is None:
            fail += 1
            continue
        dem, res = got
        feats = compute_features_from_dem(dem, res)
        if feats is None:
            fail += 1
            continue
        feat_rows.append({**s, "features": {k: feats[k] for k in FEATURE_NAMES}, "block": block5(s["lat"], s["lon"])})

    model_path = CORPUS / "models" / "NEAR_hgb.pkl"
    if not model_path.exists():
        model_path = CORPUS / "models" / "NEAR_logreg.pkl"
    with model_path.open("rb") as f:
        payload = pickle.load(f)
    model = payload["model"]
    cal = payload.get("cal")

    X = np.asarray([[r["features"][n] for n in FEATURE_NAMES] for r in feat_rows], dtype=np.float64)
    y = np.asarray([r["y"] for r in feat_rows], dtype=np.int32)
    blocks = [r["block"] for r in feat_rows]
    for j in range(X.shape[1]):
        med = np.nanmedian(X[:, j])
        X[np.isnan(X[:, j]), j] = med if np.isfinite(med) else 0.0
    raw = model.predict_proba(X)[:, 1]
    if cal:
        from train_eval import apply_cal

        scores = apply_cal(cal, raw)
    else:
        scores = raw
    slope = X[:, FEATURE_NAMES.index("slope")]
    ref = np.sort(slope[y == 0]) if (y == 0).any() else np.sort(slope)
    slope_s = np.searchsorted(ref, slope, side="right") / max(len(ref), 1)

    boot = bootstrap_block(y, scores, blocks, n_boot=1000, seed=42)
    delta = delta_auc_boot(y, scores, slope_s, blocks, n_boot=1000, seed=42)
    report = {
        "status": "OK",
        "source": dl,
        "n_presences_sampled": len(pres),
        "n_scored": len(feat_rows),
        "dem_fail": fail,
        "model": str(model_path),
        "metrics": boot,
        "vs_slope": delta,
        "limits": [
            "NASA GLC is media-reported with coarse positional accuracy",
            "Absences synthetic offsets, not field surveys",
            "No retune/recalibration on transfer set",
            "Poor transfer expected; not a failure of CONUS Tier decision",
            "Does not authorize non-CONUS claims",
        ],
    }
    write_json(OUT / "phase6_transfer.json", report)
    append_log("END phase6_transfer")
    print(json.dumps({"n": len(feat_rows), "auc": boot["point"]["roc_auc"], "dci": delta["ci95"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
