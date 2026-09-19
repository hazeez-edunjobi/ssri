"""Unit tests for SSRI catalog ingestion (no fabricated science metrics)."""

from __future__ import annotations

import csv
from pathlib import Path

from ssri_model.ingestion.schema import DomainRole, HazardLabelSet, PrdHazard
from ssri_model.ingestion.usgs_landslide import (
    convert_usgs_csv_row,
    ingest_usgs_csv,
    write_catalog_jsonl,
)
from ssri_model.ingestion.registry import DATASET_REGISTRY


def test_prd_hazards_are_landslide_subsidence_liquefaction() -> None:
    assert {h.value for h in PrdHazard} == {
        "landslide",
        "subsidence",
        "liquefaction",
    }


def test_missing_labels_stay_none() -> None:
    labels = HazardLabelSet(landslide=1)
    assert labels.landslide == 1
    assert labels.subsidence is None
    assert labels.liquefaction is None
    assert labels.available_tasks() == ("landslide",)


def test_convert_usgs_row_sets_landslide_only(tmp_path: Path) -> None:
    row = {
        "USGS_ID": "TEST-001",
        "Lat_N": "37.7749",
        "Lon_W": "-122.4194",
        "Confidence": "8",
        "LS_Type": "slide",
        "Inventory": "unit-test",
        "Inv_URL": "https://example.invalid",
        "Date_Min": "2000-01-01",
    }
    sample = convert_usgs_csv_row(row)
    assert sample is not None
    assert sample.domain_role == DomainRole.SOURCE
    assert sample.hazard_type == "landslide"
    assert sample.label == 1
    assert sample.labels.landslide == 1
    assert sample.labels.subsidence is None
    assert sample.labels.liquefaction is None
    assert sample.latitude == 37.7749
    assert sample.longitude == -122.4194


def test_ingest_usgs_csv_and_jsonl(tmp_path: Path) -> None:
    csv_path = tmp_path / "points.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["USGS_ID", "Lat_N", "Lon_W", "Confidence", "Inventory"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "USGS_ID": "A",
                "Lat_N": "6.5",
                "Lon_W": "3.4",
                "Confidence": "5",
                "Inventory": "demo",
            }
        )
        writer.writerow(
            {
                "USGS_ID": "B",
                "Lat_N": "bad",
                "Lon_W": "3.4",
                "Confidence": "5",
                "Inventory": "demo",
            }
        )
    samples = ingest_usgs_csv(csv_path)
    assert len(samples) == 1
    out = write_catalog_jsonl(samples, tmp_path / "catalog.jsonl")
    assert out.is_file()
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_registry_documents_bgs_iffi_blockers() -> None:
    by_id = {entry.dataset_id: entry for entry in DATASET_REGISTRY}
    assert by_id["bgs_mass_movement_uk"].status == "BLOCKED"
    assert by_id["iffi_italian_landslide_inventory"].status == "BLOCKED"
    assert by_id["usgs_landslide_inventories_us_v3"].status == "INGESTED"
