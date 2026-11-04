"""Phase 6: failure analysis by block, slope, source, distance."""
from __future__ import annotations

import json
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CORPUS,
    FEATURE_NAMES,
    OUT,
    append_log,
    haversine_km,
    load_jsonl,
    roc_auc,
    write_json,
)
from lobo_eval import matrix, slope_cdf_scores  # noqa: E402


def main() -> int:
    append_log("START failure_analysis")
    near = load_jsonl(CORPUS / "lobo_near.jsonl")
    X, y, blocks = matrix(near)
    j = FEATURE_NAMES.index("slope")
    # Use frozen NEAR models + slope CDF from full LOBO set
    ref_idx = np.arange(len(near))
    slope_s = slope_cdf_scores(X, ref_idx)
    lr = pickle.load(open(CORPUS / "models" / "NEAR_logreg.pkl", "rb"))["model"]
    hgb = pickle.load(open(CORPUS / "models" / "NEAR_hgb.pkl", "rb"))["model"]
    s_lr = lr.predict_proba(X)[:, 1]
    s_h = hgb.predict_proba(X)[:, 1]
    thr = json.loads((OUT / "phase3_freeze.json").read_text(encoding="utf-8"))["NEAR"]["thr_slope"]

    # Distance to nearest opposite-label presence/absence
    pos = [(r["lat"], r["lon"]) for r in near if r["y"] == 1]
    neg = [(r["lat"], r["lon"]) for r in near if r["y"] == 0]

    by_block = {}
    for b in sorted(set(blocks)):
        idxs = [i for i, bb in enumerate(blocks) if bb == b]
        yy = y[idxs]
        if len(set(yy)) < 2:
            continue
        by_block[b] = {
            "n": len(idxs),
            "n_pos": int(yy.sum()),
            "auc_slope": roc_auc(yy, slope_s[idxs]),
            "auc_logreg": roc_auc(yy, s_lr[idxs]),
            "auc_hgb": roc_auc(yy, s_h[idxs]),
            "mean_slope_pos": float(X[idxs][yy == 1, j].mean()),
            "mean_slope_neg": float(X[idxs][yy == 0, j].mean()),
            "sources": dict(
                defaultdict(
                    int,
                    (
                        (__import__("collections").Counter(near[i]["source"] for i in idxs))
                    ),
                )
            )
            if False
            else dict(__import__("collections").Counter(near[i].get("source", "?") for i in idxs)),
        }

    # Slope quintile performance
    qs = np.quantile(X[:, j], [0, 0.2, 0.4, 0.6, 0.8, 1.0])
    slope_bins = []
    for a, b in zip(qs[:-1], qs[1:]):
        m = (X[:, j] >= a) & (X[:, j] <= b)
        if m.sum() < 10 or len(set(y[m])) < 2:
            continue
        slope_bins.append(
            {
                "slope_lo": float(a),
                "slope_hi": float(b),
                "n": int(m.sum()),
                "auc_slope": roc_auc(y[m], slope_s[m]),
                "auc_logreg": roc_auc(y[m], s_lr[m]),
                "auc_hgb": roc_auc(y[m], s_h[m]),
            }
        )

    # FP/FN for slope at train threshold
    pred = (slope_s >= thr).astype(int)
    fp_idx = np.where((pred == 1) & (y == 0))[0][:8]
    fn_idx = np.where((pred == 0) & (y == 1))[0][:8]

    def ex(i):
        r = near[i]
        # nearest presence distance for absences / nearest absence for presence
        if r["y"] == 0 and pos:
            d = min(haversine_km(r["lat"], r["lon"], plat, plon) for plat, plon in pos)
        elif r["y"] == 1 and neg:
            d = min(haversine_km(r["lat"], r["lon"], nlat, nlon) for nlat, nlon in neg)
        else:
            d = None
        return {
            "sample_id": r["sample_id"],
            "lat": r["lat"],
            "lon": r["lon"],
            "block": r["block"],
            "y": r["y"],
            "slope": float(X[i, j]),
            "score_slope": float(slope_s[i]),
            "score_logreg": float(s_lr[i]),
            "score_hgb": float(s_h[i]),
            "source": r.get("source"),
            "dist_km_nearest_opp": d,
        }

    out = {
        "question": "Does anything beyond slope add value?",
        "answer": "No under PROTOCOL_v3 Tier A. On NEAR LOBO, slope-only AUC≈0.89; logreg/HGB ΔAUC point estimates negative and 95% CI lower bounds ≤0. On SLOPE-MATCHED, slope itself drops to ~0.53 and multivariate models still do not beat it (ΔAUC point < 0).",
        "why": "Presence–absence separation in NEAR/FAR is largely slope-driven. Matching absences on slope removes that signal; residual DEM features do not recover ranking skill above chance with CI support.",
        "by_block": by_block,
        "by_slope_quintile": slope_bins,
        "false_positives_slope": [ex(int(i)) for i in fp_idx],
        "false_negatives_slope": [ex(int(i)) for i in fn_idx],
        "threshold_slope": thr,
    }
    write_json(OUT / "phase6_failure.json", out)
    append_log("END failure_analysis")
    print(json.dumps({"n_blocks": len(by_block), "n_fp_ex": len(fp_idx), "n_fn_ex": len(fn_idx)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
