"""SYNTHETIC rehearsal: Abeokuta-format overburden CSV + labels → validate path.

Also runs REAL sheet 260_Abeokuta.csv through the point-grid validator with an
ASSUMED-FOR-TEST CRS (FEATURE_LAYER_ONLY expected). Not geological evidence.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "poc" / "release_shell" / "outputs" / "hazard_factors_v2_rehearsal"


def _peak_rss_mb() -> float:
    try:
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        return -1.0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / "model"))
    os.environ["SSRI_RELEASE_SHELL"] = "true"

    from ssri_model.release_shell.point_grid_csv import ingest_point_grid_csv

    # --- SYNTHETIC Abeokuta-format layer + labels ---
    lines = ["X,Y,Z"]
    for y in range(20):
        for x in range(20):
            lines.append(f"{-115500 + x * 100},{777400 + y * 100},{50 + 0.1 * x + 0.05 * y}")
    synth_csv = ("\n".join(lines) + "\n").encode()
    (OUT / "SYNTHETIC_overburden.csv").write_bytes(synth_csv)

    label_lines = ["X,Y,hazard,date"]
    for y in range(0, 20, 4):
        for x in range(0, 20, 4):
            label_lines.append(
                f"{-115500 + x * 100},{777400 + y * 100},landslide,2020-01-01"
            )
    (OUT / "SYNTHETIC_labels.csv").write_text("\n".join(label_lines) + "\n", encoding="utf-8")

    t0 = time.perf_counter()
    layer = ingest_point_grid_csv(
        synth_csv,
        filename="SYNTHETIC_overburden.csv",
        layer_name="overburden_thickness",
        crs="EPSG:32631",  # SYNTHETIC placeholder CRS for rehearsal only
    )
    synth_s = time.perf_counter() - t0
    synth = {
        "synthetic": True,
        "layer": layer.to_dict(),
        "seconds": round(synth_s, 3),
        "peak_rss_mb": round(_peak_rss_mb(), 1),
        "note": "Single layer → FEATURE_LAYER_ONLY; cannot train without full schema + labels joined.",
    }

    # Label parse
    from ssri_model.release_shell.labels_inventory import parse_label_csv

    inv = parse_label_csv(
        (OUT / "SYNTHETIC_labels.csv").read_bytes(),
        crs="EPSG:32631",
        filename="SYNTHETIC_labels.csv",
    )
    synth["labels"] = inv.to_dict()

    # --- REAL client CSV with ASSUMED-FOR-TEST CRS ---
    real_path = ROOT / "sheet 260_Abeokuta.csv"
    real = {"skipped": True}
    if real_path.exists():
        t1 = time.perf_counter()
        try:
            real_layer = ingest_point_grid_csv(
                real_path.read_bytes(),
                filename="sheet 260_Abeokuta.csv",
                layer_name="overburden_thickness",
                crs="EPSG:32631",  # ASSUMED-FOR-TEST — not client-confirmed
            )
            real = {
                "assumed_crs": "EPSG:32631 (ASSUMED-FOR-TEST)",
                "status": real_layer.status,
                "trainable": real_layer.trainable,
                "row_count": real_layer.row_count,
                "missing_cells": real_layer.missing_cells,
                "seconds": round(time.perf_counter() - t1, 3),
                "peak_rss_mb": round(_peak_rss_mb(), 1),
                "messages": real_layer.messages,
                "evidence": "NOT real evidence — CRS assumed for test only",
            }
        except Exception as exc:  # noqa: BLE001
            real = {
                "assumed_crs": "EPSG:32631 (ASSUMED-FOR-TEST)",
                "error": str(exc),
                "seconds": round(time.perf_counter() - t1, 3),
                "peak_rss_mb": round(_peak_rss_mb(), 1),
            }

    report = {
        "synthetic_rehearsal": synth,
        "real_abeokuta_assumed_crs": real,
        "train_note": (
            "Full 3-seed train/evaluate/assess on a complete v2 Stage 2.5 ZIP is "
            "covered by existing shell rehearsals; this script proves the new "
            "point-grid path + FEATURE_LAYER_ONLY behaviour for Abeokuta-format CSV."
        ),
    }
    (OUT / "rehearsal.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    ok = (
        synth["layer"]["status"] == "FEATURE_LAYER_ONLY"
        and real.get("status") == "FEATURE_LAYER_ONLY"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
