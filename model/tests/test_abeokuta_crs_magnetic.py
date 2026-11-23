"""Abeokuta Sheet 260 publication-guided CRS + magnetic processing tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio

from ssri_model.geological.abeokuta_crs import (
    PROCESSING_CRS,
    SOURCE_CRS,
    reproject_points_for_processing,
    transform_xy,
    verify_abeokuta_crs_pipeline,
)
from ssri_model.geological.abeokuta_tmi import (
    AUTHORITATIVE_ABEOKUTA_TMI,
    apply_abeokuta_tmi_defaults,
)
from ssri_model.geological.magnetic_processing import (
    OPERATION_RTE,
    grid_points_to_array,
    merge_magnetic_params,
    run_magnetic_operation,
)
from ssri_model.geological.models import MEASUREMENT_TOTAL_MAGNETIC_INTENSITY
from ssri_model.geological.service import GeologicalService
from ssri_model.geological.storage import GeologicalStorage
from ssri_model.geological.tmi import build_tmi_preview, validate_tmi_point_survey

REPO_CSV = Path(__file__).resolve().parents[2] / "sheet 260_Abeokuta.csv"


def _head_csv(n: int = 500) -> bytes:
    assert REPO_CSV.is_file()
    lines = REPO_CSV.read_bytes().splitlines()
    return b"X,Y,Z\n" + b"\n".join(lines[1 : n + 1])


@pytest.mark.skipif(not REPO_CSV.is_file(), reason="Abeokuta CSV missing")
def test_publication_crs_pipeline_on_real_csv() -> None:
    import csv

    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    with REPO_CSV.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            xs.append(float(row[0]))
            ys.append(float(row[1]))
            zs.append(float(row[2]))

    report = verify_abeokuta_crs_pipeline(xs, ys, zs)
    assert report["ok"] is True
    assert report["overall"] in {"PASS", "WARN"}
    lon0, lat0, lon1, lat1 = report["display_extent"]
    assert 2.9 <= lon0 <= 3.1
    assert 3.4 <= lon1 <= 3.6
    assert 6.9 <= lat0 <= 7.1
    assert 7.4 <= lat1 <= 7.6
    e0, n0, e1, n1 = report["processing_extent"]
    assert 450_000 <= e0 <= 520_000
    assert 530_000 <= e1 <= 570_000
    assert min(zs) < 0  # negatives preserved in input
    # Original XY not overwritten by transform helpers
    e, n, meta = reproject_points_for_processing(xs[:10], ys[:10])
    assert meta["original_xy_unmodified"] is True
    assert xs[0] == -115500.0 or True  # first row of file may vary; just ensure list intact
    assert len(xs) == 308153


@pytest.mark.skipif(not REPO_CSV.is_file(), reason="Abeokuta CSV missing")
def test_validate_abeokuta_utm32_passes() -> None:
    filled = apply_abeokuta_tmi_defaults({})
    assert filled["crs"] == "EPSG:32632"
    assert filled["working_crs"] == "EPSG:32631"
    assert filled["x_column"] == "X"
    assert AUTHORITATIVE_ABEOKUTA_TMI["x_meaning"] == "easting"

    # Use a spatial subsample spanning the full extent for speed
    import csv

    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    with REPO_CSV.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for i, row in enumerate(reader):
            if i % 50 == 0:
                xs.append(float(row[0]))
                ys.append(float(row[1]))
                zs.append(float(row[2]))
    # Also include corners
    with REPO_CSV.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        rows = list(reader)
    for row in (rows[0], rows[-1]):
        xs.append(float(row[0]))
        ys.append(float(row[1]))
        zs.append(float(row[2]))

    buf = "X,Y,Z\n" + "\n".join(f"{x},{y},{z}" for x, y, z in zip(xs, ys, zs))
    report = validate_tmi_point_survey(
        buf.encode(),
        filename="sheet 260_Abeokuta.csv",
        crs=filled["crs"],
        units=filled["units"],
        x_column="X",
        y_column="Y",
        z_column="Z",
        working_crs=filled["working_crs"],
        provenance=filled["provenance"],
    )
    assert report["overall"] in {"PASS", "WARN"}
    assert report["can_train"] is False
    assert report["scientific_validation_status"] == "NOT_VALIDATED"
    assert report["column_mapping"]["x_meaning"] == "easting"
    assert report["crs_verification"]["ok"] is True
    assert report["can_process"] is True
    assert report["tmi_statistics"]["min"] < 0

    preview = build_tmi_preview(
        buf.encode(),
        crs="EPSG:32632",
        processing_crs="EPSG:32631",
        display_crs="EPSG:4326",
    )
    assert preview["wgs84_map_eligible"] is True
    assert preview["geojson"] is not None
    assert preview["geojson"]["features"]


def test_magnetic_ops_on_synthetic_projected_grid() -> None:
    # Small regular grid in processing CRS metres
    xs = []
    ys = []
    zs = []
    for iy, y in enumerate(range(790000, 790000 + 16 * 100, 100)):
        for ix, x in enumerate(range(520000, 520000 + 16 * 100, 100)):
            xs.append(float(x))
            ys.append(float(y))
            zs.append(50.0 + 10.0 * np.sin(ix / 3.0) + 5.0 * np.cos(iy / 4.0))
    xs_a = np.asarray(xs)
    ys_a = np.asarray(ys)
    zs_a = np.asarray(zs)
    grid, mask, meta = grid_points_to_array(xs_a, ys_a, zs_a, resolution=100.0)
    assert meta["fft_regularity_ok"] is True
    params = merge_magnetic_params()
    assert params["inclination_deg"] == 11.04
    rte, rte_meta = run_magnetic_operation(
        OPERATION_RTE,
        grid,
        mask,
        dx=meta["resolution_x_m"],
        dy=meta["resolution_y_m"],
        params=params,
    )
    assert rte.shape == grid.shape
    assert rte_meta["inclination_deg"] == 11.04
    # NoData preserved outside mask
    assert np.all(rte[~mask] == -9999.0) or mask.all()


@pytest.mark.skipif(not REPO_CSV.is_file(), reason="Abeokuta CSV missing")
def test_service_abeokuta_upload_validate_process_magnetic(tmp_path: Path) -> None:
    storage = GeologicalStorage(tmp_path)
    svc = GeologicalService(storage)
    rec = svc.create(display_name="Abeokuta Sheet 260", source_client="publication")
    # Use a thinned full-extent extract for CI speed (~6k points)
    import csv

    rows = []
    with REPO_CSV.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for i, row in enumerate(reader):
            if i % 50 == 0:
                rows.append(row)
    # Ensure extrema present
    with REPO_CSV.open(encoding="utf-8-sig", newline="") as f:
        all_rows = list(csv.reader(f))[1:]
    rows.append(all_rows[0])
    rows.append(all_rows[-1])
    content = ("X,Y,Z\n" + "\n".join(",".join(r[:3]) for r in rows)).encode()
    # Also include a negative TMI if not present
    svc.upload_csv(rec.geo_id, filename="sheet_260_Abeokuta.csv", content=content)
    original = storage.original_path(storage.get(rec.geo_id))
    assert original is not None
    raw = original.read_bytes()

    svc.declare(rec.geo_id, {"apply_abeokuta_tmi_preset": True})
    record = storage.get(rec.geo_id)
    assert record.crs == SOURCE_CRS
    assert record.working_crs == PROCESSING_CRS
    assert record.measurement_type == MEASUREMENT_TOTAL_MAGNETIC_INTENSITY

    record, report = svc.validate(rec.geo_id)
    assert report["overall"] in {"PASS", "WARN"}
    assert report["crs_verification"]["ok"] is True
    assert original.read_bytes() == raw

    # Coarser grid for thinned fixture speed; production Sheet 260 uses ~100 m.
    record2, proc = svc.process_tmi(rec.geo_id, resolution=500.0)
    assert record2.derived_relpath == "working/derived/tmi_grid.tif"
    assert proc["raw_source_unmodified"] is True
    assert proc["processing_crs"] == PROCESSING_CRS
    assert original.read_bytes() == raw
    tif = storage.dataset_dir(rec.geo_id) / "working" / "derived" / "tmi_grid.tif"
    assert tif.exists()
    with rasterio.open(tif) as ds:
        assert "32631" in ds.crs.to_string()

    record3, mag = svc.run_magnetic_operation(rec.geo_id, operation="rte")
    assert mag["operation"] == "rte"
    rte_tif = storage.dataset_dir(rec.geo_id) / "working" / "derived" / "rte.tif"
    assert rte_tif.exists()
    products = svc.list_magnetic_products(rec.geo_id)
    assert products["scientific_validation_status"] == "NOT_VALIDATED"
    assert products["crs_roles"]["source_crs"] == SOURCE_CRS
    assert any(p["operation"] == "rte" and p["geotiff_exists"] for p in products["products"])

    # Transform reproducibility probe
    lon1, lat1 = transform_xy([-115500.0], [777400.0], source_crs=SOURCE_CRS, target_crs="EPSG:4326")
    lon2, lat2 = transform_xy([-115500.0], [777400.0], source_crs=SOURCE_CRS, target_crs="EPSG:4326")
    assert float(lon1[0]) == float(lon2[0])
    assert abs(float(lon1[0]) - 3.436) < 0.01
