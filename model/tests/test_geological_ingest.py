"""Geological catalogue: ingest, validate, coverage, lineaments, offline apply."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import Affine

from ssri_model.api.app import create_app
from ssri_model.geological.apply import apply_geological_to_offline_dataset
from ssri_model.geological.coverage import classify_coverage, match_aoi
from ssri_model.geological.inspect import inspect_point_grid_bytes
from ssri_model.geological.models import GeologicalDatasetRecord
from ssri_model.geological.service import GeologicalService
from ssri_model.geological.storage import GeologicalStorage
from ssri_model.ml.constants import CHANNEL_COUNT, FEATURE_NODATA
from ssri_model.release_shell.channel_schema import CHANNEL_NAMES_V2
from tests.api_helpers import build_api_config

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "geological"


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(build_api_config(tmp_path)))


def test_inspect_detects_delimiter_and_header() -> None:
    content = (FIXTURES / "regular.csv").read_bytes()
    report = inspect_point_grid_bytes(content, filename="regular.csv")
    assert report["overall"] == "INSPECTED"
    assert report["header_present"] is True
    assert report["detected_columns"]["x"] == 0
    assert report["row_count"] == 9
    assert report["crs"] is None
    assert report["measurement_type"] is None


def test_inspect_reports_negatives_and_gaps() -> None:
    neg = inspect_point_grid_bytes((FIXTURES / "negative_thickness.csv").read_bytes())
    assert neg["negative_z_count"] >= 1
    assert neg["overall"] == "INSPECTED"
    gap = inspect_point_grid_bytes((FIXTURES / "gapped.csv").read_bytes())
    assert gap["missing_lattice_cells"] == 1


def test_upload_preserves_original_bytes_and_unique_ids(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    a = svc.create(display_name="A")
    b = svc.create(display_name="B")
    assert a.geo_id != b.geo_id
    raw = (FIXTURES / "regular.csv").read_bytes()
    svc.upload_csv(a.geo_id, filename="regular.csv", content=raw)
    svc.upload_csv(b.geo_id, filename="other.csv", content=(FIXTURES / "gapped.csv").read_bytes())
    a2 = storage.get(a.geo_id)
    b2 = storage.get(b.geo_id)
    assert storage.original_path(a2).read_bytes() == raw
    assert a2.content_sha256 != b2.content_sha256
    with pytest.raises(Exception) as exc:
        svc.upload_csv(a.geo_id, filename="again.csv", content=raw)
    assert getattr(exc.value, "code", "") == "ORIGINAL_IMMUTABLE"


def test_validate_requires_crs_and_measurement(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="NeedCRS")
    svc.upload_csv(rec.geo_id, filename="regular.csv", content=(FIXTURES / "regular.csv").read_bytes())
    with pytest.raises(Exception) as exc:
        svc.validate(rec.geo_id)
    assert getattr(exc.value, "code", "") == "CRS_REQUIRED"
    svc.declare(rec.geo_id, {"crs": "EPSG:32631"})
    with pytest.raises(Exception) as exc2:
        svc.validate(rec.geo_id)
    assert getattr(exc2.value, "code", "") == "MEASUREMENT_REQUIRED"


def test_validate_depth_not_aliased_to_thickness(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="Depth")
    svc.upload_csv(
        rec.geo_id,
        filename="depth_candidate.csv",
        content=(FIXTURES / "depth_candidate.csv").read_bytes(),
    )
    svc.declare(
        rec.geo_id,
        {
            "measurement_type": "depth_to_bedrock",
            "crs": "EPSG:32631",
            "units": "m",
        },
    )
    record, report = svc.validate(rec.geo_id)
    assert record.measurement_type == "depth_to_bedrock"
    assert report["measurement_type"] == "depth_to_bedrock"
    assert report["layer_name"] == "depth_to_bedrock"
    assert report["can_train"] is False


def test_validate_thickness_negative_warn(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="Neg")
    svc.upload_csv(
        rec.geo_id,
        filename="negative_thickness.csv",
        content=(FIXTURES / "negative_thickness.csv").read_bytes(),
    )
    svc.declare(
        rec.geo_id,
        {
            "measurement_type": "overburden_thickness",
            "crs": "EPSG:32631",
            "units": "m",
        },
    )
    _, report = svc.validate(rec.geo_id)
    unit = next(c for c in report["checks"] if c["name"] == "unit_sanity")
    assert unit["status"] == "WARN"
    assert report["overall"] == "WARN"


def test_irregular_grid_fails(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="Irregular")
    svc.upload_csv(
        rec.geo_id,
        filename="irregular.csv",
        content=(FIXTURES / "irregular.csv").read_bytes(),
    )
    svc.declare(
        rec.geo_id,
        {"measurement_type": "overburden_thickness", "crs": "EPSG:32631", "units": "m"},
    )
    record, report = svc.validate(rec.geo_id)
    assert report["overall"] == "FAIL"
    assert record.validation_status == "failed"


def test_activation_defaults_inactive_and_requires_ack(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="Act")
    assert rec.activation_status == "inactive"
    svc.upload_csv(
        rec.geo_id,
        filename="negative_thickness.csv",
        content=(FIXTURES / "negative_thickness.csv").read_bytes(),
    )
    svc.declare(
        rec.geo_id,
        {"measurement_type": "overburden_thickness", "crs": "EPSG:32631", "units": "m"},
    )
    svc.validate(rec.geo_id)
    with pytest.raises(Exception) as exc:
        svc.set_activation(rec.geo_id, activation_status="reporting_only")
    assert getattr(exc.value, "code", "") == "ACTIVATION_WARNINGS"
    updated = svc.set_activation(
        rec.geo_id,
        activation_status="reporting_only",
        acknowledged_warnings=["unit_sanity"],
    )
    assert updated.activation_status == "reporting_only"


def test_list_filters_measurement_type(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    a = svc.create(display_name="T")
    b = svc.create(display_name="D")
    for rec, mt, fixture in (
        (a, "overburden_thickness", "regular.csv"),
        (b, "depth_to_bedrock", "depth_candidate.csv"),
    ):
        svc.upload_csv(rec.geo_id, filename=fixture, content=(FIXTURES / fixture).read_bytes())
        svc.declare(rec.geo_id, {"measurement_type": mt, "crs": "EPSG:32631", "units": "m"})
        svc.validate(rec.geo_id)
    thick, total = storage.list(measurement_type="overburden_thickness")
    assert total == 1
    assert thick[0].geo_id == a.geo_id


def test_coverage_intersection_and_conflict_policy(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    ids = []
    for name in ("C1", "C2"):
        rec = svc.create(display_name=name)
        svc.upload_csv(
            rec.geo_id,
            filename="regular.csv",
            content=(FIXTURES / "regular.csv").read_bytes(),
        )
        svc.declare(
            rec.geo_id,
            {
                "measurement_type": "overburden_thickness",
                "crs": "EPSG:32631",
                "units": "m",
            },
        )
        svc.validate(rec.geo_id)
        svc.set_activation(rec.geo_id, activation_status="reporting_only", acknowledged_warnings=[])
        ids.append(rec.geo_id)
    records = [storage.get(i) for i in ids]
    report = match_aoi(
        records,
        aoi_bbox=[0, 0, 150, 150],
        aoi_crs="EPSG:32631",
        require_validated=True,
        require_activated=True,
    )
    assert len(report["matches"]) == 2
    assert report["conflicts"]
    assert report["used_in_inference"] is False
    assert report["coverage_metric"] == "aoi_bbox_intersection"
    assert report["matches"][0]["aoi_bbox_intersection_fraction"] is not None
    assert classify_coverage([0, 0, 50, 50], [0, 0, 200, 200])[0] == "full"


def test_api_upload_inspect_validate_roundtrip(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/geological/datasets",
        json={"display_name": "API Sheet", "source_client": "test"},
    )
    assert created.status_code == 201
    geo_id = created.json()["dataset"]["geo_id"]
    upload = client.post(
        f"/api/v1/geological/datasets/{geo_id}/upload",
        files={"file": ("regular.csv", (FIXTURES / "regular.csv").read_bytes(), "text/csv")},
    )
    assert upload.status_code == 200
    assert upload.json()["inspect"]["row_count"] == 9
    # Public payload must not leak absolute paths
    assert "original_relpath" not in upload.json()["dataset"]
    declare = client.post(
        f"/api/v1/geological/datasets/{geo_id}/declare",
        json={
            "measurement_type": "overburden_thickness",
            "crs": "EPSG:32631",
            "units": "m",
        },
    )
    assert declare.status_code == 200
    validate = client.post(f"/api/v1/geological/datasets/{geo_id}/validate")
    assert validate.status_code == 200
    assert validate.json()["validation"]["overall"] in {"PASS", "WARN"}
    listing = client.get("/api/v1/geological/datasets")
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1


def test_lineament_ingest_separate_from_point_grid(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="Lines", asset_kind="vector_lineament")
    svc.upload_lineament(
        rec.geo_id,
        filename="lineaments.geojson",
        content=(FIXTURES / "lineaments.geojson").read_bytes(),
    )
    updated = storage.get(rec.geo_id)
    assert updated.asset_kind == "vector_lineament"
    assert updated.feature_count == 2
    assert updated.measurement_type == "lineament_vectors"
    svc.declare(rec.geo_id, {"crs": "EPSG:32631"})
    record, report = svc.validate(rec.geo_id)
    assert record.validation_status == "validated"
    assert report["can_activate_reporting"] is True
    # Cannot upload CSV to lineament dataset
    with pytest.raises(Exception) as exc:
        svc.upload_csv(rec.geo_id, filename="x.csv", content=b"X,Y,Z\n0,0,1\n")
    assert getattr(exc.value, "code", "") in {"ASSET_KIND", "ORIGINAL_IMMUTABLE"}


def _mini_stage25(root: Path) -> Path:
    sample = root / "train" / "s1"
    sample.mkdir(parents=True)
    h = w = 8
    stack = np.zeros((CHANNEL_COUNT, h, w), dtype=np.float32)
    np.save(sample / "feature_stack.npy", stack)
    transform = Affine(100.0, 0.0, 0.0, 0.0, -100.0, 200.0)
    profile = {
        "driver": "GTiff",
        "height": h,
        "width": w,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:32631",
        "transform": transform,
        "nodata": FEATURE_NODATA,
    }
    with rasterio.open(sample / "label.tif", "w", **profile) as ds:
        ds.write(np.zeros((h, w), dtype=np.float32), 1)
    (sample / "metadata.json").write_text("{}", encoding="utf-8")
    (root / "manifest.json").write_text(
        json.dumps({"channels": list(range(CHANNEL_COUNT))}), encoding="utf-8"
    )
    return root


def test_offline_apply_overburden_and_lineaments(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    # overburden
    ob = svc.create(display_name="OB")
    svc.upload_csv(
        ob.geo_id,
        filename="regular.csv",
        content=(FIXTURES / "regular.csv").read_bytes(),
    )
    svc.declare(
        ob.geo_id,
        {"measurement_type": "overburden_thickness", "crs": "EPSG:32631", "units": "m"},
    )
    svc.validate(ob.geo_id)
    svc.set_activation(ob.geo_id, activation_status="reporting_only", acknowledged_warnings=[])

    # lineaments
    ln = svc.create(display_name="LN", asset_kind="vector_lineament")
    svc.upload_lineament(
        ln.geo_id,
        filename="lineaments.geojson",
        content=(FIXTURES / "lineaments.geojson").read_bytes(),
    )
    svc.declare(ln.geo_id, {"crs": "EPSG:32631"})
    svc.validate(ln.geo_id)
    svc.set_activation(ln.geo_id, activation_status="reporting_only", acknowledged_warnings=[])

    target = _mini_stage25(tmp_path / "stage25")
    report = apply_geological_to_offline_dataset(
        storage,
        geo_ids=[ob.geo_id, ln.geo_id],
        target_dataset_root=target,
        window_m=200.0,
        allow_direct_target_root=True,
    )
    assert report["overall"] == "PASS"
    assert report["used_in_inference"] is False
    stack = np.load(target / "train" / "s1" / "feature_stack.npy")
    assert stack.shape[0] == len(CHANNEL_NAMES_V2)
    # depth cannot be applied as thickness
    depth = svc.create(display_name="DepthOnly")
    svc.upload_csv(
        depth.geo_id,
        filename="depth_candidate.csv",
        content=(FIXTURES / "depth_candidate.csv").read_bytes(),
    )
    svc.declare(
        depth.geo_id,
        {"measurement_type": "depth_to_bedrock", "crs": "EPSG:32631", "units": "m"},
    )
    svc.validate(depth.geo_id)
    svc.set_activation(depth.geo_id, activation_status="reporting_only", acknowledged_warnings=[])
    with pytest.raises(Exception) as exc:
        apply_geological_to_offline_dataset(
            storage,
            geo_ids=[depth.geo_id],
            target_dataset_root=target,
            allow_direct_target_root=True,
        )
    assert getattr(exc.value, "code", "") == "APPLY_MEASUREMENT"


def test_api_coverage_endpoint(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post("/api/v1/geological/datasets", json={"display_name": "Cov"})
    geo_id = created.json()["dataset"]["geo_id"]
    client.post(
        f"/api/v1/geological/datasets/{geo_id}/upload",
        files={"file": ("regular.csv", (FIXTURES / "regular.csv").read_bytes(), "text/csv")},
    )
    client.post(
        f"/api/v1/geological/datasets/{geo_id}/declare",
        json={"measurement_type": "overburden_thickness", "crs": "EPSG:32631", "units": "m"},
    )
    client.post(f"/api/v1/geological/datasets/{geo_id}/validate")
    client.post(
        f"/api/v1/geological/datasets/{geo_id}/activation",
        json={"activation_status": "reporting_only", "acknowledged_warnings": []},
    )
    cov = client.post(
        "/api/v1/geological/coverage",
        json={"aoi_bbox": [0, 0, 150, 150], "aoi_crs": "EPSG:32631"},
    )
    assert cov.status_code == 200
    body = cov.json()["coverage"]
    assert body["used_in_inference"] is False
    assert body["coverage_metric"] == "aoi_bbox_intersection"
    desc = (body.get("coverage_metric_description") or "").lower()
    assert "bounding-box" in desc or "bbox" in body["coverage_metric"]
    assert "not valid-cell" in desc or "not valid-cell" in (body.get("note") or "").lower() \
        or "valid-cell" in desc
    assert any(m["geo_id"] == geo_id for m in body["matches"])
    match = next(m for m in body["matches"] if m["geo_id"] == geo_id)
    assert match["used_in_feature_application"] is False


def test_record_to_dict_hides_paths() -> None:
    rec = GeologicalDatasetRecord(
        geo_id="geo_abcdef123456",
        display_name="x",
        asset_kind="point_grid_csv",
        original_filename="a.csv",
        uploaded_at="t",
        content_sha256="abc",
        original_relpath="original/a.csv",
        working_relpath="working/layer.csv",
    )
    payload = rec.to_dict()
    assert "original_relpath" not in payload
    assert payload["has_original"] is True
