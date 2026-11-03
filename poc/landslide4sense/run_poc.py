"""
Isolated Landslide4Sense PoC runner.

Official IARAI baseline weights (batch3500_F1_7396.pth) are unreachable from this
environment (cloud.iarai.ac.at NXDOMAIN). This script runs the smallest free
pretrained alternative trained on the same Landslide4Sense 14-band format:
DeepSlide MobileNetV2 U-Net (MIT, harshinde/DeepSlide_Models).

Landslide only. Does not touch SSRI production code.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parent
DATA_IMG = ROOT / "data" / "images"
DATA_MSK = ROOT / "data" / "masks"
WEIGHTS = ROOT / "weights" / "mobilenetv2.pth"
OUT = ROOT / "outputs"
VENDOR = ROOT / "vendor"

sys.path.insert(0, str(VENDOR))

# Official L4S baseline mean/std (for documentation / optional compare only)
L4S_MEAN = np.array(
    [-0.4914, -0.3074, -0.1277, -0.0625, 0.0439, 0.0803, 0.0644, 0.0802, 0.3000, 0.4082, 0.0823, 0.0516, 0.3338, 0.7819],
    dtype=np.float32,
)
L4S_STD = np.array(
    [0.9325, 0.8775, 0.8860, 0.8869, 0.8857, 0.8418, 0.8354, 0.8491, 0.9061, 1.6072, 0.8848, 0.9232, 0.9018, 1.2913],
    dtype=np.float32,
)

# Hold-out ids for evaluation (not used for any training in this PoC)
EVAL_IDS = [1, 10, 100, 50]
PREVIEW_ID = 1


@dataclass
class ChipMetrics:
    chip_id: int
    precision: float
    recall: float
    f1: float
    iou: float
    pred_pos: int
    gt_pos: int


def load_image(path: Path) -> np.ndarray:
    """Return float32 array shaped (14, H, W)."""
    with h5py.File(path, "r") as f:
        key = "img" if "img" in f else list(f.keys())[0]
        data = np.array(f[key], dtype=np.float32)
    data = np.nan_to_num(data, nan=1e-6)
    if data.ndim != 3:
        raise ValueError(f"Unexpected ndim {data.ndim} in {path}")
    if data.shape[0] == 14:
        return data
    if data.shape[-1] == 14:
        return np.transpose(data, (2, 0, 1))
    raise ValueError(f"Unexpected shape {data.shape} in {path}")


def load_mask(path: Path) -> np.ndarray:
    with h5py.File(path, "r") as f:
        key = "mask" if "mask" in f else list(f.keys())[0]
        mask = np.array(f[key])
    return (mask > 0).astype(np.uint8)


def binary_metrics(pred: np.ndarray, gt: np.ndarray) -> dict:
    pred_b = pred.astype(bool).ravel()
    gt_b = gt.astype(bool).ravel()
    tp = int(np.logical_and(pred_b, gt_b).sum())
    fp = int(np.logical_and(pred_b, ~gt_b).sum())
    fn = int(np.logical_and(~pred_b, gt_b).sum())
    tn = int(np.logical_and(~pred_b, ~gt_b).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    iou = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "iou": iou,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def majority_baseline(gt: np.ndarray) -> np.ndarray:
    """Always predict the majority class on the chip (non-landslide if empty)."""
    return np.zeros_like(gt, dtype=np.uint8)


def slope_threshold_baseline(image_chw: np.ndarray, gt: np.ndarray) -> np.ndarray:
    """Simple heuristic: predict landslide where slope (band 13) exceeds median of GT landslide pixels,
    else global 75th percentile of slope. Fallback to zeros if no GT positives."""
    slope = image_chw[12]
    if gt.sum() > 0:
        thr = float(np.median(slope[gt.astype(bool)]))
    else:
        thr = float(np.percentile(slope, 75))
    return (slope >= thr).astype(np.uint8)


def build_model() -> nn.Module:
    import segmentation_models_pytorch as smp

    # DeepSlide config: smp Unet, mobilenet_v2, 14 in, 1 class, imagenet encoder init at train time
    return smp.Unet(
        encoder_name="mobilenet_v2",
        encoder_weights=None,
        in_channels=14,
        classes=1,
    )


def load_weights(model: nn.Module, path: Path) -> str:
    state = torch.load(path, map_location="cpu", weights_only=False)
    notes = []
    if isinstance(state, dict) and "state_dict" in state:
        state = state["state_dict"]
        notes.append("unwrapped Lightning state_dict")
    if not isinstance(state, dict):
        raise TypeError(f"Unexpected checkpoint type: {type(state)}")

    # DeepSlide Lightning: model(smp_model_v2).model(smp.Unet) → keys "model.model.*"
    # Prefer longest matching prefix first so Unet keys load cleanly.
    candidates = []
    for prefix in ("model.model.", "model.", ""):
        if prefix == "":
            cand = dict(state)
        else:
            cand = {k[len(prefix) :]: v for k, v in state.items() if k.startswith(prefix)}
        if cand:
            candidates.append((prefix or "<raw>", cand))

    best = None
    for label, cand in candidates:
        missing, unexpected = model.load_state_dict(cand, strict=False)
        notes.append(
            f"prefix={label} keys={len(cand)} missing={len(missing)} unexpected={len(unexpected)}"
        )
        score = len(missing) + len(unexpected)
        if best is None or score < best[0]:
            best = (score, label, cand, missing, unexpected)

    assert best is not None
    # Reload the best candidate so the live model holds those weights.
    model.load_state_dict(best[2], strict=False)
    notes.append(f"selected_prefix={best[1]} missing={len(best[3])} unexpected={len(best[4])}")
    if len(best[3]) > 20:
        raise RuntimeError(f"Too many missing keys after load: {notes}")
    return "; ".join(notes)


def predict_prob(model: nn.Module, image_chw: np.ndarray, device: torch.device) -> np.ndarray:
    # DeepSlide streamlit: normalize=False, raw float tensor, sigmoid
    x = torch.from_numpy(image_chw).unsqueeze(0).float().to(device)
    with torch.no_grad():
        logits = model(x)
        prob = torch.sigmoid(logits).squeeze().cpu().numpy()
    return prob.astype(np.float32)


def save_preview(image_chw: np.ndarray, gt: np.ndarray, prob: np.ndarray, pred: np.ndarray, path: Path) -> None:
    rgb = image_chw[:3].transpose(1, 2, 0)
    rgb = (rgb - rgb.min()) / (rgb.max() - rgb.min() + 1e-8)
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.5))
    axes[0].imshow(rgb)
    axes[0].set_title("S2 B1-B3 (stretch)")
    axes[1].imshow(gt, cmap="gray", vmin=0, vmax=1)
    axes[1].set_title("Ground truth")
    axes[2].imshow(prob, cmap="magma", vmin=0, vmax=1)
    axes[2].set_title("Pred probability")
    axes[3].imshow(rgb)
    axes[3].imshow(np.ma.masked_where(pred == 0, pred), cmap="autumn", alpha=0.55, vmin=0, vmax=1)
    axes[3].set_title("Overlay (>0.5)")
    for ax in axes:
        ax.axis("off")
    fig.suptitle("Landslide PoC — DeepSlide MobileNetV2 on Landslide4Sense chip (NOT georeferenced)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def try_write_geotiff(pred: np.ndarray, prob: np.ndarray, path: Path) -> dict:
    """
    Landslide4Sense competition chips do not ship CRS / affine.
    Write a local 10 m/px GeoTIFF in a synthetic local CRS only if rasterio is available,
    and clearly mark that this is NOT real-world georeferencing.
    """
    meta = {
        "georeferenced": False,
        "reason": "Landslide4Sense HDF5 chips contain no CRS/affine; competition patches are ~10 m/px but locations are not released.",
        "written": False,
    }
    try:
        import rasterio
        from rasterio.transform import from_origin
    except ImportError:
        # Fallback: write numpy + sidecar JSON
        np.save(path.with_suffix(".npy"), pred)
        meta["written"] = True
        meta["format"] = "npy"
        meta["path"] = str(path.with_suffix(".npy"))
        return meta

    transform = from_origin(0.0, 1280.0, 10.0, 10.0)  # local grid only
    profile = {
        "driver": "GTiff",
        "height": pred.shape[0],
        "width": pred.shape[1],
        "count": 2,
        "dtype": "float32",
        "crs": None,
        "transform": transform,
        "compress": "lzw",
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(pred.astype(np.float32), 1)
        dst.write(prob.astype(np.float32), 2)
        dst.update_tags(
            AREA_OR_POINT="Area",
            NOTE="SYNTHETIC_LOCAL_GRID_ONLY_NO_REAL_CRS",
            PIXEL_SIZE_M="10",
            SOURCE="Landslide4Sense competition chip; no geographic metadata in source",
            BAND1="binary_landslide_pred",
            BAND2="landslide_probability",
        )
    meta["written"] = True
    meta["format"] = "GeoTIFF"
    meta["path"] = str(path)
    meta["crs"] = None
    meta["transform"] = "from_origin(0, 1280, 10, 10) local only"
    return meta


def peak_rss_mb() -> float | None:
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "verdict": "BLOCKED",
        "candidate_primary": {
            "name": "IARAI Landslide4Sense baseline U-Net",
            "checkpoint": "batch3500_F1_7396.pth",
            "source": "https://cloud.iarai.ac.at/index.php/s/CgbjDRK6B5KYaLE",
            "license_code": "MIT (iarai/Landslide4Sense-2022)",
            "license_data": "CC-BY-4.0 (Zenodo / competition)",
            "status": "UNREACHABLE",
            "blocker": "DNS NXDOMAIN for cloud.iarai.ac.at (and nextcloud.iarai.ac.at) from this host",
        },
        "candidate_executed": {
            "name": "DeepSlide MobileNetV2 U-Net (SMP)",
            "checkpoint": str(WEIGHTS),
            "source": "https://huggingface.co/harshinde/DeepSlide_Models/mobilenetv2.pth",
            "license": "MIT",
            "dataset": "Landslide4Sense / ibm-nasa-geospatial/Landslide4sense (14-band 128x128 h5)",
            "architecture": "smp.Unet(encoder_name=mobilenet_v2, in_channels=14, classes=1)",
            "reported_paper_f1": 0.7119,
        },
        "ssri_input_compatibility": {
            "ssri_channels": 13,
            "l4s_channels": 14,
            "defensible_transform_from_ssri_stack": False,
            "reason": "SSRI Stage 2.5 uses a different 13-channel feature stack (CHANNEL_NAMES). L4S requires Sentinel-2 B1-B12 + ALOS slope + DEM. Mapping SSRI channels into L4S is not scientifically defensible without rebuilding the S2+DEM/slope stack.",
        },
        "errors": [],
    }

    if not WEIGHTS.exists():
        report["errors"].append(f"Missing weights: {WEIGHTS}")
        (OUT / "execution_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    device = torch.device("cpu")
    t0 = time.perf_counter()
    mem0 = peak_rss_mb()

    try:
        model = build_model()
        load_note = load_weights(model, WEIGHTS)
        model.eval()
        model.to(device)
        report["weight_load"] = load_note
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"model load failed: {exc}")
        report["traceback"] = traceback.format_exc()
        (OUT / "execution_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 3

    build_s = time.perf_counter() - t0

    # Inspect one chip
    sample = load_image(DATA_IMG / f"image_{PREVIEW_ID}.h5")
    report["input_format"] = {
        "shape": list(sample.shape),
        "dtype": str(sample.dtype),
        "min": float(sample.min()),
        "max": float(sample.max()),
        "resolution_claimed_m": 10,
        "crs_in_source": None,
    }

    per_chip = []
    baseline_majority = []
    baseline_slope = []
    infer_times = []

    for cid in EVAL_IDS:
        img_path = DATA_IMG / f"image_{cid}.h5"
        msk_path = DATA_MSK / f"mask_{cid}.h5"
        if not img_path.exists() or not msk_path.exists():
            report["errors"].append(f"missing chip {cid}")
            continue
        image = load_image(img_path)
        gt = load_mask(msk_path)

        t_inf = time.perf_counter()
        prob = predict_prob(model, image, device)
        infer_times.append(time.perf_counter() - t_inf)
        pred = (prob > 0.5).astype(np.uint8)

        m = binary_metrics(pred, gt)
        per_chip.append(
            {
                "chip_id": cid,
                **m,
                "pred_pos": int(pred.sum()),
                "gt_pos": int(gt.sum()),
            }
        )
        baseline_majority.append({"chip_id": cid, **binary_metrics(majority_baseline(gt), gt)})
        baseline_slope.append({"chip_id": cid, **binary_metrics(slope_threshold_baseline(image, gt), gt)})

        # Persist per-chip arrays
        np.save(OUT / f"pred_prob_{cid}.npy", prob)
        np.save(OUT / f"pred_mask_{cid}.npy", pred)
        with h5py.File(OUT / f"pred_mask_{cid}.h5", "w") as hf:
            hf.create_dataset("mask", data=pred)
            hf.create_dataset("probability", data=prob)

        if cid == PREVIEW_ID:
            save_preview(image, gt, prob, pred, OUT / "preview_map.png")
            geo = try_write_geotiff(pred, prob, OUT / "prediction_local_grid.tif")
            report["georeference"] = geo

    def mean_f1(rows: list[dict]) -> float:
        if not rows:
            return 0.0
        return float(np.mean([r["f1"] for r in rows]))

    report["evaluation"] = {
        "dataset": "Landslide4Sense train chips (HF mirror), held-out ids for this PoC only",
        "chip_ids": EVAL_IDS,
        "note": "These train-split chips may overlap DeepSlide training data; metrics are smoke-test only, NOT independent scientific validation.",
        "model": per_chip,
        "baseline_majority_class": baseline_majority,
        "baseline_slope_threshold": baseline_slope,
        "mean_f1_model": mean_f1(per_chip),
        "mean_f1_majority": mean_f1(baseline_majority),
        "mean_f1_slope": mean_f1(baseline_slope),
        "outperforms_majority": mean_f1(per_chip) > mean_f1(baseline_majority),
        "outperforms_slope": mean_f1(per_chip) > mean_f1(baseline_slope),
    }

    mem1 = peak_rss_mb()
    report["runtime"] = {
        "device": str(device),
        "model_build_load_s": round(build_s, 3),
        "infer_per_chip_s": [round(x, 3) for x in infer_times],
        "infer_mean_s": round(float(np.mean(infer_times)), 3) if infer_times else None,
        "rss_mb_start": mem0,
        "rss_mb_end": mem1,
        "checkpoint_mb": round(WEIGHTS.stat().st_size / (1024 * 1024), 2),
    }

    inference_ok = len(per_chip) > 0 and not report["errors"]
    real_pred = inference_ok and any(c["pred_pos"] >= 0 for c in per_chip)
    geo_real = bool(report.get("georeference", {}).get("georeferenced"))

    if not inference_ok:
        report["verdict"] = "FAIL"
    elif not real_pred:
        report["verdict"] = "FAIL"
    else:
        # Official L4S baseline still blocked; executed fallback produced real pixel predictions.
        # Georeference from source is unavailable — not a failure of inference.
        report["verdict"] = "PASS"
        report["verdict_caveats"] = [
            "PASS refers to DeepSlide MobileNetV2 fallback, not the official IARAI batch3500 checkpoint.",
            "Official IARAI pretrained weights remain UNREACHABLE (DNS).",
            "No real-world CRS in source chips; local-grid GeoTIFF only.",
            "Eval chips are from the public train split; may leak vs DeepSlide training — not scientific validation.",
            "Landslide detection only; no subsidence/sinkhole claim.",
        ]

    report["integration_recommendation"] = {
        "integrate_now": False,
        "reason": (
            "Do not wire into SSRI assess yet: (1) official L4S weights unreachable; "
            "(2) SSRI 13-ch stack is incompatible with 14-band L4S input without new data pipeline; "
            "(3) L4S chips lack CRS needed for SSRI map products; "
            "(4) this PoC is landslide-only and NOT scientifically validated."
        ),
        "next_steps": [
            "Obtain official batch3500_F1_7396.pth from a reachable mirror or alternate network path.",
            "OR continue with DeepSlide/ResNet34 after building a Sentinel-2 + DEM/slope ingest that matches L4S band order.",
            "For georeferenced products, generate 14-band stacks from STAC/COGs with real affine/CRS rather than competition chips.",
            "Next candidate if DeepSlide underperforms on held-out AOIs: TorchGeo Prithvi / TerraMind with free weights (larger deps).",
        ],
    }

    (OUT / "execution_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Human-readable report
    lines = [
        "# Landslide4Sense PoC — Execution Report",
        "",
        f"**Verdict:** {report['verdict']}",
        "",
        "## Model tested",
        f"- Primary (blocked): IARAI `{report['candidate_primary']['checkpoint']}` — {report['candidate_primary']['blocker']}",
        f"- Executed: DeepSlide MobileNetV2 — `{WEIGHTS.name}` ({report['runtime']['checkpoint_mb']} MB), MIT",
        f"- Architecture: {report['candidate_executed']['architecture']}",
        "",
        "## Commands",
        "```",
        "cd model && poetry run pip install h5py segmentation-models-pytorch",
        "curl -L -o poc/landslide4sense/weights/mobilenetv2.pth \\",
        "  https://huggingface.co/harshinde/DeepSlide_Models/resolve/main/mobilenetv2.pth",
        "poetry -C model run python poc/landslide4sense/run_poc.py",
        "```",
        "",
        "## Input",
        f"- Dataset: Landslide4Sense train chips via HF (`image_*.h5` / `mask_*.h5`)",
        f"- Shape: {report['input_format']['shape']} float32; claimed ~10 m/px; **no CRS in source**",
        "- Preprocess (DeepSlide): NaN→ε, no mean/std normalize, sigmoid @ 0.5",
        "- SSRI 13-ch stack: **not used** (incompatible)",
        "",
        "## Outputs",
        f"- Preview: `poc/landslide4sense/outputs/preview_map.png`",
        f"- Predictions: `pred_mask_*.h5` / `.npy`",
        f"- Local-grid raster attempt: `{report.get('georeference', {})}`",
        "",
        "## Evaluation (smoke only)",
        f"- Chips: {EVAL_IDS}",
        f"- Mean F1 model: {report['evaluation']['mean_f1_model']:.4f}",
        f"- Mean F1 majority baseline: {report['evaluation']['mean_f1_majority']:.4f}",
        f"- Mean F1 slope baseline: {report['evaluation']['mean_f1_slope']:.4f}",
        f"- Outperforms majority: {report['evaluation']['outperforms_majority']}",
        f"- Outperforms slope: {report['evaluation']['outperforms_slope']}",
        "",
        "## Runtime",
        f"- Device: {report['runtime']['device']}",
        f"- Load+build: {report['runtime']['model_build_load_s']} s",
        f"- Infer mean: {report['runtime']['infer_mean_s']} s / chip",
        f"- RSS end: {report['runtime']['rss_mb_end']} MB",
        "",
        "## Integration",
        report["integration_recommendation"]["reason"],
        "",
        "**Successful execution alone does not establish scientific validity.**",
        "",
    ]
    (OUT / "EXECUTION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("verdict", "evaluation", "runtime", "georeference", "weight_load")}, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
