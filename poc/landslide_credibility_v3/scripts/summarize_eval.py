"""Print headline LOBO metrics from phase4_eval.json."""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "outputs"
d = json.loads((OUT / "phase4_eval.json").read_text(encoding="utf-8"))
print("decision", d["decision"], d["credibility_level"])
for scheme in ["NEAR_lobo", "FAR_lobo", "SLOPE_MATCHED_lobo"]:
    print("==", scheme, "n_oof=", d[scheme].get("n_oof"))
    for name, r in d[scheme]["lobo_results"].items():
        vs = r["vs_slope"]
        print(
            f"  {name}: AUC={vs['auc_point']} CI={vs['auc_ci95']} "
            f"slope={vs['slope_auc_point']} dAUC={vs['delta_point']} "
            f"dCI={vs['delta_ci95']} frac={r['frac_blocks_auc_gt_0_5']} "
            f"pr={r.get('pr_auc')} brier={r.get('brier')} ece={r.get('ece')}"
        )
print("sealed", d["sealed_fresh"])
print("spent keys", d["exploratory_spent_v2"].keys())
if d["exploratory_spent_v2"].get("results"):
    for k, v in d["exploratory_spent_v2"]["results"].items():
        print(" spent", k, "auc", v.get("roc_auc"), "d", v["vs_slope"].get("delta_point"))
