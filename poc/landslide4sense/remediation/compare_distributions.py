"""Compare Landslide4Sense HDF5 tensors vs STAC physical-unit stack, channel-by-channel."""
from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "remediation" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

BANDS = [f"B{i}" for i in range(1, 13)] + ["slope", "DEM"]

# Official IARAI baseline stats (computed on competition train HDF5; used by baseline U-Net only)
IARAI_MEAN = np.array(
    [-0.4914, -0.3074, -0.1277, -0.0625, 0.0439, 0.0803, 0.0644, 0.0802, 0.3000, 0.4082, 0.0823, 0.0516, 0.3338, 0.7819],
    dtype=np.float64,
)
IARAI_STD = np.array(
    [0.9325, 0.8775, 0.8860, 0.8869, 0.8857, 0.8418, 0.8354, 0.8491, 0.9061, 1.6072, 0.8848, 0.9232, 0.9018, 1.2913],
    dtype=np.float64,
)


def load_l4s_chip(path: Path) -> np.ndarray:
    with h5py.File(path, "r") as f:
        arr = np.array(f["img"], dtype=np.float64)
    if arr.shape[-1] == 14:
        arr = np.transpose(arr, (2, 0, 1))
    return arr


def stats(arr: np.ndarray) -> dict:
    flat = arr.reshape(arr.shape[0], -1)
    return {
        "min": flat.min(axis=1).tolist(),
        "max": flat.max(axis=1).tolist(),
        "mean": flat.mean(axis=1).tolist(),
        "std": flat.std(axis=1).tolist(),
        "p01": np.percentile(flat, 1, axis=1).tolist(),
        "p50": np.percentile(flat, 50, axis=1).tolist(),
        "p99": np.percentile(flat, 99, axis=1).tolist(),
        "frac_neg": (flat < 0).mean(axis=1).tolist(),
        "frac_gt1": (flat > 1).mean(axis=1).tolist(),
        "frac_gt10": (flat > 10).mean(axis=1).tolist(),
    }


def main() -> None:
    val_imgs = sorted((ROOT / "data" / "validation" / "images").glob("image_*.h5"))
    train_imgs = sorted((ROOT / "data" / "images").glob("image_*.h5"))
    chips = val_imgs[:40] if len(val_imgs) >= 10 else train_imgs
    assert chips, "no L4S chips"

    stacks = [load_l4s_chip(p) for p in chips]
    flat = np.concatenate([s.reshape(14, -1) for s in stacks], axis=1)
    l4s_stats = {
        "n_chips": len(chips),
        "n_pixels_per_band": int(flat.shape[1]),
        "min": flat.min(axis=1).tolist(),
        "max": flat.max(axis=1).tolist(),
        "mean": flat.mean(axis=1).tolist(),
        "std": flat.std(axis=1).tolist(),
        "p01": np.percentile(flat, 1, axis=1).tolist(),
        "p50": np.percentile(flat, 50, axis=1).tolist(),
        "p99": np.percentile(flat, 99, axis=1).tolist(),
        "frac_neg": (flat < 0).mean(axis=1).tolist(),
        "frac_gt1": (flat > 1).mean(axis=1).tolist(),
        "frac_gt10": (flat > 10).mean(axis=1).tolist(),
    }

    stac_path = ROOT / "validation" / "outputs" / "georef" / "input_stack_14chw.npy"
    stac_report = {"present": stac_path.exists()}
    if stac_path.exists():
        stac = np.load(stac_path).astype(np.float64)
        sf = stac.reshape(14, -1)
        stac_report.update(
            {
                "shape": list(stac.shape),
                "min": sf.min(axis=1).tolist(),
                "max": sf.max(axis=1).tolist(),
                "mean": sf.mean(axis=1).tolist(),
                "std": sf.std(axis=1).tolist(),
                "p01": np.percentile(sf, 1, axis=1).tolist(),
                "p50": np.percentile(sf, 50, axis=1).tolist(),
                "p99": np.percentile(sf, 99, axis=1).tolist(),
                "frac_neg": (sf < 0).mean(axis=1).tolist(),
                "frac_gt1": (sf > 1).mean(axis=1).tolist(),
                "frac_gt10": (sf > 10).mean(axis=1).tolist(),
            }
        )
        # mean absolute difference of means / ratio of stds
        mean_ratio = []
        std_ratio = []
        for i in range(14):
            lm, sm = l4s_stats["mean"][i], stac_report["mean"][i]
            ls, ss = l4s_stats["std"][i], stac_report["std"][i]
            mean_ratio.append(None if abs(sm) < 1e-12 else lm / sm)
            std_ratio.append(None if abs(ss) < 1e-12 else ls / ss)
        stac_report["l4s_mean_over_stac_mean"] = mean_ratio
        stac_report["l4s_std_over_stac_std"] = std_ratio

    report = {
        "band_names": BANDS,
        "deepslide_documented_preprocess": {
            "source": "HarshShinde0/Deepslide streamlit config",
            "normalize": False,
            "channels": list(range(1, 15)),
            "activation": "sigmoid",
            "threshold": 0.5,
            "note": "DeepSlide loads competition HDF5 as float; no mean/std in training config.",
        },
        "iarai_baseline_stats_on_competition_hdf5": {
            "mean": IARAI_MEAN.tolist(),
            "std": IARAI_STD.tolist(),
            "note": "Used by official baseline U-Net only; DeepSlide config sets normalize=False so these are NOT applied at DeepSlide inference.",
        },
        "authoritative_packaging_scale": {
            "status": "UNPUBLISHED",
            "evidence": [
                "IARAI issue #4 asks how bands were normalized; no maintainer answer in API comments.",
                "Paper describes resampling to 10 m but does not publish radiometric packaging formula.",
                "IARAI mean/std are empirical on packaged tensors, not a recipe to build them from STAC.",
            ],
        },
        "l4s_empirical": l4s_stats,
        "stac_physical": stac_report,
    }
    (OUT / "distribution_compare.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # human table
    lines = ["band,l4s_mean,l4s_std,l4s_min,l4s_max,stac_mean,stac_std,stac_min,stac_max"]
    for i, name in enumerate(BANDS):
        row = [
            name,
            f"{l4s_stats['mean'][i]:.4f}",
            f"{l4s_stats['std'][i]:.4f}",
            f"{l4s_stats['min'][i]:.4f}",
            f"{l4s_stats['max'][i]:.4f}",
        ]
        if stac_path.exists():
            row += [
                f"{stac_report['mean'][i]:.4f}",
                f"{stac_report['std'][i]:.4f}",
                f"{stac_report['min'][i]:.4f}",
                f"{stac_report['max'][i]:.4f}",
            ]
        lines.append(",".join(row))
    (OUT / "distribution_compare.csv").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"n_chips": len(chips), "stac": stac_path.exists(), "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
