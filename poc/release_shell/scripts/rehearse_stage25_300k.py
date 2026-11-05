"""SYNTHETIC Stage 2.5 rehearsal: >=300k cells, 13 channels, >=8 distinct 5° blocks.

Not geological truth. Reports validation time, peak RSS, and short train start/complete.
"""

from __future__ import annotations

import json
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

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
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

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(counters), counters.cb
            )
            return counters.PeakWorkingSetSize / (1024 * 1024)
        except Exception:
            return -1.0
    return -1.0


def main() -> int:
    os.environ["SSRI_RELEASE_SHELL"] = "true"
    # Short SYNTHETIC train: keep spatial diversity, relax tile-count gate only.
    os.environ["SSRI_RELEASE_SHELL_MIN_TILES"] = "8"
    os.environ["SSRI_RELEASE_SHELL_MIN_BLOCKS"] = "8"
    os.environ["SSRI_RELEASE_SHELL_MIN_HELD_OUT"] = "2"

    from fastapi.testclient import TestClient

    from ssri_model.api.app import create_app
    from ssri_model.dataset.catalog import write_manifest, write_statistics
    from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES, LABEL_NODATA
    from ssri_model.ml.splits import DatasetSplit
    from tests.api_helpers import build_api_config

    root = Path("poc/release_shell/outputs/rehearsal_300k")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    stage = root / "stage25"

    # 9 blocks × 3 tiles × 128×128 = 442,368 cells (>= 300,000), 13 channels.
    coords = [
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
    tile_h = tile_w = 128
    tiles_per_block = 3
    train_ids: list[str] = []
    val_ids: list[str] = []
    total_cells = 0

    t_gen = time.perf_counter()
    try:
        for bi, (lat, lon) in enumerate(coords):
            for ti in range(tiles_per_block):
                sample_id = f"b{bi}_t{ti}"
                split_name = "validation" if bi >= 7 else "train"
                sample = stage / split_name / sample_id
                sample.mkdir(parents=True)
                yy, xx = np.mgrid[0:tile_h, 0:tile_w]
                stack = np.zeros((CHANNEL_COUNT, tile_h, tile_w), dtype=np.float32)
                for ch in range(CHANNEL_COUNT):
                    stack[ch] = (
                        (ch + 1) * 0.1
                        + 0.01 * xx
                        + 0.02 * yy
                        + 0.0001 * ch * xx
                        + 0.05 * ti
                        + 0.1 * bi
                    )
                labels = np.zeros((tile_h, tile_w), dtype=np.int16)
                labels[20:80, 20:80] = 1
                labels[90:120, 90:120] = 0
                np.save(sample / "feature_stack.npy", stack)
                with rasterio.open(
                    sample / "label.tif",
                    "w",
                    driver="GTiff",
                    height=tile_h,
                    width=tile_w,
                    count=1,
                    dtype="float32",
                    crs="EPSG:4326",
                    transform=from_origin(
                        lon - 0.05 + ti * 0.01, lat + 0.05, 0.0005, 0.0005
                    ),
                    nodata=float(LABEL_NODATA),
                ) as ds:
                    ds.write(labels.astype(np.float32), 1)
                (sample / "metadata.json").write_text(
                    json.dumps(
                        {
                            "sample_id": sample_id,
                            "crs": "EPSG:4326",
                            "centroid_lat": lat + ti * 0.01,
                            "centroid_lon": lon + ti * 0.01,
                            "resolution_m": 30,
                            "source_format": "SYNTHETIC",
                            "synthetic": True,
                            "notes": "SYNTHETIC 300k-cell rehearsal; not geological truth",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "label_classes": list(CHANNEL_NAMES[:3]),
                        }
                    ),
                    encoding="utf-8",
                )
                total_cells += tile_h * tile_w
                (val_ids if split_name == "validation" else train_ids).append(sample_id)
    except MemoryError as exc:
        report = {"synthetic": True, "memory_failure": True, "error": str(exc)}
        (root / "rehearsal.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    gen_s = time.perf_counter() - t_gen
    split = DatasetSplit(train=tuple(train_ids), validation=tuple(val_ids), test=())
    write_statistics(stage, split=split)
    write_manifest(
        stage,
        dataset_name="SYNTHETIC-300k-rehearsal",
        version="synthetic-300k-1",
        split=split,
        crs="EPSG:4326",
        resolution_m=30.0,
    )
    print(
        f"generated tiles={len(train_ids)+len(val_ids)} cells={total_cells} "
        f"blocks={len(coords)} gen_s={gen_s:.2f} peak_rss_mb={_peak_rss_mb():.1f}"
    )

    zip_path = root / "SYNTHETIC_300k_stage25.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in stage.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(stage).as_posix())
    print(f"zip_bytes={zip_path.stat().st_size} peak_rss_mb={_peak_rss_mb():.1f}")

    out = Path("outputs/rehearsal_300k_shell")
    if out.exists():
        shutil.rmtree(out)
    client = TestClient(create_app(build_api_config(out)))
    created = client.post(
        "/api/v1/training/datasets",
        json={"name": "SYNTHETIC-300k", "description": "SYNTHETIC 300k-cell rehearsal"},
    )
    dataset_id = created.json()["dataset"]["dataset_id"]

    t_up = time.perf_counter()
    upload = client.post(
        f"/api/v1/release-shell/datasets/{dataset_id}/upload",
        files={"file": ("SYNTHETIC_300k_stage25.zip", zip_path.read_bytes(), "application/zip")},
    )
    upload_s = time.perf_counter() - t_up

    t_val = time.perf_counter()
    validate = client.post(f"/api/v1/release-shell/datasets/{dataset_id}/validate")
    validate_s = time.perf_counter() - t_val
    print(f"upload={upload.status_code} s={upload_s:.2f}")
    print(f"validate={validate.status_code} s={validate_s:.2f}")
    print(validate.text[:800])

    t_tr = time.perf_counter()
    train = client.post(
        "/api/v1/release-shell/jobs",
        json={
            "dataset_id": dataset_id,
            "epochs": 1,
            "batch_size": 1,
            "seeds": [0],
            "model_name": "SYNTHETIC-300k",
            "device": "cpu",
        },
    )
    train_start_s = time.perf_counter() - t_tr
    print(f"train_start={train.status_code} s={train_start_s:.2f}")
    print(train.text[:600])

    train_complete = False
    train_complete_s = None
    train_error = None
    if train.status_code in {200, 202}:
        job_id = train.json().get("job_id")
        t_wait = time.perf_counter()
        for _ in range(120):
            status = client.get(f"/api/v1/jobs/{job_id}")
            body = status.json()
            st = body.get("status") or body.get("job", {}).get("status")
            if st in {"COMPLETED", "SUCCEEDED", "completed", "succeeded"}:
                train_complete = True
                train_complete_s = time.perf_counter() - t_wait
                break
            if st in {"FAILED", "failed", "CANCELLED", "cancelled"}:
                train_error = body
                train_complete_s = time.perf_counter() - t_wait
                break
            time.sleep(2)
        else:
            train_error = {"timeout": True, "last": status.text[:400]}

    peak = _peak_rss_mb()
    report = {
        "synthetic": True,
        "total_cells": total_cells,
        "channels": CHANNEL_COUNT,
        "distinct_5deg_blocks": len(coords),
        "tiles": len(train_ids) + len(val_ids),
        "generate_s": round(gen_s, 3),
        "upload_s": round(upload_s, 3),
        "validate_s": round(validate_s, 3),
        "train_start_s": round(train_start_s, 3),
        "train_started": train.status_code in {200, 202},
        "train_completed_short_run": train_complete,
        "train_complete_s": None if train_complete_s is None else round(train_complete_s, 3),
        "train_error": train_error,
        "peak_rss_mb": round(peak, 1),
        "memory_failure": False,
        "upload_status": upload.status_code,
        "validate_status": validate.status_code,
        "train_status": train.status_code,
        "mins_note": "MIN_TILES=8 MIN_BLOCKS=8 MIN_HELD_OUT=2 for short SYNTHETIC train",
    }
    (root / "rehearsal.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["train_started"] and total_cells >= 300_000 else 1


if __name__ == "__main__":
    raise SystemExit(main())
