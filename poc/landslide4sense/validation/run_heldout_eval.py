"""Held-out evaluation of DeepSlide MobileNetV2 on L4S validation chips."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import h5py
import numpy as np
import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_poc import (  # noqa: E402
    WEIGHTS,
    binary_metrics,
    build_model,
    load_image,
    load_mask,
    load_weights,
    majority_baseline,
    predict_prob,
    slope_threshold_baseline,
)

VAL_IMG = ROOT / "data" / "validation" / "images"
VAL_MSK = ROOT / "data" / "validation" / "masks"
OUT = ROOT / "validation" / "outputs"
CRIT = json.loads((ROOT / "validation" / "acceptance_criteria.json").read_text(encoding="utf-8"))


def micro(rows: list[dict]) -> dict:
    tp = sum(r["tp"] for r in rows)
    fp = sum(r["fp"] for r in rows)
    fn = sum(r["fn"] for r in rows)
    tn = sum(r["tn"] for r in rows)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
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
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = []
    for img in sorted(VAL_IMG.glob("image_*.h5")):
        cid = int(img.stem.split("_")[1])
        msk = VAL_MSK / f"mask_{cid}.h5"
        if msk.exists():
            pairs.append((cid, img, msk))
    min_chips = CRIT["held_out_eval"]["minimum_chips"]
    report: dict = {
        "phase": 3,
        "dataset": "Landslide4Sense validation (HF)",
        "n_pairs_available": len(pairs),
        "decision_threshold": CRIT["threshold_policy"]["decision_threshold"],
        "threshold_selection": CRIT["threshold_policy"]["selection"],
        "acceptance_criteria_path": str(ROOT / "validation" / "acceptance_criteria.json"),
        "gates": {},
        "errors": [],
    }
    if len(pairs) < min_chips:
        report["errors"].append(f"Need >= {min_chips} labelled validation chips; have {len(pairs)}")
        report["verdict"] = "BLOCKED"
        (OUT / "heldout_eval.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    device = torch.device("cpu")
    t0 = time.perf_counter()
    model = build_model()
    load_note = load_weights(model, WEIGHTS)
    model.eval().to(device)
    load_s = time.perf_counter() - t0
    report["weight_load"] = load_note
    report["model_load_s"] = round(load_s, 3)

    thr = float(CRIT["threshold_policy"]["decision_threshold"])
    model_rows, maj_rows, slope_rows = [], [], []
    infer_times = []
    gt_pos_total = 0
    pixels_total = 0

    for cid, img_p, msk_p in pairs:
        image = load_image(img_p)
        gt = load_mask(msk_p)
        t1 = time.perf_counter()
        prob = predict_prob(model, image, device)
        infer_times.append(time.perf_counter() - t1)
        pred = (prob > thr).astype(np.uint8)
        model_rows.append({"chip_id": cid, **binary_metrics(pred, gt), "pred_pos": int(pred.sum()), "gt_pos": int(gt.sum())})
        maj_rows.append({"chip_id": cid, **binary_metrics(majority_baseline(gt), gt)})
        slope_rows.append({"chip_id": cid, **binary_metrics(slope_threshold_baseline(image, gt), gt)})
        gt_pos_total += int(gt.sum())
        pixels_total += int(gt.size)

    m_micro = micro(model_rows)
    maj_micro = micro(maj_rows)
    slope_micro = micro(slope_rows)
    report["test_set"] = {
        "n_chips": len(pairs),
        "n_pixels": pixels_total,
        "landslide_pixels": gt_pos_total,
        "class_prevalence_landslide": gt_pos_total / pixels_total if pixels_total else 0.0,
        "chip_ids": [p[0] for p in pairs],
    }
    report["metrics"] = {
        "model": m_micro,
        "majority_baseline": maj_micro,
        "slope_baseline": slope_micro,
        "per_chip_model": model_rows,
    }
    report["runtime"] = {
        "infer_mean_s": round(float(np.mean(infer_times)), 4),
        "infer_sum_s": round(float(np.sum(infer_times)), 3),
    }

    gates = CRIT["held_out_eval"]["gates"]
    g1 = m_micro["f1"] > maj_micro["f1"]
    g2 = (m_micro["f1"] - slope_micro["f1"]) >= float(gates["beat_slope_micro_f1_by"]["delta"])
    g3 = m_micro["f1"] >= float(gates["absolute_micro_f1_floor"]["min_f1"])
    report["gates"] = {
        "beat_majority_micro_f1": {"pass": g1, "model_f1": m_micro["f1"], "majority_f1": maj_micro["f1"]},
        "beat_slope_micro_f1_by_0_10": {
            "pass": g2,
            "model_f1": m_micro["f1"],
            "slope_f1": slope_micro["f1"],
            "delta": m_micro["f1"] - slope_micro["f1"],
        },
        "absolute_micro_f1_floor_0_50": {"pass": g3, "model_f1": m_micro["f1"], "floor": 0.50},
    }
    numeric_pass = g1 and g2 and g3
    report["numeric_gates_pass"] = numeric_pass
    report["scientific_acceptance"] = "UNRESOLVED"
    report["scientific_acceptance_note"] = CRIT["held_out_eval"]["scientific_acceptance"]["policy"]
    report["verdict"] = "PASS_NUMERIC" if numeric_pass else "FAIL_NUMERIC"

    (OUT / "heldout_eval.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("verdict", "test_set", "metrics", "gates", "numeric_gates_pass")}, indent=2, default=str))
    return 0 if numeric_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
