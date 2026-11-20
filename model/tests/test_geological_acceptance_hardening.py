"""Acceptance hardening: F2 pixel values, F5 crash recovery, F5 concurrency, F1 path."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from ssri_model.geological.apply import apply_geological_to_offline_dataset
from ssri_model.geological.service import GeologicalService
from ssri_model.geological.storage import GeologicalStorage
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.ml.constants import FEATURE_NODATA
from ssri_model.release_shell.channel_schema import CHANNEL_NAMES_V2, OVERBURDEN_THICKNESS

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "geological"


def _aligned_stage25(root: Path) -> Path:
    """3×3 tile whose cell centres sit on CSV points (0/100/200)."""
    sample = root / "train" / "s1"
    sample.mkdir(parents=True)
    h = w = 3
    # Cell centres: x={0,100,200}, y north→south {200,100,0}
    transform = Affine(100.0, 0.0, -50.0, 0.0, -100.0, 250.0)
    stack = np.zeros((13, h, w), dtype=np.float32)
    np.save(sample / "feature_stack.npy", stack)
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
        json.dumps({"channels": list(range(13))}), encoding="utf-8"
    )
    return root


def _prepare_mapped_overburden(svc: GeologicalService) -> str:
    rec = svc.create(display_name="PixelMapped")
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
    assert record.x_column == "Easting_m"
    assert record.y_column == "Northing_m"
    assert record.z_column == "Thickness_m"
    svc.set_activation(
        rec.geo_id, activation_status="reporting_only", acknowledged_warnings=[]
    )
    return rec.geo_id


def test_f2_pixel_values_use_thickness_not_notes(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    geo_id = _prepare_mapped_overburden(svc)
    target = _aligned_stage25(tmp_path / "stage25")

    report = apply_geological_to_offline_dataset(
        storage,
        geo_ids=[geo_id],
        target_dataset_root=target,
        allow_direct_target_root=True,
    )
    mapping = report["steps"][0]["column_mapping"]
    assert mapping == {
        "x_column": "Easting_m",
        "y_column": "Northing_m",
        "z_column": "Thickness_m",
    }
    assert "Notes" not in mapping.values()

    stack = np.load(target / "train" / "s1" / "feature_stack.npy")
    assert stack.shape[0] == 16 == len(CHANNEL_NAMES_V2)
    idx = CHANNEL_NAMES_V2.index(OVERBURDEN_THICKNESS)
    assert idx == 13
    band = stack[idx]

    # Row order north→south: y=200,100,0 ; cols x=0,100,200
    expected = np.array(
        [
            [10.0, 11.0, 12.0],  # y=200
            [10.0, 11.0, 12.0],  # y=100
            [10.0, 11.0, 12.0],  # y=0
        ],
        dtype=np.float32,
    )
    np.testing.assert_allclose(band, expected, rtol=0, atol=1e-5)

    # Notes column values are letters — must never land in the raster as numbers.
    assert not np.any(np.isfinite(band) & (band > 12.5))

    # Expand canvas: uncovered cells outside the 3×3 mapped grid stay nodata when
    # a larger empty pad is considered — here the whole tile is covered; verify
    # FEATURE_NODATA is preserved on a second apply target with offset grid.
    offset_root = tmp_path / "offset"
    sample = offset_root / "train" / "s1"
    sample.mkdir(parents=True)
    # Centres at x=1000.. — far from CSV → all nodata
    transform = Affine(100.0, 0.0, 950.0, 0.0, -100.0, 1250.0)
    np.save(sample / "feature_stack.npy", np.zeros((13, 3, 3), dtype=np.float32))
    profile = {
        "driver": "GTiff",
        "height": 3,
        "width": 3,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:32631",
        "transform": transform,
        "nodata": FEATURE_NODATA,
    }
    with rasterio.open(sample / "label.tif", "w", **profile) as ds:
        ds.write(np.zeros((3, 3), dtype=np.float32), 1)
    (sample / "metadata.json").write_text("{}", encoding="utf-8")
    (offset_root / "manifest.json").write_text("{}", encoding="utf-8")

    apply_geological_to_offline_dataset(
        storage,
        geo_ids=[geo_id],
        target_dataset_root=offset_root,
        allow_direct_target_root=True,
    )
    far = np.load(sample / "feature_stack.npy")[idx]
    assert far.shape == (3, 3)
    assert np.all(far == FEATURE_NODATA)


def test_f1_http_apply_never_needs_allow_direct_flag(tmp_path: Path) -> None:
    """Registered-id apply path works with default allow_direct_target_root=False."""
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    geo_id = _prepare_mapped_overburden(svc)
    training = TrainingStorage(tmp_path)
    ds = training.create_dataset(name="http-style")
    _aligned_stage25(Path(ds.root_path))
    report = apply_geological_to_offline_dataset(
        storage,
        geo_ids=[geo_id],
        target_dataset_id=ds.dataset_id,
        # intentionally omit allow_direct_target_root
    )
    assert report["overall"] == "PASS"
    assert report["target_dataset_id"] == ds.dataset_id


def test_f1_default_rejects_raw_path_without_dataset_id(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    geo_id = _prepare_mapped_overburden(svc)
    target = _aligned_stage25(tmp_path / "stage25")
    with pytest.raises(Exception) as exc:
        apply_geological_to_offline_dataset(
            storage,
            geo_ids=[geo_id],
            target_dataset_root=target,
            # allow_direct_target_root defaults False
        )
    assert getattr(exc.value, "code", "") == "APPLY_TARGET_ID_REQUIRED"


def test_f1_resolves_registered_dataset_id(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    geo_id = _prepare_mapped_overburden(svc)
    training = TrainingStorage(tmp_path)
    ds = training.create_dataset(name="harden-target")
    _aligned_stage25(Path(ds.root_path))
    report = apply_geological_to_offline_dataset(
        storage,
        geo_ids=[geo_id],
        target_dataset_id=ds.dataset_id,
    )
    assert report["overall"] == "PASS"
    assert report["target_dataset_id"] == ds.dataset_id
    stack = np.load(Path(ds.root_path) / "train" / "s1" / "feature_stack.npy")
    assert stack.shape[0] == 16


def test_f5_crash_recovery_from_pass_report(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    geo_id = _prepare_mapped_overburden(svc)
    target = _aligned_stage25(tmp_path / "stage25")
    report = apply_geological_to_offline_dataset(
        storage,
        geo_ids=[geo_id],
        target_dataset_root=target,
        target_dataset_id="ds_sim",
        allow_direct_target_root=True,
        record_provenance=False,  # simulate crash after report, before ledger
    )
    report_path = Path(report["report_path"])
    assert report_path.exists()
    assert report["overall"] == "PASS"
    assert report["used_in_inference"] is False
    assert storage.feature_application_status(storage.get(geo_id))[
        "used_in_feature_application"
    ] is False

    recovered = storage.recover_feature_applications_from_report(report_path)
    assert recovered["recovered"] == 1
    assert recovered["used_in_inference"] is False
    status = storage.feature_application_status(storage.get(geo_id))
    assert status["used_in_feature_application"] is True
    assert status["feature_applications"][0]["application_id"] == report["application_id"]
    assert status["feature_applications"][0]["content_sha256"] == storage.get(
        geo_id
    ).content_sha256
    assert status["feature_applications"][0]["used_in_inference"] is False

    # Second recovery is idempotent — no duplicate successful rows
    again = storage.recover_feature_applications_from_report(report_path)
    assert again["recovered"] == 0
    assert storage.feature_application_status(storage.get(geo_id))[
        "feature_application_count"
    ] == 1


def test_f5_incomplete_report_not_recovered_as_success(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    fake = tmp_path / "geological_apply_report.json"
    fake.write_text(
        json.dumps(
            {
                "overall": "FAIL",
                "application_id": "app_bad",
                "steps": [{"geo_id": "geo_abcdef123456", "content_sha256": "x"}],
                "used_in_inference": False,
            }
        ),
        encoding="utf-8",
    )
    result = storage.recover_feature_applications_from_report(fake)
    assert result["recovered"] == 0
    assert result["reason"] == "report_not_pass"


def test_f5_concurrent_ledger_appends(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    barrier = threading.Barrier(8)
    errors: list[BaseException] = []

    def worker(i: int) -> bool:
        barrier.wait(timeout=10)
        try:
            return storage.record_feature_application(
                {
                    "application_id": f"app_concurrent_{i:02d}",
                    "geo_id": f"geo_{i:012d}",
                    "content_sha256": f"sha_{i}",
                    "target_dataset_id": "ds_concurrent",
                    "measurement_type": "overburden_thickness",
                    "channels": ["overburden_thickness"],
                    "overall": "PASS",
                    "used_in_inference": False,
                }
            )
        except BaseException as exc:  # noqa: BLE001 — collect for assertion
            errors.append(exc)
            raise

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(worker, i) for i in range(8)]
        results = [f.result() for f in as_completed(futures)]

    assert not errors
    assert all(results)
    rows = storage.list_feature_applications()
    assert len(rows) == 8
    for row in rows:
        # Every ledger line must remain valid JSON dict with required fields
        assert row["overall"] == "PASS"
        assert row["used_in_inference"] is False
        assert row["application_id"].startswith("app_concurrent_")
        json.dumps(row)  # re-serializable

    # Duplicate concurrent writes of the same identity must not multiply rows
    barrier2 = threading.Barrier(4)

    def dup_worker() -> bool:
        barrier2.wait(timeout=10)
        return storage.record_feature_application(
            {
                "application_id": "app_same",
                "geo_id": "geo_000000000001",
                "content_sha256": "sha_same",
                "target_dataset_id": "ds_concurrent",
                "channels": ["overburden_thickness"],
                "overall": "PASS",
            }
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        dup_results = [f.result() for f in as_completed([pool.submit(dup_worker) for _ in range(4)])]
    assert sum(1 for r in dup_results if r) == 1
    same = [
        r
        for r in storage.list_feature_applications()
        if r.get("application_id") == "app_same"
    ]
    assert len(same) == 1
