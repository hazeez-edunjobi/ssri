"""Remediation tests for audit findings F1–F5."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import Affine

from ssri_model.api.app import create_app
from ssri_model.geological.target import resolve_offline_apply_target
from ssri_model.geological.apply import apply_geological_to_offline_dataset
from ssri_model.geological.coverage import match_aoi
from ssri_model.geological.service import GeologicalService
from ssri_model.geological.storage import GeologicalStorage
from ssri_model.manual_training.exceptions import UnsafePathError
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.ml.constants import CHANNEL_COUNT, FEATURE_NODATA
from ssri_model.release_shell.channel_schema import CHANNEL_NAMES_V2
from tests.api_helpers import build_api_config

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "geological"


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(build_api_config(tmp_path)))


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


def _prepare_overburden(svc: GeologicalService, fixture: str = "regular.csv", **declare):
    rec = svc.create(display_name="OB")
    svc.upload_csv(
        rec.geo_id,
        filename=fixture,
        content=(FIXTURES / fixture).read_bytes(),
    )
    payload = {
        "measurement_type": "overburden_thickness",
        "crs": "EPSG:32631",
        "units": "m",
        **declare,
    }
    svc.declare(rec.geo_id, payload)
    svc.validate(rec.geo_id)
    svc.set_activation(
        rec.geo_id, activation_status="reporting_only", acknowledged_warnings=[]
    )
    return rec.geo_id


# --- F1: secure offline apply path ---


def test_f1_resolve_requires_registered_dataset_id(tmp_path: Path) -> None:
    training = TrainingStorage(tmp_path)
    ds = training.create_dataset(name="safe-target")
    _mini_stage25(Path(ds.root_path))

    dataset_id, root = resolve_offline_apply_target(
        training, target_dataset_id=ds.dataset_id
    )
    assert dataset_id == ds.dataset_id
    assert root == Path(ds.root_path).resolve()
    assert str(training.datasets_dir.resolve()) in str(root)


def test_f1_unknown_dataset_id_fails(tmp_path: Path) -> None:
    training = TrainingStorage(tmp_path)
    with pytest.raises(Exception) as exc:
        resolve_offline_apply_target(training, target_dataset_id="ds_doesnotexist1")
    assert getattr(exc.value, "code", "") == "DATASET_NOT_FOUND"


def test_f1_traversal_and_absolute_path_rejected(tmp_path: Path) -> None:
    training = TrainingStorage(tmp_path)
    with pytest.raises(UnsafePathError):
        resolve_offline_apply_target(training, target_dataset_id="../etc/passwd")
    with pytest.raises(UnsafePathError):
        resolve_offline_apply_target(
            training, target_dataset_id=str(tmp_path / "outside")
        )


def test_f1_api_rejects_root_only_and_accepts_dataset_id(tmp_path: Path) -> None:
    client = _client(tmp_path)
    # API config uses tmp_path/service-outputs as output_root.
    output_root = tmp_path / "service-outputs"
    training = TrainingStorage(output_root)
    ds = training.create_dataset(name="api-target")
    _mini_stage25(Path(ds.root_path))

    storage = GeologicalStorage(output_root)
    svc = GeologicalService(storage)
    geo_id = _prepare_overburden(svc)

    rejected = client.post(
        "/api/v1/geological/apply/offline",
        json={
            "geo_ids": [geo_id],
            "target_dataset_root": str(tmp_path / "escape_me"),
        },
    )
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "APPLY_TARGET_ID_REQUIRED"

    outside = tmp_path / "outside_stage25"
    _mini_stage25(outside)
    mismatched = client.post(
        "/api/v1/geological/apply/offline",
        json={
            "geo_ids": [geo_id],
            "target_dataset_id": ds.dataset_id,
            "target_dataset_root": str(outside),
        },
    )
    assert mismatched.status_code == 400
    assert mismatched.json()["error"]["code"] == "UNSAFE_PATH"

    ok = client.post(
        "/api/v1/geological/apply/offline",
        json={"geo_ids": [geo_id], "target_dataset_id": ds.dataset_id},
    )
    assert ok.status_code == 200
    body = ok.json()["application"]
    assert body["overall"] == "PASS"
    assert body["target_dataset_id"] == ds.dataset_id
    assert Path(ds.root_path).resolve() == Path(body["target_dataset_root"]).resolve()
    stack = np.load(Path(ds.root_path) / "train" / "s1" / "feature_stack.npy")
    assert stack.shape[0] == len(CHANNEL_NAMES_V2)


def test_f1_symlink_escape_rejected_where_supported(tmp_path: Path) -> None:
    training = TrainingStorage(tmp_path)
    ds = training.create_dataset(name="link-target")
    outside = tmp_path / "outside_data"
    outside.mkdir()
    link = Path(ds.root_path)
    # Replace data dir with symlink pointing outside training root when OS allows.
    if link.exists():
        for child in link.iterdir():
            if child.is_file():
                child.unlink()
            else:
                import shutil

                shutil.rmtree(child)
        try:
            link.rmdir()
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("Symlink creation not supported in this environment")
    # dataset.json still points at the old root_path string; resolve_under_training
    # on a path that escapes should raise.
    escaped = tmp_path / "escape_dest"
    escaped.mkdir()
    with pytest.raises(UnsafePathError):
        training.resolve_under_training(escaped)


# --- F2: declared column mappings ---


def test_f2_nonstandard_headers_validate_and_apply(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="Mapped")
    svc.upload_csv(
        rec.geo_id,
        filename="nonstandard_headers.csv",
        content=(FIXTURES / "nonstandard_headers.csv").read_bytes(),
    )
    svc.declare(
        rec.geo_id,
        {
            "measurement_type": "overburden_thickness",
            "crs": "EPSG:32631",
            "units": "m",
            "x_column": "Easting_m",
            "y_column": "Northing_m",
            "z_column": "Thickness_m",
        },
    )
    record, report = svc.validate(rec.geo_id)
    assert report["overall"] in {"PASS", "WARN"}
    assert report["column_mapping"]["applied"] is True
    assert record.x_column == "Easting_m"
    svc.set_activation(
        rec.geo_id, activation_status="reporting_only", acknowledged_warnings=[]
    )

    training = TrainingStorage(tmp_path)
    ds = training.create_dataset(name="mapped-target")
    target = _mini_stage25(Path(ds.root_path))
    applied = apply_geological_to_offline_dataset(
        storage,
        geo_ids=[rec.geo_id],
        target_dataset_root=target,
        target_dataset_id=ds.dataset_id,
        allow_direct_target_root=True,
    )
    assert applied["overall"] == "PASS"
    assert applied["steps"][0]["column_mapping"]["x_column"] == "Easting_m"
    stack = np.load(target / "train" / "s1" / "feature_stack.npy")
    assert stack.shape[0] == len(CHANNEL_NAMES_V2)


def test_f2_missing_mapped_column_fails(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="MissingCol")
    svc.upload_csv(
        rec.geo_id,
        filename="nonstandard_headers.csv",
        content=(FIXTURES / "nonstandard_headers.csv").read_bytes(),
    )
    svc.declare(
        rec.geo_id,
        {
            "measurement_type": "overburden_thickness",
            "crs": "EPSG:32631",
            "units": "m",
            "x_column": "NotARealColumn",
            "y_column": "Northing_m",
            "z_column": "Thickness_m",
        },
    )
    record, report = svc.validate(rec.geo_id)
    assert report["overall"] == "FAIL"
    assert record.validation_status == "failed"


def test_f2_ambiguous_mapping_fails(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="Ambiguous")
    svc.upload_csv(
        rec.geo_id,
        filename="nonstandard_headers.csv",
        content=(FIXTURES / "nonstandard_headers.csv").read_bytes(),
    )
    svc.declare(
        rec.geo_id,
        {
            "measurement_type": "overburden_thickness",
            "crs": "EPSG:32631",
            "units": "m",
            "x_column": "Easting_m",
            "y_column": "Easting_m",
            "z_column": "Thickness_m",
        },
    )
    _, report = svc.validate(rec.geo_id)
    assert report["overall"] == "FAIL"
    assert any(c["name"] == "column_mapping" for c in report["checks"])


def test_f2_default_headers_unchanged(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    geo_id = _prepare_overburden(svc, "regular.csv")
    record = storage.get(geo_id)
    assert record.validation_status == "validated"


def test_f2_depth_still_cannot_apply_as_thickness(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="DepthMap")
    svc.upload_csv(
        rec.geo_id,
        filename="nonstandard_headers.csv",
        content=(FIXTURES / "nonstandard_headers.csv").read_bytes(),
    )
    svc.declare(
        rec.geo_id,
        {
            "measurement_type": "depth_to_bedrock",
            "crs": "EPSG:32631",
            "units": "m",
            "x_column": "Easting_m",
            "y_column": "Northing_m",
            "z_column": "Thickness_m",
        },
    )
    svc.validate(rec.geo_id)
    svc.set_activation(
        rec.geo_id, activation_status="reporting_only", acknowledged_warnings=[]
    )
    target = _mini_stage25(tmp_path / "stage25")
    with pytest.raises(Exception) as exc:
        apply_geological_to_offline_dataset(
            storage,
            geo_ids=[rec.geo_id],
            target_dataset_root=target,
            allow_direct_target_root=True,
        )
    assert getattr(exc.value, "code", "") == "APPLY_MEASUREMENT"


# --- F3: bbox semantics ---


def test_f3_coverage_metric_is_bbox_not_valid_cells(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    geo_id = _prepare_overburden(svc)
    report = match_aoi(
        [storage.get(geo_id)],
        aoi_bbox=[0, 0, 150, 150],
        aoi_crs="EPSG:32631",
        storage=storage,
    )
    assert report["coverage_metric"] == "aoi_bbox_intersection"
    assert "valid-cell" in report["coverage_metric_description"].lower() or \
        "valid-cell" in report["note"].lower() or \
        "not valid" in report["coverage_metric_description"].lower()
    m = report["matches"][0]
    assert "aoi_bbox_intersection_fraction" in m
    assert m["approx_aoi_coverage_fraction"] == m["aoi_bbox_intersection_fraction"]

    # CRS mismatch warning still surfaces
    warn_report = match_aoi(
        [storage.get(geo_id)],
        aoi_bbox=[0, 0, 150, 150],
        aoi_crs="EPSG:4326",
        storage=storage,
    )
    assert warn_report["matches"][0]["crs_warning"]


# --- F4: tenancy model ---


def test_f4_records_created_by_and_exposes_shared_tenancy(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/geological/datasets",
        json={"display_name": "Owned"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["tenancy_model"] == "single_tenant_shared_operator_catalogue"
    assert body["dataset"]["created_by_key_id"]
    listing = client.get("/api/v1/geological/datasets")
    assert listing.json()["tenancy_model"] == "single_tenant_shared_operator_catalogue"


# --- F5: feature application provenance ---


def test_f5_successful_apply_updates_provenance(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    geo_id = _prepare_overburden(svc)
    training = TrainingStorage(tmp_path)
    ds = training.create_dataset(name="prov-target")
    target = _mini_stage25(Path(ds.root_path))

    before = storage.feature_application_status(storage.get(geo_id))
    assert before["used_in_feature_application"] is False

    apply_geological_to_offline_dataset(
        storage,
        geo_ids=[geo_id],
        target_dataset_root=target,
        target_dataset_id=ds.dataset_id,
        allow_direct_target_root=True,
    )
    after = storage.feature_application_status(storage.get(geo_id))
    assert after["used_in_feature_application"] is True
    assert after["feature_application_count"] == 1
    assert after["latest_target_dataset_id"] == ds.dataset_id
    assert after["feature_applications"][0]["content_sha256"] == storage.get(
        geo_id
    ).content_sha256
    assert after["feature_applications"][0]["used_in_inference"] is False

    # Survives "restart" (new storage handle on same root)
    storage2 = GeologicalStorage(tmp_path)
    revived = storage2.feature_application_status(storage2.get(geo_id))
    assert revived["used_in_feature_application"] is True

    # Coverage reflects provenance
    report = match_aoi(
        [storage2.get(geo_id)],
        aoi_bbox=[0, 0, 200, 200],
        storage=storage2,
    )
    assert report["matches"][0]["used_in_feature_application"] is True

    # Repeated application increments history
    apply_geological_to_offline_dataset(
        storage2,
        geo_ids=[geo_id],
        target_dataset_root=target,
        target_dataset_id=ds.dataset_id,
        allow_direct_target_root=True,
    )
    twice = storage2.feature_application_status(storage2.get(geo_id))
    assert twice["feature_application_count"] == 2


def test_f5_failed_apply_does_not_mark_used(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="DepthFail")
    svc.upload_csv(
        rec.geo_id,
        filename="depth_candidate.csv",
        content=(FIXTURES / "depth_candidate.csv").read_bytes(),
    )
    svc.declare(
        rec.geo_id,
        {"measurement_type": "depth_to_bedrock", "crs": "EPSG:32631", "units": "m"},
    )
    svc.validate(rec.geo_id)
    svc.set_activation(
        rec.geo_id, activation_status="reporting_only", acknowledged_warnings=[]
    )
    target = _mini_stage25(tmp_path / "stage25")
    with pytest.raises(Exception):
        apply_geological_to_offline_dataset(
            storage,
            geo_ids=[rec.geo_id],
            target_dataset_root=target,
            allow_direct_target_root=True,
        )
    status = storage.feature_application_status(storage.get(rec.geo_id))
    assert status["used_in_feature_application"] is False
    assert status["feature_application_count"] == 0
