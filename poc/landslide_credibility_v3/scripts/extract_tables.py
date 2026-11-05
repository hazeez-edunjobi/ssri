"""Extract complete metric tables for FINAL_REPORT."""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "outputs"
d = json.loads((OUT / "phase4_eval.json").read_text(encoding="utf-8"))


def row(scheme, name):
    r = d[scheme]["lobo_results"][name]
    vs = r["vs_slope"]
    cm = r["confusion"]
    return {
        "scheme": scheme,
        "name": name,
        "roc_auc": vs["auc_point"],
        "auc_ci95": vs["auc_ci95"],
        "pr_auc": r["pr_auc"],
        "brier": r["brier"],
        "ece": r["ece"],
        "delta": vs["delta_point"],
        "delta_ci95": vs["delta_ci95"],
        "frac_gt_0_5": r["frac_blocks_auc_gt_0_5"],
        "n_blocks": r["n_both_class_blocks"],
        "thr": r["threshold"],
        "tp": cm["tp"],
        "fp": cm["fp"],
        "fn": cm["fn"],
        "tn": cm["tn"],
        "pd": None,
    }


rows = []
for scheme in ["NEAR_lobo", "FAR_lobo", "SLOPE_MATCHED_lobo"]:
    for name in d[scheme]["lobo_results"]:
        rows.append(row(scheme, name))
    print("PD", scheme, "logreg", d[scheme].get("pd_logreg"), "hgb", d[scheme].get("pd_hgb"))

(OUT / "phase4_tables.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
print("wrote", len(rows), "rows")
for r in rows:
    if r["name"] == "B0_majority":
        continue
    print(
        f"| {r['scheme']} | {r['name']} | {r['roc_auc']:.4f} | {r['auc_ci95']} | {r['pr_auc']:.4f} | "
        f"{r['brier']:.4f} | {r['ece']:.4f} | {r['delta']} | {r['delta_ci95']} | {r['frac_gt_0_5']:.3f} | "
        f"{r['tp']}/{r['fp']}/{r['fn']}/{r['tn']} |"
    )
