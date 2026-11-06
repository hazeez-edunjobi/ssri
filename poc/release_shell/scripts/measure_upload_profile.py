"""SYNTHETIC upload/memory profile for the release shell.

Measures, for BOTH channel schemas (v1 = 13 channels, v2 = 16 channels):

  * >= 300,000 cells, >= 8 distinct 5-degree blocks
  * ZIP upload time
  * validation time
  * training time PER SEED (one single-seed job per seed)
  * peak process RSS

This is SYNTHETIC data and NOT geological truth. Numbers are host-specific and
are meant to inform SSRI_UPLOAD_MAX_BYTES / memory guidance, not to be replicated
exactly. LOCAL ONLY.

Run:
    poetry -C model run python ../poc/release_shell/scripts/measure_upload_profile.py
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

REPO = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "outputs" / "measure_upload_profile"

# 9 blocks x 3 tiles x 128 x 128 = 442,368 cells (>= 300,000)
BLOCK_CENTERS = [
    (32.5, -117.5),
    (37.5, -122.5),
    (42.5, -122.5),
    (47.5, -122.5),
    (32.5, -110.5),
    (37.5, -110.5),
    (42.5, -105.5),
    (35.5, -95.5),
    (40.5, -85.5),
]
TILE = 128
TILES_PER_BLOCK = 3
SEEDS = [42, 43, 44]


def _peak_rss_mb() -> float:
    try:
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            c = PMC()
            c.cb = ctypes.sizeof(PMC)
            h = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb)
            return c.PeakWorkingSetSize / (1024 * 1024)
        except Exception:
            return -1.0
    return -1.0


def _build_stage25(
    root: Path, channel_names: tuple[str, ...], schema_version: str
) -> tuple[Path, int]:
    from ssri_model.dataset.catalog import write_manifest, write_statistics
    from ssri_model.ml.constants import LABEL_NODATA
    from ssri_model.ml.splits import DatasetSplit

    stage = root / "stage25"
    n_ch = len(channel_names)
    train_ids: list[str] = []
    val_ids: list[str] = []
    total_cells = 0
    stats_acc = {
        name: {"min": math.inf, "max": -math.inf, "sum": 0.0, "sumsq": 0.0, "n": 0}
        for name in channel_names
    }
    for bi, (lat, lon) in enumerate(BLOCK_CENTERS):
        for ti in range(TILES_PER_BLOCK):
            sid = f"b{bi}_t{ti}"
            split_name = "validation" if bi >= 7 else "train"
            sample = stage / split_name / sid
            sample.mkdir(parents=True)
            yy, xx = np.mgrid[0:TILE, 0:TILE]
            stack = np.zeros((n_ch, TILE, TILE), dtype=np.float32)
            for ch in range(n_ch):
                stack[ch] = (
                    (ch + 1) * 0.1 + 0.01 * xx + 0.02 * yy + 0.05 * ti + 0.1 * bi
                )
            for ch, name in enumerate(channel_names):
                vals = stack[ch].astype(np.float64)
                acc = stats_acc[name]
                acc["min"] = min(acc["min"], float(vals.min()))
                acc["max"] = max(acc["max"], float(vals.max()))
                acc["sum"] += float(vals.sum())
                acc["sumsq"] += float((vals * vals).sum())
                acc["n"] += int(vals.size)
            labels = np.zeros((TILE, TILE), dtype=np.int16)
            labels[20:80, 20:80] = 1
            labels[90:120, 90:120] = 0
            np.save(sample / "feature_stack.npy", stack)
            with rasterio.open(
                sample / "label.tif",
                "w",
                driver="GTiff",
                height=TILE,
                width=TILE,
                count=1,
                dtype="float32",
                crs="EPSG:4326",
                transform=from_origin(lon - 0.05 + ti * 0.01, lat + 0.05, 0.0005, 0.0005),
                nodata=float(LABEL_NODATA),
            ) as ds:
                ds.write(labels.astype(np.float32), 1)
            (sample / "metadata.json").write_text(
                json.dumps(
                    {
                        "sample_id": sid,
                        "crs": "EPSG:4326",
                        "centroid_lat": lat + ti * 0.01,
                        "centroid_lon": lon + ti * 0.01,
                        "resolution_m": 30,
                        "source_format": "SYNTHETIC",
                        "synthetic": True,
                        "channel_schema_version": schema_version,
                        "notes": "SYNTHETIC profile; not geological truth",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "label_classes": ["subsidence", "landslide", "sinkhole"],
                    }
                ),
                encoding="utf-8",
            )
            total_cells += TILE * TILE
            (val_ids if split_name == "validation" else train_ids).append(sid)
    split = DatasetSplit(train=tuple(train_ids), validation=tuple(val_ids), test=())
    write_statistics(stage, split=split)
    write_manifest(
        stage,
        dataset_name=f"SYNTHETIC-profile-{n_ch}ch",
        version=f"synthetic-{n_ch}ch",
        split=split,
        crs="EPSG:4326",
        resolution_m=30.0,
    )
    # Per-channel stats for ALL channels. write_statistics only emits the v1
    # channel list, so the v2 trainer would fail with
    # "Statistics missing channels: overburden_thickness, ...". Overwrite with
    # the real accumulated stats for the declared schema.
    channel_stats: dict[str, dict[str, float]] = {}
    for name in channel_names:
        acc = stats_acc[name]
        n = int(acc["n"])
        mean = acc["sum"] / n if n else 0.0
        var = max(acc["sumsq"] / n - mean * mean, 0.0) if n else 0.0
        channel_stats[name] = {
            "min": float(acc["min"]) if n else 0.0,
            "max": float(acc["max"]) if n else 0.0,
            "mean": mean,
            "std": math.sqrt(var),
            "valid_count": float(n),
            "nodata_count": 0.0,
        }

    # Declare the channel schema so the validator expects the right depth.
    # channels/channel_names must be OVERWRITTEN (write_manifest emits a v1
    # list by default), otherwise the classic validator sees 13 vs 16.
    for name in ("manifest.json", "statistics.json"):
        p = stage / name
        payload = json.loads(p.read_text(encoding="utf-8"))
        payload["channel_schema_version"] = schema_version
        payload["channels"] = list(channel_names)
        payload["channel_names"] = list(channel_names)
        payload["synthetic"] = True
        if name == "statistics.json":
            payload["channel_stats"] = channel_stats
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return stage, total_cells


def _zip_stage(stage: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in stage.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(stage).as_posix())


def _run_schema(client, schema: str, channel_names: tuple[str, ...]) -> dict:
    import numpy as np  # noqa: F811

    from ssri_model.ml.constants import LABEL_NODATA  # noqa: F401

    root = OUT / schema
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    t0 = time.perf_counter()
    stage, total_cells = _build_stage25(root, channel_names, schema)
    gen_s = time.perf_counter() - t0
    zip_path = root / f"SYNTHETIC_{schema}_stage25.zip"
    _zip_stage(stage, zip_path)
    zip_bytes = zip_path.stat().st_size

    created = client.post(
        "/api/v1/training/datasets",
        json={"name": f"SYNTHETIC-profile-{schema}", "description": "SYNTHETIC profile"},
    )
    ds_id = created.json()["dataset"]["dataset_id"]

    t_up = time.perf_counter()
    up = client.post(
        f"/api/v1/release-shell/datasets/{ds_id}/upload",
        files={"file": (zip_path.name, zip_path.read_bytes(), "application/zip")},
    )
    upload_s = time.perf_counter() - t_up

    t_val = time.perf_counter()
    val = client.post(f"/api/v1/release-shell/datasets/{ds_id}/validate")
    validate_s = time.perf_counter() - t_val
    val_body = val.json().get("validation", {})

    per_seed: dict[str, dict] = {}
    for seed in SEEDS:
        t_tr = time.perf_counter()
        train = client.post(
            "/api/v1/release-shell/jobs",
            json={
                "dataset_id": ds_id,
                "epochs": 1,
                "batch_size": 2,
                "seeds": [seed],
                "model_name": f"SYNTHETIC-{schema}",
                "device": "cpu",
            },
        )
        started = train.status_code in {200, 202}
        elapsed = None
        completed = False
        job_id = train.json().get("job_id") if started else None
        if job_id:
            for _ in range(900):
                status = client.get(f"/api/v1/jobs/{job_id}").json()
                st = str(
                    status.get("status") or (status.get("job") or {}).get("status") or ""
                ).lower()
                if st in {"completed", "succeeded", "success"}:
                    completed = True
                    break
                if st in {"failed", "cancelled", "error"}:
                    break
                time.sleep(1)
            elapsed = time.perf_counter() - t_tr
        per_seed[str(seed)] = {
            "started": started,
            "completed": completed,
            "wall_s": None if elapsed is None else round(elapsed, 2),
        }

    return {
        "schema": schema,
        "channels": len(channel_names),
        "distinct_5deg_blocks": len(BLOCK_CENTERS),
        "tiles": len(BLOCK_CENTERS) * TILES_PER_BLOCK,
        "total_cells": total_cells,
        "zip_bytes": zip_bytes,
        "zip_mib": round(zip_bytes / (1024 * 1024), 2),
        "generate_s": round(gen_s, 2),
        "upload_s": round(upload_s, 2),
        "validate_s": round(validate_s, 2),
        "validate_overall": val_body.get("overall"),
        "can_train": val_body.get("can_train"),
        "channel_schema_version": val_body.get("channel_schema"),
        "per_seed": per_seed,
        "peak_rss_mb": round(_peak_rss_mb(), 1),
    }


def main() -> int:
    os.environ["SSRI_RELEASE_SHELL"] = "true"
    os.environ["SSRI_RELEASE_SHELL_MIN_TILES"] = "8"
    os.environ["SSRI_RELEASE_SHELL_MIN_BLOCKS"] = "8"
    os.environ["SSRI_RELEASE_SHELL_MIN_HELD_OUT"] = "2"

    sys.path.insert(0, str(REPO / "model" / "src"))
    sys.path.insert(0, str(REPO / "model"))
    sys.path.insert(0, str(REPO / "model" / "tests"))

    from fastapi.testclient import TestClient

    from ssri_model.api.app import create_app
    from ssri_model.release_shell.channel_schema import CHANNEL_NAMES_V1, CHANNEL_NAMES_V2
    from api_helpers import build_api_config  # type: ignore

    out_root = OUT / "service-outputs"
    if out_root.exists():
        shutil.rmtree(out_root)
    client = TestClient(create_app(build_api_config(out_root)))

    report = {"synthetic": True, "runs": []}
    for schema, names in (("v1", CHANNEL_NAMES_V1), ("v2", CHANNEL_NAMES_V2)):
        print(f"--- {schema} ({len(names)} channels) ---")
        result = _run_schema(client, schema, names)
        report["runs"].append(result)
        print(json.dumps(result, indent=2))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "profile.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"written: {OUT / 'profile.json'}")
    ok = all(
        r["can_train"] and r["total_cells"] >= 300_000 and r["distinct_5deg_blocks"] >= 8
        for r in report["runs"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
