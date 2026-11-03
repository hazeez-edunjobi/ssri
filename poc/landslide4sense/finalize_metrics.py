"""Patch execution report with micro-averaged metrics and dependency inventory."""
from __future__ import annotations

import json
import platform
from pathlib import Path

OUT = Path(__file__).resolve().parent / "outputs"
rep_path = OUT / "execution_report.json"
rep = json.loads(rep_path.read_text(encoding="utf-8"))


def micro(rows: list[dict]) -> dict:
    tp = sum(c["tp"] for c in rows)
    fp = sum(c["fp"] for c in rows)
    fn = sum(c["fn"] for c in rows)
    tn = sum(c["tn"] for c in rows)
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
    }


ev = rep["evaluation"]
ev["micro_model"] = micro(ev["model"])
ev["micro_majority"] = micro(ev["baseline_majority_class"])
ev["micro_slope"] = micro(ev["baseline_slope_threshold"])
ev["outperforms_majority_micro"] = ev["micro_model"]["f1"] > ev["micro_majority"]["f1"]
ev["outperforms_slope_micro"] = ev["micro_model"]["f1"] > ev["micro_slope"]["f1"]

deps = {}
for name in ("torch", "h5py", "numpy", "matplotlib", "segmentation_models_pytorch", "rasterio"):
    try:
        mod = __import__(name)
        deps[name] = getattr(mod, "__version__", "unknown")
    except Exception as exc:  # noqa: BLE001
        deps[name] = f"missing ({exc})"

rep["environment"] = {
    "platform": platform.platform(),
    "python": platform.python_version(),
    "dependencies": deps,
    "gpu": False,
    "device": "cpu",
}

try:
    import psutil

    rep["runtime"]["rss_mb_end"] = round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
except Exception:  # noqa: BLE001
    pass

rep_path.write_text(json.dumps(rep, indent=2), encoding="utf-8")

md = OUT / "EXECUTION_REPORT.md"
text = md.read_text(encoding="utf-8")
extra = f"""
## Micro-averaged metrics (all eval pixels)

| Method | Precision | Recall | F1 | IoU |
|--------|-----------|--------|----|-----|
| DeepSlide MobileNetV2 | {ev['micro_model']['precision']:.4f} | {ev['micro_model']['recall']:.4f} | {ev['micro_model']['f1']:.4f} | {ev['micro_model']['iou']:.4f} |
| Majority (all non-LS) | {ev['micro_majority']['precision']:.4f} | {ev['micro_majority']['recall']:.4f} | {ev['micro_majority']['f1']:.4f} | {ev['micro_majority']['iou']:.4f} |
| Slope threshold | {ev['micro_slope']['precision']:.4f} | {ev['micro_slope']['recall']:.4f} | {ev['micro_slope']['f1']:.4f} | {ev['micro_slope']['iou']:.4f} |

Deps: {json.dumps(deps)}
"""
if "Micro-averaged metrics" not in text:
    md.write_text(text.rstrip() + "\n" + extra + "\n", encoding="utf-8")

print(json.dumps({"micro_model": ev["micro_model"], "micro_slope": ev["micro_slope"], "deps": deps}, indent=2))
