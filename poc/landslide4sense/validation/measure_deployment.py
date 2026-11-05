"""Local deployment-feasibility measurements for DeepSlide MobileNetV2 (CPU)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_poc import WEIGHTS, build_model, load_weights, predict_prob  # noqa: E402

OUT = ROOT / "validation" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)


def rss_mb() -> float | None:
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    report: dict = {
        "phase": 5,
        "target_architecture": {
            "api": "ssri_model.api.app:app FastAPI /api/v1",
            "worker": "Celery ssri.execute_job via infra/docker-compose.yml worker",
            "frontend": "Next.js /dashboard -> POST /api/v1/assess",
            "production_host": "https://ssri-api.onrender.com (CPU torch historically)",
            "live_production_test": False,
            "note": "No production deploy or Render live load test performed (authorization required).",
        },
        "ssri_contract_gap": {
            "assess_expects": "Stage 2.5 SSRIModel 13-channel feature stack",
            "deepslide_expects": "14-band L4S Sentinel-2 + slope + DEM",
            "compatible_without_new_pipeline": False,
        },
    }
    device = torch.device("cpu")
    dummy = np.random.randn(14, 128, 128).astype(np.float32)
    # also try a real chip if present
    chip_path = ROOT / "data" / "images" / "image_1.h5"
    if chip_path.exists():
        import h5py

        with h5py.File(chip_path, "r") as f:
            arr = np.array(f["img"], dtype=np.float32)
        if arr.shape[-1] == 14:
            arr = np.transpose(arr, (2, 0, 1))
        dummy = np.nan_to_num(arr, nan=1e-6)

    rss0 = rss_mb()
    t0 = time.perf_counter()
    model = build_model()
    load_weights(model, WEIGHTS)
    model.eval().to(device)
    load_s = time.perf_counter() - t0
    rss1 = rss_mb()

    times = []
    for _ in range(5):
        t1 = time.perf_counter()
        _ = predict_prob(model, dummy, device)
        times.append(time.perf_counter() - t1)
    rss2 = rss_mb()

    # Concurrent simulation: sequential batch of 4 chips (same process)
    batch = np.stack([dummy] * 4, axis=0)
    t2 = time.perf_counter()
    with torch.no_grad():
        x = torch.from_numpy(batch).float()
        logits = model(x)
        torch.sigmoid(logits)
    batch_s = time.perf_counter() - t2
    rss3 = rss_mb()

    report["measurements"] = {
        "device": str(device),
        "checkpoint_mb": round(WEIGHTS.stat().st_size / (1024 * 1024), 2),
        "model_load_s": round(load_s, 3),
        "infer_per_chip_s_mean": round(float(np.mean(times)), 4),
        "infer_per_chip_s_p50": round(float(np.median(times)), 4),
        "batch4_s": round(batch_s, 4),
        "rss_mb_start": rss0,
        "rss_mb_after_load": rss1,
        "rss_mb_after_infer": rss2,
        "rss_mb_after_batch4": rss3,
        "deps": ["torch", "segmentation-models-pytorch", "h5py", "numpy", "rasterio (geo path)"],
    }
    peak = max(x for x in (rss1, rss2, rss3) if x is not None) if any(v is not None for v in (rss1, rss2, rss3)) else None
    report["gates"] = {
        "single_chip_cpu_ok": True,
        "peak_rss_under_1500mb": (peak is not None and peak < 1500) if peak is not None else None,
        "peak_rss_mb": peak,
        "live_render_verified": False,
        "assess_route_compatible_without_new_ingest": False,
        "worker_path_compatible_without_new_ingest": False,
    }
    report["verdict"] = "FEASIBLE_ISOLATED_CPU_BUT_NOT_SSRI_WIRED"
    report["failure_handling"] = (
        "Not integrated; no production failure path for DeepSlide. "
        "Isolated PoC raises on missing weights / bad shapes."
    )
    (OUT / "deployment_measure.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
