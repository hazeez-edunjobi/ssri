"""Upload unlimited-by-default + lineament/overburden apply (SYNTHETIC only)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.manual_training.ingest import ingest_zip_bytes
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.manual_training.upload_limits import (
    reject_if_upload_too_large,
    reject_if_zip_expansion_unsafe,
    upload_max_bytes,
)
from ssri_model.ml.constants import FEATURE_NODATA
from ssri_model.release_shell.channel_schema import CHANNEL_NAMES_V1, CHANNEL_NAMES_V2, SCHEMA_V2
from ssri_model.release_shell.feature_apply import (
    apply_lineaments_to_dataset,
    apply_overburden_to_dataset,
)
from ssri_model.release_shell.lineaments import load_lineament_segments
from ssri_model.release_shell.point_grid_csv import ingest_point_grid_csv
from ssri_model.release_shell.validator import validate_point_grid_layer


def test_no_app_byte_cap_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SSRI_UPLOAD_MAX_BYTES", raising=False)
    assert upload_max_bytes() is None
    # Former default was 1 GiB — sizes above that must no longer raise.
    reject_if_upload_too_large(1 * 1024 * 1024 * 1024 + 50_000_000)


def test_zip_bomb_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSRI_UPLOAD_MAX_COMPRESSION_RATIO", "10")
    with pytest.raises(ManualTrainingError) as caught:
        reject_if_zip_expansion_unsafe(
            compressed_size=1000,
            uncompressed_size=1000 * 50,
            file_count=1,
        )
    assert caught.value.code == "ZIP_BOMB"


def _write_v1_sample(root: Path, sid: str = "t0") -> Path:
    d = root / "train" / sid
    d.mkdir(parents=True)
    h, w = 8, 8
    feats = np.zeros((len(CHANNEL_NAMES_V1), h, w), dtype=np.float32)
    for i in range(len(CHANNEL_NAMES_V1)):
        feats[i] = i + 0.1
    np.save(d / "feature_stack.npy", feats)
    transform = from_origin(100.0, 200.0, 10.0, 10.0)  # projected metres
    label = np.full((h, w), -1, dtype=np.int16)
    label[2:6, 2:6] = 1
    with rasterio.open(
        d / "label.tif",
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="int16",
        crs="EPSG:32631",
        transform=transform,
        nodata=-1,
    ) as ds:
        ds.write(label, 1)
    (d / "metadata.json").write_text(
        json.dumps(
            {
                "sample_id": sid,
                "synthetic": True,
                "crs": "EPSG:32631",
                "channel_schema_version": "v1",
            }
        ),
        encoding="utf-8",
    )
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "channel_schema_version": "v1",
                "channel_names": list(CHANNEL_NAMES_V1),
            }
        ),
        encoding="utf-8",
    )
    (root / "statistics.json").write_text("{}", encoding="utf-8")
    # validation twin required by classic validator elsewhere — optional here
    return d


def test_apply_lineaments_promotes_v1_stack_to_v2(tmp_path: Path) -> None:
    root = tmp_path / "ds"
    _write_v1_sample(root)
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[100.0, 120.0], [180.0, 120.0]],
                },
            }
        ],
    }
    segs = load_lineament_segments(geojson)
    result = apply_lineaments_to_dataset(root, segs, window_m=40.0, lineament_crs="EPSG:32631")
    assert result["overall"] == "PASS"
    assert result["samples_updated"] == 1
    stack = np.load(root / "train" / "t0" / "feature_stack.npy")
    assert stack.shape[0] == len(CHANNEL_NAMES_V2)
    dens = stack[CHANNEL_NAMES_V2.index("lineament_density")]
    dist = stack[CHANNEL_NAMES_V2.index("lineament_distance")]
    assert np.isfinite(dens).any()
    assert (dist != FEATURE_NODATA).any()
    man = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert man["channel_schema_version"] == SCHEMA_V2
    assert man["channel_names"] == list(CHANNEL_NAMES_V2)


def test_apply_overburden_thickness_and_reject_depth_as_thickness(tmp_path: Path) -> None:
    root = tmp_path / "ds"
    _write_v1_sample(root)
    # Grid covering the label extent (origin 100,200; 8x8 cells @ 10 m)
    lines = ["X,Y,Z"]
    for y in range(120, 201, 10):
        for x in range(100, 181, 10):
            lines.append(f"{x},{y},12.5")
    layer = ingest_point_grid_csv(
        ("\n".join(lines) + "\n").encode(),
        filename="SYNTHETIC_overburden.csv",
        layer_name="overburden_thickness",
        crs="EPSG:32631",
    )
    result = apply_overburden_to_dataset(
        root, layer, measurement_type="thickness", units="m"
    )
    assert result["overall"] == "PASS"
    stack = np.load(root / "train" / "t0" / "feature_stack.npy")
    ob = stack[CHANNEL_NAMES_V2.index("overburden_thickness")]
    assert float(np.nanmax(ob[ob != FEATURE_NODATA])) == pytest.approx(12.5)

    with pytest.raises(ValueError, match="depth"):
        apply_overburden_to_dataset(
            root, layer, measurement_type="depth_to_interface", units="m"
        )


def test_validate_layer_depth_vs_thickness_contract() -> None:
    lines = ["X,Y,Z", "0,0,1", "100,0,2", "0,100,3", "100,100,4"]
    content = ("\n".join(lines) + "\n").encode()
    bad = validate_point_grid_layer(
        content,
        filename="SYNTHETIC.csv",
        layer_name="overburden_thickness",
        crs="EPSG:32631",
        measurement_type="depth_to_interface",
        units="m",
    )
    assert bad["overall"] == "FAIL"
    assert any(c["name"] == "measurement_type" and c["status"] == "FAIL" for c in bad["checks"])

    good = validate_point_grid_layer(
        content,
        filename="SYNTHETIC.csv",
        layer_name="overburden_thickness",
        crs="EPSG:32631",
        measurement_type="thickness",
        units="m",
    )
    assert good["overall"] in {"PASS", "WARN"}
    assert good["measurement_type"] == "thickness"
    assert good["units"] == "m"


def test_ingest_accepts_payload_above_former_1gib_when_unlimited(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove the former 1 GiB app default no longer blocks (check + small zip path)."""
    monkeypatch.delenv("SSRI_UPLOAD_MAX_BYTES", raising=False)
    reject_if_upload_too_large(2 * 1024 * 1024 * 1024)

    root = tmp_path / "stage25"
    _write_v1_sample(root)
    # Classic trainer requires a non-empty validation split.
    import shutil

    shutil.copytree(root / "train" / "t0", root / "validation" / "v0")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path in root.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(root)).replace("\\", "/"))
    payload = buf.getvalue()
    storage = TrainingStorage(tmp_path / "out")
    rec = storage.create_dataset(name="SYNTHETIC large-cap")
    # Proof of unlimited: reject_if_upload_too_large(2 GiB) above plus successful
    # ingest here with no SSRI_UPLOAD_MAX_BYTES set.
    record, _preview = ingest_zip_bytes(
        storage, rec.dataset_id, filename="SYNTHETIC.zip", content=payload
    )
    assert record.root_path
    assert Path(record.root_path, "train", "t0", "feature_stack.npy").exists()
