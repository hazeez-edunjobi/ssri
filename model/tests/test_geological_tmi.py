"""Client TMI geophysical ingest — software correctness fixtures only.

Synthetic points are not scientific evidence and must not unblock Stage 2.5 training.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
import rasterio

from ssri_model.geological.inspect import inspect_point_grid_bytes
from ssri_model.geological.models import (
    MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
    canonicalize_measurement_type,
    is_tmi_measurement,
)
from ssri_model.geological.service import GeologicalService
from ssri_model.geological.storage import GeologicalStorage
from ssri_model.geological.tmi import (
    assess_feature_compatibility,
    parse_tmi_points,
    validate_tmi_point_survey,
)
from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "geological"


def test_tmi_aliases_canonicalize() -> None:
    assert canonicalize_measurement_type("TMI") == MEASUREMENT_TOTAL_MAGNETIC_INTENSITY
    assert canonicalize_measurement_type("total_magnetic_intensity") == (
        MEASUREMENT_TOTAL_MAGNETIC_INTENSITY
    )
    assert is_tmi_measurement("tmi")
    assert not is_tmi_measurement("overburden_thickness")


def test_inspect_suggests_tmi_column() -> None:
    report = inspect_point_grid_bytes(
        (FIXTURES / "tmi_mapped_headers.csv").read_bytes(),
        filename="tmi_mapped_headers.csv",
    )
    assert report["header_row"] == ["Lon", "Lat", "TMI"]
    assert report["detected_columns"]["z"] == 2


def test_parse_with_column_mapping() -> None:
    raw = (FIXTURES / "tmi_mapped_headers.csv").read_bytes()
    parsed = parse_tmi_points(
        raw, x_column="Lon", y_column="Lat", z_column="TMI"
    )
    assert parsed["ok"]
    assert len(parsed["xs"]) == 6
    assert parsed["column_indices"]["z"] == 2


def test_validate_tmi_geographic_and_stats() -> None:
    raw = (FIXTURES / "tmi_client_xy_z.csv").read_bytes()
    report = validate_tmi_point_survey(
        raw,
        filename="tmi_client_xy_z.csv",
        crs="EPSG:4326",
        units="unknown",
        x_column="X",
        y_column="Y",
        z_column="Z",
        provenance={"survey_date": "unknown"},
    )
    assert report["overall"] in {"PASS", "WARN"}
    assert report["can_train"] is False
    assert report["scientific_validation_status"] == "NOT_VALIDATED"
    assert report["tmi_statistics"]["count"] == 12
    assert report["tmi_statistics"]["units"] == "unknown"
    assert report["feature_compatibility"]["corresponds_to_existing_channel"] is False
    assert report["feature_compatibility"]["may_add_as_14th_channel"] is False
    assert report["feature_compatibility"]["production_model_unchanged"] is True
    assert report["feature_compatibility"]["is_hazard_label"] is False
    assert CHANNEL_NAMES[report["feature_compatibility"]["existing_related_channel"]["index_0_based"]] == "magnetics"
    assert report["feature_compatibility"]["channel_count_frozen"] == CHANNEL_COUNT


def test_validate_rejects_metres_as_degrees() -> None:
    csv = b"X,Y,Z\n500000,700000,100.0\n500100,700000,101.0\n500000,700100,102.0\n500100,700100,103.0\n"
    report = validate_tmi_point_survey(
        csv, filename="bad.csv", crs="EPSG:4326", units="nT"
    )
    assert report["overall"] == "FAIL"
    assert report["can_process"] is False


def test_abeokuta_authoritative_preset_and_real_csv_qc() -> None:
    from ssri_model.geological.abeokuta_tmi import (
        AUTHORITATIVE_ABEOKUTA_TMI,
        apply_abeokuta_tmi_defaults,
        looks_like_abeokuta_filename,
    )
    from ssri_model.geological.tmi import build_tmi_preview

    assert looks_like_abeokuta_filename("sheet 260_Abeokuta.csv")
    filled = apply_abeokuta_tmi_defaults({})
    assert filled["crs"] == "EPSG:32632"
    assert filled["working_crs"] == "EPSG:32631"
    assert filled["x_column"] == "X"
    assert filled["z_column"] == "Z"
    assert filled["measurement_type"] == MEASUREMENT_TOTAL_MAGNETIC_INTENSITY
    assert AUTHORITATIVE_ABEOKUTA_TMI["x_meaning"] == "easting"
    assert AUTHORITATIVE_ABEOKUTA_TMI["display_crs"] == "EPSG:4326"

    repo_csv = Path(__file__).resolve().parents[2] / "sheet 260_Abeokuta.csv"
    if not repo_csv.is_file():
        pytest.skip("Abeokuta CSV not present in workspace")
    # Head sample alone may fail extent checks; include file corners.
    lines = repo_csv.read_bytes().splitlines()
    head = b"X,Y,Z\n" + b"\n".join(lines[1:200] + lines[-50:])
    report = validate_tmi_point_survey(
        head,
        filename="sheet 260_Abeokuta.csv",
        crs=AUTHORITATIVE_ABEOKUTA_TMI["crs"],
        units=AUTHORITATIVE_ABEOKUTA_TMI["units"],
        x_column="X",
        y_column="Y",
        z_column="Z",
        working_crs=AUTHORITATIVE_ABEOKUTA_TMI["working_crs"],
        provenance=filled["provenance"],
    )
    assert report["overall"] in {"PASS", "WARN"}
    assert report["can_train"] is False
    assert report["scientific_validation_status"] == "NOT_VALIDATED"
    assert report["column_mapping"]["z_meaning"] == "total_magnetic_intensity"
    assert report["column_mapping"]["x_meaning"] == "easting"
    assert report["crs_verification"]["ok"] is True
    assert report["tmi_statistics"]["count"] >= 1
    preview = build_tmi_preview(
        head,
        crs="EPSG:32632",
        x_column="X",
        y_column="Y",
        z_column="Z",
        processing_crs="EPSG:32631",
        display_crs="EPSG:4326",
    )
    assert preview["ok"] is True
    assert preview["wgs84_map_eligible"] is True
    assert preview["survey_local"] is not None
    assert preview["geojson"] is not None


def test_abeokuta_wgs84_fixture_passes_and_maps() -> None:
    from ssri_model.geological.tmi import build_tmi_preview

    raw = (FIXTURES / "tmi_client_xy_z.csv").read_bytes()
    report = validate_tmi_point_survey(
        raw,
        filename="abeokuta_wgs84_fixture.csv",
        crs="EPSG:4326",
        x_column="X",
        y_column="Y",
        z_column="Z",
    )
    assert report["overall"] in {"PASS", "WARN"}
    preview = build_tmi_preview(raw, crs="EPSG:4326")
    assert preview["wgs84_map_eligible"] is True
    assert preview["geojson"] is not None
    assert preview["geojson"]["features"]


def test_validate_invalid_lon_lat() -> None:
    csv = b"X,Y,Z\n190.0,7.0,100.0\n3.3,7.1,101.0\n3.4,7.2,102.0\n3.5,7.3,103.0\n"
    report = validate_tmi_point_survey(
        csv, filename="bad_lon.csv", crs="EPSG:4326"
    )
    assert report["overall"] == "FAIL"
    names = {c["name"]: c["status"] for c in report["checks"]}
    assert names.get("geographic_ranges") == "FAIL"


def test_feature_compatibility_never_claims_live() -> None:
    compat = assess_feature_compatibility(
        crs="EPSG:4326",
        units=None,
        spatial={"gridding_suitable": True, "irregular_point_cloud": True},
        tmi_stats={"count": 12},
    )
    assert compat["contributes_to_live_hazard_predictions"] is False
    assert compat["blocks_stage25_training_promotion"] is True
    assert compat["assumes_nanotesla"] is False


def test_service_tmi_upload_validate_process(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="Client TMI fixture", source_client="synthetic_fixture")
    raw = (FIXTURES / "tmi_client_xy_z.csv").read_bytes()
    svc.upload_csv(rec.geo_id, filename="tmi_client_xy_z.csv", content=raw)
    original = storage.original_path(storage.get(rec.geo_id))
    assert original is not None
    assert original.read_bytes() == raw

    svc.declare(
        rec.geo_id,
        {
            "measurement_type": "tmi",
            "crs": "EPSG:4326",
            "units": "unknown",
            "x_column": "X",
            "y_column": "Y",
            "z_column": "Z",
            "survey_method": "unknown",
        },
    )
    record, report = svc.validate(rec.geo_id)
    assert record.validation_status == "validated"
    assert report["can_train"] is False
    assert record.feature_compatibility
    assert record.scientific_validation_status == "NOT_VALIDATED"

    # Original still intact after validate
    assert original.read_bytes() == raw

    record2, proc = svc.process_tmi(rec.geo_id, resolution=0.0005)
    assert record2.derived_relpath == "working/derived/tmi_grid.tif"
    assert proc["raw_source_unmodified"] is True
    assert proc["geophysical_transforms_applied"] == []
    assert original.read_bytes() == raw

    tif = storage.dataset_dir(rec.geo_id) / "working" / "derived" / "tmi_grid.tif"
    assert tif.exists()
    with rasterio.open(tif) as ds:
        assert ds.count == 1
        assert ds.crs.to_string() in {"EPSG:4326", "OGC:CRS84"} or "4326" in ds.crs.to_string()

    with pytest.raises(Exception):
        svc.set_activation(rec.geo_id, activation_status="approved", acknowledged_warnings=[])
    # May fail on warnings first — acknowledge then expect TMI_NOT_APPROVABLE
    warn_names = [
        c["name"] for c in (report.get("checks") or []) if c.get("status") == "WARN"
    ]
    with pytest.raises(Exception) as exc2:
        svc.set_activation(
            rec.geo_id,
            activation_status="approved",
            acknowledged_warnings=warn_names,
        )
    assert getattr(exc2.value, "code", "") == "TMI_NOT_APPROVABLE"

    limited = svc.set_compatibility_decision(
        rec.geo_id, decision="accepted_with_limitations"
    )
    assert limited.processing_status == "accepted_with_limitations"
    assert limited.scientific_validation_status == "NOT_VALIDATED"


def test_zipcsv_preserves_original_zip(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="ZIPCSV TMI")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("survey/tmi.csv", (FIXTURES / "tmi_client_xy_z.csv").read_bytes())
    zip_bytes = buf.getvalue()
    svc.upload_csv(rec.geo_id, filename="survey.zip", content=zip_bytes)
    stored = storage.get(rec.geo_id)
    assert storage.original_path(stored).read_bytes() == zip_bytes
    working = storage.working_path(stored)
    assert working is not None
    assert working.read_bytes().startswith(b"X,Y,Z")


def test_failed_validation_blocks_process(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="Bad TMI")
    csv = b"X,Y,Z\n999,999,1\n1000,999,2\n999,1000,3\n1000,1000,4\n"
    svc.upload_csv(rec.geo_id, filename="bad.csv", content=csv)
    svc.declare(
        rec.geo_id,
        {
            "measurement_type": "total_magnetic_intensity",
            "crs": "EPSG:4326",
            "units": "nT",
        },
    )
    record, report = svc.validate(rec.geo_id)
    assert report["overall"] == "FAIL"
    assert record.validation_status == "failed"
    with pytest.raises(Exception) as exc:
        svc.process_tmi(rec.geo_id, resolution=0.1)
    assert getattr(exc.value, "code", "") in {
        "PROCESS_REQUIRES_VALIDATED",
        "PROCESS_BLOCKED",
    }
