"""Geological catalogue overlays for assess (lineament / overburden / TMI context)."""

from __future__ import annotations

import json
from pathlib import Path

import torch

from ssri_model.api.assess_conditioning import sample_conditioning_features
from ssri_model.api.geological_conditioning_overlay import (
    enrich_conditioning_with_geological_catalogue,
)
from ssri_model.geological.durable import build_geological_storage
from ssri_model.ml.constants import CHANNEL_COUNT


def _seed_tmi_dataset(root: Path) -> str:
    storage = build_geological_storage(root)
    rec = storage.create_shell(
        display_name="Abeokuta-like TMI",
        asset_kind="point_grid_csv",
        source_client="test",
    )
    geo_id = rec.geo_id
    working = storage.dataset_dir(geo_id) / "working" / "layer.csv"
    working.parent.mkdir(parents=True, exist_ok=True)
    working.write_text("X,Y,Z\n1,1,10\n", encoding="utf-8")
    rec.measurement_type = "total_magnetic_intensity"
    rec.crs = "EPSG:32632"
    rec.working_crs = "EPSG:32631"
    rec.validation_status = "validated"
    rec.activation_status = "inactive"
    rec.working_relpath = "working/layer.csv"
    rec.units = "nT"
    rec.provenance = {
        "z_meaning": "total_magnetic_intensity",
        "display_crs": "EPSG:4326",
        "display_bbox_wgs84": [3.0, 7.0, 3.5, 7.5],
        "publication": "test publication",
    }
    storage.save(rec)
    return geo_id


def _seed_overburden(root: Path) -> str:
    storage = build_geological_storage(root)
    rec = storage.create_shell(
        display_name="Thickness grid",
        asset_kind="point_grid_csv",
        source_client="test",
    )
    geo_id = rec.geo_id
    working = storage.dataset_dir(geo_id) / "working" / "layer.csv"
    working.parent.mkdir(parents=True, exist_ok=True)
    # Rough WGS84 lon/lat grid near Abeokuta for simple CRS=4326 sampling
    working.write_text(
        "X,Y,Z\n3.20,7.10,18.5\n3.21,7.11,19.0\n3.22,7.12,17.25\n",
        encoding="utf-8",
    )
    rec.measurement_type = "overburden_thickness"
    rec.crs = "EPSG:4326"
    rec.validation_status = "validated"
    rec.activation_status = "reporting_only"
    rec.working_relpath = "working/layer.csv"
    rec.units = "m"
    rec.x_column = "X"
    rec.y_column = "Y"
    rec.z_column = "Z"
    rec.grid_spacing_x = 0.01
    rec.grid_spacing_y = 0.01
    rec.provenance = {"display_bbox_wgs84": [3.0, 7.0, 3.5, 7.5]}
    storage.save(rec)
    return geo_id


def _seed_lineaments(root: Path) -> str:
    storage = build_geological_storage(root)
    rec = storage.create_shell(
        display_name="Test lineaments",
        asset_kind="vector_lineament",
        source_client="test",
    )
    geo_id = rec.geo_id
    working = storage.dataset_dir(geo_id) / "working" / "lineaments.geojson"
    working.parent.mkdir(parents=True, exist_ok=True)
    # Lon/lat NE-SW-ish segment across Abeokuta box
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[3.05, 7.05], [3.40, 7.40]],
                },
            }
        ],
    }
    working.write_text(json.dumps(geojson), encoding="utf-8")
    rec.measurement_type = "lineament_vectors"
    rec.asset_kind = "vector_lineament"
    rec.crs = "EPSG:4326"
    rec.validation_status = "validated"
    rec.activation_status = "reporting_only"
    rec.working_relpath = "working/lineaments.geojson"
    rec.provenance = {"display_bbox_wgs84": [3.0, 7.0, 3.5, 7.5]}
    storage.save(rec)
    return geo_id


def test_tmi_context_attached_without_claiming_overburden(tmp_path: Path) -> None:
    _seed_tmi_dataset(tmp_path)
    base = sample_conditioning_features(torch.zeros(1, CHANNEL_COUNT, 4, 4))
    enriched = enrich_conditioning_with_geological_catalogue(
        base,
        output_root=tmp_path,
        latitude=7.15,
        longitude=3.25,
    )
    ctx = enriched.get("geological_context") or []
    assert len(ctx) == 1
    assert ctx[0]["not_overburden_thickness"] is True
    assert "NE-SW" in (ctx[0].get("structural_orientation_theme") or "")
    ob = enriched["layers"]["overburden_thickness"]
    assert ob["status"] == "unavailable"
    assert "TMI" in (ob.get("reason") or "")
    assert ob.get("used_in_inference") is False
    dens = enriched["layers"]["lineament_density"]
    assert dens["status"] == "unavailable"
    assert "fabricated" in (dens.get("reason") or "").lower() or "activated lineament" in (
        dens.get("reason") or ""
    ).lower()
    assert dens.get("used_in_inference") is False


def test_activated_overburden_sampled_not_inference(tmp_path: Path) -> None:
    _seed_overburden(tmp_path)
    base = sample_conditioning_features(torch.zeros(1, CHANNEL_COUNT, 4, 4))
    enriched = enrich_conditioning_with_geological_catalogue(
        base,
        output_root=tmp_path,
        latitude=7.11,
        longitude=3.21,
    )
    ob = enriched["layers"]["overburden_thickness"]
    assert ob["status"] == "available"
    assert ob["value"] == 19.0
    assert ob.get("used_in_inference") is False
    assert "catalogue" in (ob.get("reason") or "").lower() or ob.get("source") == "geological_catalogue"


def test_activated_lineaments_sampled_not_faults(tmp_path: Path) -> None:
    _seed_lineaments(tmp_path)
    base = sample_conditioning_features(torch.zeros(1, CHANNEL_COUNT, 4, 4))
    enriched = enrich_conditioning_with_geological_catalogue(
        base,
        output_root=tmp_path,
        latitude=7.20,
        longitude=3.20,
    )
    dens = enriched["layers"]["lineament_density"]
    dist = enriched["layers"]["lineament_distance"]
    assert dens["status"] == "available"
    assert dist["status"] == "available"
    assert dens.get("used_in_inference") is False
    assert "fault" in (dens.get("reason") or "").lower() or dens.get("source") == "geological_catalogue"
