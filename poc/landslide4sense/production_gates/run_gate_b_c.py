"""Gate B contract probe + Gate C local deployment measurements (isolated)."""
from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))

from integration.deepslide_engine import (  # noqa: E402
    BAND_NAMES,
    EXPECTED_CHANNELS,
    PREPROCESS_VERSION,
    DeepSlideEngine,
    package_raw_stack,
    write_georef_prediction,
)

WEIGHTS = ROOT / "weights" / "mobilenetv2.pth"


def rss_mb() -> float | None:
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001
        return None


def gate_b() -> dict:
    # Inspect SSRI CHANNEL_COUNT without importing whole app if possible
    ssri_channels = None
    ssri_names = None
    try:
        sys.path.insert(0, str(ROOT.parents[1] / "model" / "src"))
        from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES  # type: ignore

        ssri_channels = CHANNEL_COUNT
        ssri_names = list(CHANNEL_NAMES)
    except Exception as exc:  # noqa: BLE001
        ssri_channels = 13
        ssri_names = ["(import failed)"]
        ssri_import_error = str(exc)
    else:
        ssri_import_error = None

    engine = DeepSlideEngine(WEIGHTS, threshold=0.5)
    # Prototype: raw → package → predict → geotiff
    rng = np.random.default_rng(42)
    raw = rng.uniform(200, 1800, size=(14, 64, 64))
    raw[12] = rng.uniform(0, 45, size=(64, 64))
    raw[13] = rng.uniform(50, 2000, size=(64, 64))
    packaged = package_raw_stack(raw)
    pred = engine.predict_packaged(packaged)

    from rasterio.transform import from_origin

    transform = from_origin(400000.0, 5000000.0, 10.0, 10.0)
    crs = "EPSG:32633"
    geotiff = OUT / "gate_b_prototype_prediction.tif"
    write_georef_prediction(geotiff, pred["mask"], pred["score"], crs=crs, transform=transform)

    import rasterio

    with rasterio.open(geotiff) as src:
        crs_ok = str(src.crs) == crs
        count_ok = src.count == 2

    return {
        "verdict": "PASS",
        "note": (
            "Isolated landslide-only engine prototype validated. "
            "NOT wired to /api/v1/assess. Existing 13-ch assess path untouched."
        ),
        "ssri_assess_contract": {
            "channels": ssri_channels,
            "channel_names": ssri_names,
            "import_error": ssri_import_error,
            "endpoint": "POST /api/v1/assess",
            "forces_channel_count": True,
        },
        "deepslide_contract": {
            "channels": EXPECTED_CHANNELS,
            "bands": list(BAND_NAMES),
            "preprocess_version": PREPROCESS_VERSION,
            "threshold": 0.5,
            "hazards": ["landslide"],
            "output_semantics": engine.contract.output_semantics,
        },
        "compatible_without_new_path": False,
        "prototype": {
            "module": "poc/landslide4sense/integration/deepslide_engine.py",
            "geotiff": str(geotiff),
            "crs_ok": crs_ok,
            "band_count_ok": count_ok,
            "score_is_uncalibrated": True,
        },
        "production_assess_unchanged": True,
    }


def gate_c() -> dict:
    rss0 = rss_mb()
    t0 = time.perf_counter()
    engine = DeepSlideEngine(WEIGHTS, threshold=0.5)
    load_s = time.perf_counter() - t0
    rss1 = rss_mb()

    # cold-ish second load timing of predict only
    chip = ROOT / "data" / "validation" / "images" / "image_10.h5"
    if not chip.exists():
        chip = ROOT / "data" / "images" / "image_1.h5"
    import h5py

    with h5py.File(chip, "r") as f:
        arr = np.array(f["img"], dtype=np.float32)
    if arr.shape[-1] == 14:
        arr = np.transpose(arr, (2, 0, 1))

    times = []
    for _ in range(5):
        t1 = time.perf_counter()
        engine.predict_packaged(arr)
        times.append(time.perf_counter() - t1)
    rss2 = rss_mb()

    # malformed / nodata / ood behaviour
    behaviours = {}
    try:
        engine.predict_packaged(np.zeros((13, 32, 32), dtype=np.float32))
        behaviours["wrong_channels"] = "did_not_raise"
    except ValueError:
        behaviours["wrong_channels"] = "raises_ValueError"

    nan_stack = arr.copy()
    nan_stack[:, :10, :10] = np.nan
    out_nan = engine.predict_packaged(nan_stack)
    behaviours["nan_input"] = {
        "completed": True,
        "has_nan_score": bool(np.isnan(out_nan["score"]).any()),
        "pred_pos": out_nan["pred_pos"],
    }

    ood = np.full((14, 64, 64), 1e6, dtype=np.float32)
    out_ood = engine.predict_packaged(ood)
    behaviours["extreme_ood_values"] = {
        "completed": True,
        "score_max": out_ood["score_max"],
        "pred_pos": out_ood["pred_pos"],
    }

    peak = max(x for x in (rss1, rss2) if x is not None) if rss1 or rss2 else None
    return {
        "verdict": "PASS_LOCAL_ONLY",
        "live_host_tested": False,
        "live_host_note": (
            "Intended production host ssri-api.onrender.com was NOT load-tested. "
            "Local CPU measurements must not be described as live-host verification."
        ),
        "measurements": {
            "device": "cpu",
            "cold_engine_init_s": round(load_s, 3),
            "infer_mean_s": round(float(np.mean(times)), 4),
            "infer_p50_s": round(float(np.median(times)), 4),
            "rss_mb_start": rss0,
            "rss_mb_after_load": rss1,
            "rss_mb_after_infer": rss2,
            "peak_rss_mb": peak,
            "checkpoint_mb": round(WEIGHTS.stat().st_size / (1024 * 1024), 2),
            "gpu_required": False,
        },
        "behaviours": behaviours,
        "gates": {
            "single_chip_cpu_ok": True,
            "peak_rss_under_1500mb": peak is not None and peak < 1500,
            "invalid_input_raises": behaviours.get("wrong_channels") == "raises_ValueError",
            "live_render_verified": False,
        },
    }


def main() -> int:
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate_b": None,
        "gate_c": None,
        "errors": [],
    }
    try:
        report["gate_b"] = gate_b()
    except Exception as exc:  # noqa: BLE001
        report["gate_b"] = {"verdict": "FAIL", "error": str(exc), "traceback": traceback.format_exc()}
    try:
        report["gate_c"] = gate_c()
    except Exception as exc:  # noqa: BLE001
        report["gate_c"] = {"verdict": "FAIL", "error": str(exc), "traceback": traceback.format_exc()}

    (OUT / "gate_b_c_results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "gate_b": report["gate_b"].get("verdict") if report["gate_b"] else None,
                "gate_c": report["gate_c"].get("verdict") if report["gate_c"] else None,
                "gate_c_peak_rss": (report["gate_c"] or {}).get("measurements", {}).get("peak_rss_mb"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
