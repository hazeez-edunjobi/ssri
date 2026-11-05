"""SYNTHETIC rehearsal: >250k-row CSV (former cap) + /shell Stage 2.5 flow.

The 250k cap lived on CSV import (platform/classic), not Stage 2.5 zip bytes.
This script (1) times CSV convert past 250k rows, (2) runs /shell upload→validate→train
on a small SYNTHETIC Stage 2.5 zip. Not geological truth.
"""

from __future__ import annotations

import io
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


def _synthetic_xyz(width: int, height: int) -> bytes:
    buf = io.StringIO()
    buf.write("X,Y,Z\n")
    for y in range(height):
        for x in range(width):
            buf.write(f"{x * 100},{y * 100},{(x + y) % 7}\n")
    return buf.getvalue().encode()


def _write_stage25(stage_root: Path) -> None:
    from rasterio.transform import from_origin

    from ssri_model.dataset.catalog import write_manifest, write_statistics
    from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES, LABEL_NODATA
    from ssri_model.ml.splits import DatasetSplit

    # Distinct 5° blocks so release-shell spatial split can run (SYNTHETIC only).
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
    train_ids: list[str] = []
    val_ids: list[str] = []
    for i, (lat, lon) in enumerate(coords):
        split_name = "validation" if i >= 7 else "train"
        sample_id = f"t{i}"
        sample = stage_root / split_name / sample_id
        sample.mkdir(parents=True)
        yy, xx = np.mgrid[0:16, 0:16]
        stack = np.zeros((CHANNEL_COUNT, 16, 16), dtype=np.float64)
        for ch in range(CHANNEL_COUNT):
            stack[ch] = (ch + 1) * 0.1 + 0.01 * xx + 0.02 * yy + 0.001 * ch * xx * yy
        labels = np.zeros((16, 16), dtype=np.int16)
        labels[2:10, 2:10] = 1
        labels[10:14, 10:14] = 0
        np.save(sample / "feature_stack.npy", stack)
        with rasterio.open(
            sample / "label.tif",
            "w",
            driver="GTiff",
            height=16,
            width=16,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=from_origin(lon - 0.05, lat + 0.05, 0.001, 0.001),
            nodata=float(LABEL_NODATA),
        ) as ds:
            ds.write(labels.astype(np.float32), 1)
        (sample / "metadata.json").write_text(
            json.dumps(
                {
                    "sample_id": sample_id,
                    "crs": "EPSG:4326",
                    "centroid_lat": lat,
                    "centroid_lon": lon,
                    "resolution_m": 100,
                    "source_format": "SYNTHETIC",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "label_classes": list(CHANNEL_NAMES[:3]),
                    "notes": "SYNTHETIC rehearsal; not geological truth",
                    "synthetic": True,
                }
            ),
            encoding="utf-8",
        )
        (val_ids if split_name == "validation" else train_ids).append(sample_id)
    split = DatasetSplit(train=tuple(train_ids), validation=tuple(val_ids), test=())
    write_statistics(stage_root, split=split)
    write_manifest(
        stage_root,
        dataset_name="SYNTHETIC shell rehearsal",
        version="synthetic-1",
        split=split,
        crs="EPSG:4326",
        resolution_m=100.0,
    )


def main() -> int:
    os.environ["SSRI_RELEASE_SHELL"] = "true"
    os.environ.pop("SSRI_UPLOAD_MAX_ROWS", None)
    # Rehearsal-only lowers: prove train starts without fabricating 300 real tiles.
    os.environ["SSRI_RELEASE_SHELL_MIN_TILES"] = "2"
    os.environ["SSRI_RELEASE_SHELL_MIN_BLOCKS"] = "2"
    os.environ["SSRI_RELEASE_SHELL_MIN_HELD_OUT"] = "1"

    from fastapi.testclient import TestClient

    from ssri_model.api.app import create_app
    from ssri_model.manual_training.csv_import import CsvFeatureOnly, convert_csv_dataset
    from tests.api_helpers import build_api_config

    root = Path("poc/release_shell/outputs/upload_cap_rehearsal")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    width, height = 641, 391  # 250,631 > 250,000
    rows = width * height
    print(f"SYNTHETIC grid {width}x{height} = {rows} rows")

    t0 = time.perf_counter()
    content = _synthetic_xyz(width, height)
    gen_s = time.perf_counter() - t0
    print(f"csv_generate_s={gen_s:.2f} bytes={len(content)} peak_rss_mb={_peak_rss_mb():.1f}")

    t1 = time.perf_counter()
    try:
        convert_csv_dataset(
            root / "csv_convert",
            filename="SYNTHETIC_elevation.csv",
            content=content,
            crs="EPSG:32631",
            dataset_name="SYNTHETIC upload-cap rehearsal",
        )
        csv_status = "READY"
        csv_rows = rows
    except CsvFeatureOnly as exc:
        csv_status = str(exc.analysis.get("status"))
        csv_rows = int(exc.analysis.get("rows") or 0)
        print(f"csv_feature_only rows={csv_rows}")
    csv_s = time.perf_counter() - t1
    print(f"csv_convert_s={csv_s:.2f} status={csv_status} peak_rss_mb={_peak_rss_mb():.1f}")

    stage_root = root / "stage25"
    _write_stage25(stage_root)
    zip_path = root / "SYNTHETIC_shell.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in stage_root.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(stage_root).as_posix())

    out = Path("outputs/upload_cap_shell")
    if out.exists():
        shutil.rmtree(out)
    client = TestClient(create_app(build_api_config(out)))

    created = client.post(
        "/api/v1/training/datasets",
        json={"name": "SYNTHETIC-upload-cap", "description": "SYNTHETIC rehearsal"},
    )
    print(f"create_status={created.status_code}")
    dataset_id = created.json()["dataset"]["dataset_id"]

    t_up = time.perf_counter()
    upload = client.post(
        f"/api/v1/release-shell/datasets/{dataset_id}/upload",
        files={"file": ("SYNTHETIC_shell.zip", zip_path.read_bytes(), "application/zip")},
    )
    upload_s = time.perf_counter() - t_up
    print(f"shell_upload_status={upload.status_code} s={upload_s:.2f}")

    t_val = time.perf_counter()
    validate = client.post(f"/api/v1/release-shell/datasets/{dataset_id}/validate")
    validate_s = time.perf_counter() - t_val
    print(f"shell_validate_status={validate.status_code} s={validate_s:.2f}")
    print(f"validate_body={validate.text[:600]}")

    t_tr = time.perf_counter()
    train = client.post(
        "/api/v1/release-shell/jobs",
        json={
            "dataset_id": dataset_id,
            "epochs": 1,
            "batch_size": 1,
            "seeds": [0],
            "model_name": "SYNTHETIC-upload-cap",
            "device": "cpu",
        },
    )
    train_start_s = time.perf_counter() - t_tr
    print(f"shell_train_status={train.status_code} start_s={train_start_s:.2f}")
    print(f"train_body={train.text[:500]}")
    peak = _peak_rss_mb()
    print(f"peak_rss_mb={peak:.1f}")

    report = {
        "synthetic": True,
        "csv_rows": csv_rows,
        "csv_generate_s": round(gen_s, 3),
        "csv_convert_s": round(csv_s, 3),
        "csv_status": csv_status,
        "shell_upload_s": round(upload_s, 3),
        "shell_validate_s": round(validate_s, 3),
        "shell_train_start_s": round(train_start_s, 3),
        "shell_upload_status": upload.status_code,
        "shell_validate_status": validate.status_code,
        "shell_train_status": train.status_code,
        "peak_rss_mb": round(peak, 1),
        "validation_slow": validate_s > 5.0,
        "training_start_slow": train_start_s > 5.0,
        "note": (
            "250k row cap was CSV-only; /shell uses Stage 2.5 zip (byte cap only). "
            "CSV >250k timed above; shell path uses small SYNTHETIC Stage 2.5."
        ),
    }
    (root / "rehearsal.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    ok = (
        csv_rows > 250_000
        and upload.status_code < 400
        and validate.status_code < 400
        and train.status_code in {200, 202}
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
