"""Package FeatureStacks v3 (240 tiles) as a Stage 2.5 upload ZIP for rehearsal."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ssri_model.ml.constants import CHANNEL_NAMES
from ssri_model.ml.normalization import NormalizationConfig

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "data" / "datasets" / "usgs_landslide_featurestacks" / "v3"
OUT = Path(__file__).resolve().parents[1] / "outputs" / "rehearsal"
WORK = OUT / "featurestacks_v3_stage25"
ZIP_PATH = OUT / "usgs_featurestacks_v3_upload.zip"


def main() -> int:
    if not SRC.exists():
        print(f"MISSING {SRC}")
        return 1
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    samples = sorted(p for p in (SRC / "samples").iterdir() if p.is_dir())
    print(f"packaging {len(samples)} samples")
    ids = []
    for sdir in samples:
        sid = sdir.name
        dest = WORK / "train" / sid
        dest.mkdir(parents=True)
        for name in ("feature_stack.npy", "label.tif", "metadata.json"):
            src = sdir / name
            if src.exists():
                shutil.copy2(src, dest / name)
        # enrich metadata with centroid if missing
        meta_path = dest / "metadata.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        if "centroid_lat" not in meta and "lat" in meta:
            meta["centroid_lat"] = meta["lat"]
            meta["centroid_lon"] = meta.get("lon")
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        ids.append(sid)

    # placeholder validation (unique id) — shell validate will re-split
    if ids:
        shutil.copytree(WORK / "train" / ids[0], WORK / "validation" / f"{ids[0]}__valcopy")
        # rewrite sample id in copied metadata path only; folder name is unique

    manifest = {
        "dataset_name": "usgs_featurestacks_v3_upload",
        "version": "v3-rehearsal",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "channels": list(CHANNEL_NAMES),
        "label_classes": ["subsidence", "landslide", "sinkhole"],
        "resolution": 30.0,
        "crs": "EPSG:4326",
        "normalization": NormalizationConfig.default().as_dict(),
        "train_count": len(ids),
        "validation_count": 1,
        "test_count": 0,
        "splits": {
            "train": ids,
            "validation": [f"{ids[0]}__valcopy"] if ids else [],
            "test": [],
        },
        "source": str(SRC),
        "n_tiles": len(ids),
    }
    (WORK / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (WORK / "statistics.json").write_text(
        json.dumps({"sample_count": len(ids), "synthetic": False}, indent=2),
        encoding="utf-8",
    )

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in WORK.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(WORK).as_posix())
    print(f"Wrote {ZIP_PATH} ({ZIP_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
