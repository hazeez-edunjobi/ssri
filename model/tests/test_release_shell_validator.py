"""Upload validator PASS/WARN/FAIL behaviour."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from ssri_model.ml.constants import CHANNEL_NAMES, FEATURE_NODATA
from ssri_model.release_shell.validator import validate_release_shell_dataset


def _write_tile(root: Path, sid: str, *, all_nodata_spectral: bool = False) -> None:
    d = root / "train" / sid
    d.mkdir(parents=True)
    h, w = 8, 8
    feats = np.zeros((13, h, w), dtype=np.float32)
    feats[0] = 100
    feats[1] = 10
    for i in range(2, 13):
        if all_nodata_spectral and i >= 7:
            feats[i] = FEATURE_NODATA
        else:
            feats[i] = float(i)
    np.save(d / "feature_stack.npy", feats)
    label = np.zeros((h, w), dtype=np.int16)
    label[2:6, 2:6] = 1
    with rasterio.open(
        d / "label.tif",
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="int16",
        crs="EPSG:4326",
        transform=from_origin(-120, 40, 0.001, 0.001),
        nodata=-1,
    ) as ds:
        ds.write(label, 1)
    (d / "metadata.json").write_text(
        json.dumps(
            {
                "centroid_lat": 37.5,
                "centroid_lon": -122.5,
                "synthetic": True,
            }
        ),
        encoding="utf-8",
    )


def test_validator_fails_all_sentinel_channels(tmp_path, monkeypatch):
    monkeypatch.setenv("SSRI_RELEASE_SHELL_MIN_TILES", "1")
    monkeypatch.setenv("SSRI_RELEASE_SHELL_MIN_BLOCKS", "1")
    root = tmp_path / "ds"
    # Need several blocks for split — write 9 tiles; one with bad channels is enough to FAIL channel_quality
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
    for i, (lat, lon) in enumerate(coords):
        sid = f"t{i}"
        _write_tile(root, sid, all_nodata_spectral=True)
        meta = json.loads((root / "train" / sid / "metadata.json").read_text(encoding="utf-8"))
        meta["centroid_lat"] = lat
        meta["centroid_lon"] = lon
        (root / "train" / sid / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "splits": {
                    "train": [f"t{i}" for i in range(9)],
                    "validation": [],
                    "test": [],
                },
                "channels": list(CHANNEL_NAMES),
            }
        ),
        encoding="utf-8",
    )
    (root / "statistics.json").write_text("{}", encoding="utf-8")
    report = validate_release_shell_dataset(root)
    channel = next(c for c in report["checks"] if c["name"] == "channel_quality")
    assert channel["status"] == "FAIL"
    assert report["can_train"] is False
