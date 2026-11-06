"""Build SYNTHETIC Stage 2.5 schema-v2 ZIP (16 channels). Not real geology."""

from __future__ import annotations

import json
import math
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from ssri_model.ml.normalization import NormalizationConfig
from ssri_model.release_shell.channel_schema import CHANNEL_NAMES_V2, SCHEMA_V2

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "templates"
WORK = OUT_DIR / "_SYNTHETIC_v2_build"
ZIP_PATH = OUT_DIR / "SYNTHETIC_stage25_v2_template.zip"

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
    (45.5, -75.5),
    (30.5, -85.5),
    (38.5, -80.5),
]


def block5(lat: float, lon: float) -> str:
    return f"{int(math.floor(lat / 5.0) * 5)}_{int(math.floor(lon / 5.0) * 5)}"


def write_sample(split: str, sid: str, lat: float, lon: float, hazard_class: int) -> None:
    d = WORK / split / sid
    d.mkdir(parents=True, exist_ok=True)
    h, w = 16, 16
    rng = np.random.default_rng(abs(hash(sid)) % (2**32))
    feats = np.zeros((len(CHANNEL_NAMES_V2), h, w), dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    feats[0] = 500 + 200 * rng.random((h, w))
    feats[1] = 5 + 25 * rng.random((h, w))
    for i in range(2, 13):
        feats[i] = rng.normal(0.0, 1.0, size=(h, w)).astype(np.float32)
    # v2 extras
    feats[13] = np.clip(20 + 5 * rng.random((h, w)) + 0.1 * xx, 0.5, None)  # overburden_thickness ≥ 0
    feats[14] = 0.001 * (xx + yy) + 0.0001 * rng.random((h, w))  # lineament_density
    feats[15] = 50 + 10 * rng.random((h, w)) + 0.5 * xx  # lineament_distance
    np.save(d / "feature_stack.npy", feats)

    label = np.full((h, w), -1, dtype=np.int16)
    label[4:12, 4:12] = hazard_class
    transform = from_origin(lon - 0.01, lat + 0.01, 0.00125, 0.00125)
    with rasterio.open(
        d / "label.tif",
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="int16",
        crs="EPSG:4326",
        transform=transform,
        nodata=-1,
    ) as ds:
        ds.write(label, 1)

    meta = {
        "synthetic": True,
        "synthetic_label": "SYNTHETIC",
        "sample_id": sid,
        "centroid_lat": lat,
        "centroid_lon": lon,
        "block": block5(lat, lon),
        "crs": "EPSG:4326",
        "imagery_date": "SYNTHETIC",
        "label_date": "SYNTHETIC",
        "channel_schema_version": SCHEMA_V2,
        "note": "SYNTHETIC v2 demo tile — not real geography or labels",
    }
    (d / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ids = []
    for i, (lat, lon) in enumerate(BLOCK_CENTERS):
        sid = f"SYNTHETIC_v2_tile_{i:02d}"
        write_sample("train", sid, lat, lon, i % 3)
        ids.append(sid)
    write_sample("validation", "SYNTHETIC_v2_val_placeholder", 33.5, -112.5, 1)

    manifest = {
        "dataset_name": "SYNTHETIC_stage25_v2_template",
        "version": "0.1.0-SYNTHETIC-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "channel_schema_version": SCHEMA_V2,
        "channels": list(CHANNEL_NAMES_V2),
        "channel_names": list(CHANNEL_NAMES_V2),
        "label_classes": ["subsidence", "landslide", "sinkhole"],
        "resolution": 30.0,
        "crs": "EPSG:4326",
        "normalization": NormalizationConfig.default_v2().as_dict(),
        "train_count": len(ids),
        "validation_count": 1,
        "test_count": 0,
        "synthetic": True,
        "splits": {
            "train": ids,
            "validation": ["SYNTHETIC_v2_val_placeholder"],
            "test": [],
        },
        "notes": [
            "SYNTHETIC schema-v2 template (16 channels) for release-shell demos only.",
            "Must never be used for insurance, engineering, safety, or emergency decisions.",
        ],
    }
    (WORK / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    stats = {
        "sample_count": len(ids) + 1,
        "train_count": len(ids),
        "validation_count": 1,
        "test_count": 0,
        "channel_names": list(CHANNEL_NAMES_V2),
        "channel_schema_version": SCHEMA_V2,
        "synthetic": True,
        "channel_stats": {
            name: {
                "min": 0.0,
                "max": 1.0,
                "mean": 0.5,
                "std": 0.1,
                "valid_count": 1,
                "nodata_count": 0,
            }
            for name in CHANNEL_NAMES_V2
        },
    }
    (WORK / "statistics.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    (WORK / "README_SYNTHETIC.txt").write_text(
        "SYNTHETIC Stage 2.5 schema-v2 template (16 channels). Not real data.\n",
        encoding="utf-8",
    )

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in WORK.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(WORK).as_posix())
    print(f"Wrote {ZIP_PATH}")


if __name__ == "__main__":
    main()
