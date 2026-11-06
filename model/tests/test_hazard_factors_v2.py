"""Additive tests for hazard-factors v2 (schemas, CSV, blocks, preview)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.ml.constants import CHANNEL_NAMES, FEATURE_NODATA
from ssri_model.release_shell.assess_contract import (
    STATUS_UNEVALUATED_PREVIEW,
    resolve_hazard_entry,
)
from ssri_model.release_shell.channel_schema import (
    CHANNEL_NAMES_V1,
    CHANNEL_NAMES_V2,
    assert_channels_match,
    schema_for_version,
)
from ssri_model.release_shell.gates import STATUS_EVALUATED, STATUS_NO_SKILL, STATUS_NOT_AVAILABLE
from ssri_model.release_shell.lineaments import derive_lineament_rasters, load_lineament_segments
from ssri_model.release_shell.point_grid_csv import ingest_point_grid_csv
from ssri_model.release_shell.spatial_split import (
    LOCAL_EVIDENCE_LIMITATION,
    TileGeo,
    assert_block_disjoint,
    block_id,
    block_size_deg_from_km,
    split_by_blocks,
)


def test_v1_schema_unchanged() -> None:
    s = schema_for_version("v1")
    assert s.channel_names == CHANNEL_NAMES_V1 == tuple(CHANNEL_NAMES)
    assert s.channel_count == 13


def test_v2_schema_adds_three_channels() -> None:
    s = schema_for_version("v2")
    assert s.channel_names[:13] == CHANNEL_NAMES_V1
    assert "overburden_thickness" in s.channel_names
    assert "lineament_density" in s.channel_names
    assert "lineament_distance" in s.channel_names
    assert s.channel_count == 16
    assert s.channel_names == CHANNEL_NAMES_V2


def test_schema_mismatch_names_missing_channels() -> None:
    with pytest.raises(ValueError, match="Missing channels: overburden_thickness"):
        assert_channels_match(
            CHANNEL_NAMES_V2,
            CHANNEL_NAMES_V1,
            context="checkpoint",
        )


def test_headerless_csv_and_missing_crs(tmp_path) -> None:
    rows = ["-115500 777400 57.1", "-115400 777400 57.2", "-115500 777500 56.9", "-115400 777500 56.8"]
    content = ("\n".join(rows) + "\n").encode()
    with pytest.raises(ManualTrainingError, match="CRS is required") as exc:
        ingest_point_grid_csv(
            content,
            filename="SYNTHETIC_headerless.csv",
            layer_name="overburden_thickness",
            crs="",
            delimiter=" ",
            has_header=False,
        )
    assert exc.value.code == "CRS_REQUIRED"

    layer = ingest_point_grid_csv(
        content,
        filename="SYNTHETIC_headerless.csv",
        layer_name="overburden_thickness",
        crs="EPSG:32631",
        delimiter=" ",
        has_header=False,
    )
    assert layer.status == "FEATURE_LAYER_ONLY"
    assert layer.trainable is False
    assert layer.row_count == 4
    assert "cannot be used alone" in layer.messages[0].lower()


def test_headed_csv_reproject_and_gaps() -> None:
    # 3x3 grid missing one cell in EPSG:4326 → reproject to itself
    lines = ["X,Y,Z"]
    for y in range(3):
        for x in range(3):
            if (x, y) == (1, 1):
                continue
            lines.append(f"{3.0 + x * 0.01},{7.0 + y * 0.01},{10 + x + y}")
    content = ("\n".join(lines) + "\n").encode()
    layer = ingest_point_grid_csv(
        content,
        filename="SYNTHETIC_gap.csv",
        layer_name="overburden_thickness",
        crs="EPSG:4326",
        working_crs="EPSG:4326",
    )
    assert layer.missing_cells == 1
    assert any("missing cell" in m.lower() for m in layer.messages)


def test_depth_to_bedrock_not_silently_relabelled() -> None:
    lines = ["X,Y,Z", "0,0,10", "100,0,11", "0,100,12", "100,100,13"]
    layer = ingest_point_grid_csv(
        ("\n".join(lines) + "\n").encode(),
        filename="depth.csv",
        layer_name="depth_to_bedrock",
        crs="EPSG:32631",
    )
    assert layer.name == "depth_to_bedrock"
    assert layer.name != "overburden_thickness"


def test_overburden_thickness_flags_negative_z() -> None:
    lines = ["X,Y,Z", "0,0,10", "100,0,-3", "0,100,12", "100,100,-1.5"]
    layer = ingest_point_grid_csv(
        ("\n".join(lines) + "\n").encode(),
        filename="SYNTHETIC_neg_overburden.csv",
        layer_name="overburden_thickness",
        crs="EPSG:32631",
    )
    assert layer.name == "overburden_thickness"
    assert any("UNIT_SANITY" in m and "negative" in m.lower() for m in layer.messages)
    # Same negatives under depth_to_bedrock must not use the thickness unit warning.
    depth = ingest_point_grid_csv(
        ("\n".join(lines) + "\n").encode(),
        filename="SYNTHETIC_neg_depth.csv",
        layer_name="depth_to_bedrock",
        crs="EPSG:32631",
    )
    assert not any("UNIT_SANITY" in m for m in depth.messages)


def test_lineament_density_and_distance_known_vector() -> None:
    # Horizontal line y=0 from x=-1 to x=1; cell at origin → distance 0
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "LineString", "coordinates": [[-1.0, 0.0], [1.0, 0.0]]},
            }
        ],
    }
    segs = load_lineament_segments(geojson)
    xs = [-0.5, 0.0, 0.5]
    ys = [-0.5, 0.0, 0.5]
    density, distance, method = derive_lineament_rasters(xs, ys, segs, window_m=2.0)
    assert method.window_m == 2.0
    # centre cell (north-up: y=0.5 is row0, y=0 row1, y=-0.5 row2)
    assert distance[1, 1] == pytest.approx(0.0, abs=1e-6)
    assert density[1, 1] > 0
    assert density[1, 1] != FEATURE_NODATA


def test_local_block_sizes_and_disjointness() -> None:
    tiles = [
        TileGeo(f"t{i}", lat=7.0 + i * 0.05, lon=3.0 + (i % 3) * 0.05, crs="EPSG:4326")
        for i in range(12)
    ]
    # ~5.5 km blocks → many distinct blocks on this cluster
    split = split_by_blocks(
        tiles,
        block_size_km=5.0,
        buffer_km=0.0,
        min_held_out_blocks=2,
        seed=0,
    )
    assert split.local_evidence_only is True
    assert LOCAL_EVIDENCE_LIMITATION in (split.to_dict().get("limitations") or [])
    assert_block_disjoint(split.train_blocks, split.validation_blocks, split.test_blocks)

    # Classic 5° still works and is not local
    tiles5 = [
        TileGeo("a", 32.5, -117.5, "EPSG:4326"),
        TileGeo("b", 37.5, -122.5, "EPSG:4326"),
        TileGeo("c", 42.5, -122.5, "EPSG:4326"),
        TileGeo("d", 47.5, -122.5, "EPSG:4326"),
        TileGeo("e", 32.5, -110.5, "EPSG:4326"),
        TileGeo("f", 37.5, -110.5, "EPSG:4326"),
        TileGeo("g", 42.5, -105.5, "EPSG:4326"),
        TileGeo("h", 35.5, -95.5, "EPSG:4326"),
        TileGeo("i", 40.5, -85.5, "EPSG:4326"),
    ]
    split5 = split_by_blocks(tiles5, min_held_out_blocks=2, buffer_km=0.0, seed=1)
    assert split5.local_evidence_only is False
    assert_block_disjoint(split5.train_blocks, split5.validation_blocks, split5.test_blocks)
    assert block_id(32.5, -117.5, size_deg=5.0) == "30_-120"


def test_km_block_ids_do_not_collapse_to_integer_degrees() -> None:
    """Regression: int() truncation collapsed km blocks into ~1 degree buckets."""
    # A ~56 km north-south span at 5 km blocks must yield many distinct blocks,
    # not a handful of integer-degree buckets.
    size_deg = block_size_deg_from_km(5.0)
    lats = [7.0 + i * 0.05 for i in range(12)]  # ~0.55 deg ~ 61 km
    ids = {block_id(lat, 3.3, size_deg=size_deg) for lat in lats}
    assert len(ids) >= 11, sorted(ids)

    # Integral (5 deg) ids stay byte-identical to the historic format.
    assert block_id(32.5, -117.5, size_deg=5.0) == "30_-120"
    # 0.0-style coordinates still render without a decimal point.
    assert block_id(0.0, 0.0, size_deg=5.0) == "0_0"


def test_preview_unevaluated_scores_on_and_off() -> None:
    meta = {
        "hazards": {
            "landslide": {
                "has_positive_labels": True,
                "gate_status": STATUS_NO_SKILL,
                "disabled_at_validation": False,
            }
        },
        "local_evidence_only": True,
    }
    off = resolve_hazard_entry(
        "landslide",
        shell_meta=meta,
        query_lat=None,
        query_lon=None,
        raw_score=0.42,
        preview_unevaluated=False,
    )
    assert off["status"] == STATUS_NOT_AVAILABLE
    assert off["score"] is None
    assert off["preview_unevaluated_scores"] is False

    on = resolve_hazard_entry(
        "landslide",
        shell_meta=meta,
        query_lat=None,
        query_lon=None,
        raw_score=0.42,
        preview_unevaluated=True,
    )
    assert on["status"] == STATUS_UNEVALUATED_PREVIEW
    assert on["score"] == pytest.approx(0.42)
    assert on["scientific_validation_status"] == "NOT_VALIDATED"
    assert any("local evidence only" in x for x in on["limitations"])

    # Disabled hazards stay null even with preview on
    meta["hazards"]["landslide"]["disabled_at_validation"] = True
    disabled = resolve_hazard_entry(
        "landslide",
        shell_meta=meta,
        query_lat=None,
        query_lon=None,
        raw_score=0.42,
        preview_unevaluated=True,
    )
    assert disabled["score"] is None
    assert disabled["status"] == STATUS_NOT_AVAILABLE


def test_v1_upload_path_still_imports() -> None:
    # Smoke: classic csv_import still importable / callable contract
    from ssri_model.manual_training.csv_import import convert_csv_dataset, looks_like_csv_bundle

    assert callable(convert_csv_dataset)
    assert looks_like_csv_bundle("x.zip", b"PK\x03\x04") is False


def _abeokuta_csv() -> Path:
    # model/tests/test_hazard_factors_v2.py → repo root is parents[2]
    return Path(__file__).resolve().parents[2] / "sheet 260_Abeokuta.csv"


def test_layer_validator_surfaces_unit_sanity_warn() -> None:
    from ssri_model.release_shell.validator import validate_point_grid_layer

    content = b"X,Y,Z\n0,0,10\n100,0,-3\n0,100,12\n100,100,-1.5\n"
    report = validate_point_grid_layer(
        content,
        filename="SYNTHETIC_neg_overburden.csv",
        layer_name="overburden_thickness",
        crs="EPSG:32631",
    )
    unit = next(c for c in report["checks"] if c["name"] == "unit_sanity")
    assert unit["status"] == "WARN"
    assert "negative" in unit["message"].lower()
    assert report["overall"] == "WARN"
    assert report["can_train"] is False
    assert report["status"] == "FEATURE_LAYER_ONLY"


@pytest.mark.skipif(
    not _abeokuta_csv().exists(),
    reason="real Abeokuta CSV not present on this checkout (not committed)",
)
def test_real_abeokuta_overburden_negative_z_warns() -> None:
    """ASSUMED-FOR-TEST CRS. The real file's 11,250 negative Z values must warn."""
    from ssri_model.release_shell.validator import validate_point_grid_layer

    report = validate_point_grid_layer(
        _abeokuta_csv().read_bytes(),
        filename="sheet 260_Abeokuta.csv",
        layer_name="overburden_thickness",
        crs="EPSG:32631",  # ASSUMED-FOR-TEST — not client-confirmed
    )
    unit = next(c for c in report["checks"] if c["name"] == "unit_sanity")
    assert unit["status"] in {"WARN", "FAIL"}
    assert "negative" in unit["message"].lower()
    assert "11,250" in unit["message"] or "11250" in unit["message"]
    assert report["value_min"] is not None and report["value_min"] < -200
    assert report["status"] == "FEATURE_LAYER_ONLY"
