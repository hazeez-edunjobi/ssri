"""USGS National Landslide Inventory (v3) → SSRI catalog samples.

Dataset
-------
- Name: Landslide Inventories across the United States (ver. 3.0, February 2025)
- DOI: https://doi.org/10.5066/P14AJF8I
- ScienceBase: https://www.sciencebase.gov/catalog/item/671eef1fd34ed0f827ea9f12
- License: CC0 1.0 (public domain dedication)
- Preferred download: ``US_Landslide_v3_csv.zip`` (~23 MB)

This module does **not** fabricate labels. It maps inventory points with valid
WGS84 coordinates to ``CatalogSample`` records with ``landslide=1`` and
``subsidence`` / ``liquefaction`` left as ``None`` (missing).
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Iterator

from ssri_model.ingestion.schema import (
    CatalogSample,
    DomainRole,
    HazardLabelSet,
    PrdHazard,
)

logger = logging.getLogger(__name__)

USGS_DATASET_NAME = "usgs_landslide_inventories_us"
USGS_DATASET_VERSION = "3.0"
USGS_DOI = "10.5066/P14AJF8I"
USGS_LICENSE = "CC0-1.0"
USGS_SCIENCEBASE_ITEM = "671eef1fd34ed0f827ea9f12"
USGS_LANDING_PAGE = (
    "https://www.sciencebase.gov/catalog/item/671eef1fd34ed0f827ea9f12"
)
USGS_CSV_ZIP_NAME = "US_Landslide_v3_csv.zip"


def convert_usgs_csv_row(
    row: dict[str, str],
    *,
    source_domain: str = "usgs_conus",
) -> CatalogSample | None:
    """Convert one USGS CSV row to a :class:`CatalogSample`, or ``None`` if unusable."""
    try:
        lat = float(row.get("Lat_N") or row.get("lat_n") or "")
        lon = float(row.get("Lon_W") or row.get("lon_w") or "")
    except ValueError:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None

    usgs_id = (row.get("USGS_ID") or row.get("usgs_id") or "").strip()
    if not usgs_id:
        usgs_id = f"usgs-{lat:.5f}-{lon:.5f}"

    confidence = (row.get("Confidence") or "").strip()
    quality_flags: list[str] = []
    if confidence:
        quality_flags.append(f"confidence={confidence}")
    ls_type = (row.get("LS_Type") or "").strip()
    if ls_type:
        quality_flags.append(f"ls_type={ls_type}")

    timestamp = (row.get("Date_Min") or row.get("Date_Max") or "").strip() or None

    return CatalogSample(
        sample_id=f"usgs-v3-{usgs_id}",
        latitude=lat,
        longitude=lon,
        dataset_name=USGS_DATASET_NAME,
        dataset_version=USGS_DATASET_VERSION,
        source_domain=source_domain,
        domain_role=DomainRole.SOURCE,
        hazard_type=PrdHazard.LANDSLIDE.value,
        label=1,
        labels=HazardLabelSet(landslide=1, subsidence=None, liquefaction=None),
        geometry_wkt=f"POINT ({lon} {lat})",
        timestamp=timestamp,
        feature_availability={},
        quality_flags=quality_flags,
        provenance={
            "doi": USGS_DOI,
            "license": USGS_LICENSE,
            "inventory": row.get("Inventory") or "",
            "inv_url": row.get("Inv_URL") or "",
            "sciencebase_item": USGS_SCIENCEBASE_ITEM,
        },
    )


def iter_usgs_csv(path: Path) -> Iterator[dict[str, str]]:
    """Yield dict rows from a USGS points/polygons CSV."""
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield {k: (v or "") for k, v in row.items()}


def ingest_usgs_csv(
    csv_path: Path | str,
    *,
    max_rows: int | None = None,
    min_confidence: int | None = None,
) -> list[CatalogSample]:
    """Ingest a USGS landslide CSV into canonical catalog samples."""
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"USGS CSV not found: {path}")

    samples: list[CatalogSample] = []
    for row in iter_usgs_csv(path):
        if min_confidence is not None:
            raw = (row.get("Confidence") or "").strip()
            try:
                conf = int(float(raw))
            except ValueError:
                continue
            if conf < min_confidence:
                continue
        sample = convert_usgs_csv_row(row)
        if sample is None:
            continue
        samples.append(sample)
        if max_rows is not None and len(samples) >= max_rows:
            break
    logger.info("Ingested %d USGS landslide samples from %s", len(samples), path)
    return samples


def write_catalog_jsonl(samples: list[CatalogSample], output_path: Path | str) -> Path:
    """Write catalog samples as JSON Lines."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for sample in samples:
            handle.write(json.dumps(sample.to_dict(), ensure_ascii=True) + "\n")
    return path


def catalog_manifest(
    samples: list[CatalogSample],
    *,
    status: str,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    """Build a machine-readable ingest manifest (no fabricated metrics)."""
    return {
        "dataset_name": USGS_DATASET_NAME,
        "dataset_version": USGS_DATASET_VERSION,
        "doi": USGS_DOI,
        "license": USGS_LICENSE,
        "landing_page": USGS_LANDING_PAGE,
        "hazard_type": PrdHazard.LANDSLIDE.value,
        "domain_role": DomainRole.SOURCE.value,
        "sample_count": len(samples),
        "label_semantics": {
            "landslide": "1 = inventory presence; 0 unused in raw inventory ingest",
            "subsidence": "missing (None) — USGS landslide inventory does not annotate subsidence",
            "liquefaction": "missing (None) — USGS landslide inventory does not annotate liquefaction",
        },
        "status": status,
        "notes": notes or [],
    }
