"""Ingest NASA COOLR / Global Landslide Catalog points for African target eval.

Queries the public ArcGIS FeatureServer and writes an SSRI catalog.jsonl with
``domain_role=target``. Does not fabricate labels: inventory points →
``landslide=1``; other PRD tasks remain missing.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ssri_model.ingestion.schema import (
    CatalogSample,
    DomainRole,
    HazardLabelSet,
    PrdHazard,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUT = REPO_ROOT / "data" / "catalogs" / "nasa_coolr_africa"

# Public NASA Earthdata COOLR events points service.
COOLR_QUERY_URL = (
    "https://gis.earthdata.nasa.gov/gis05/rest/services/Landslides/"
    "COOLR_Events_Points/FeatureServer/0/query"
)

# Approximate continental Africa + Madagascar bbox (WGS84).
AFRICA_BBOX = (-20.0, -35.0, 55.0, 38.0)


def _fetch_page(*, offset: int, page_size: int, bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    west, south, east, north = bbox
    params = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "geometryType": "esriGeometryEnvelope",
        "geometry": f"{west},{south},{east},{north}",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outSR": "4326",
        "f": "geojson",
        "resultOffset": str(offset),
        "resultRecordCount": str(page_size),
        "orderByFields": "OBJECTID ASC",
    }
    url = f"{COOLR_QUERY_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "SSRI-research/1.0"})
    with urlopen(req, timeout=120) as resp:  # noqa: S310 — fixed NASA HTTPS endpoint
        return json.loads(resp.read().decode("utf-8"))


def feature_to_sample(feature: dict[str, Any]) -> CatalogSample | None:
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates")
    props = feature.get("properties") or {}
    if not (isinstance(coords, list) and len(coords) >= 2):
        # Some services put x/y in properties.
        try:
            lon = float(props.get("longitude") or props.get("Longitude") or "")
            lat = float(props.get("latitude") or props.get("Latitude") or "")
        except ValueError:
            return None
    else:
        lon, lat = float(coords[0]), float(coords[1])

    west, south, east, north = AFRICA_BBOX
    if not (south <= lat <= north and west <= lon <= east):
        return None

    event_id = (
        props.get("event_id")
        or props.get("ev_id")
        or props.get("OBJECTID")
        or props.get("objectid")
        or f"{lat:.5f}_{lon:.5f}"
    )
    return CatalogSample(
        sample_id=f"coolr-{event_id}",
        latitude=lat,
        longitude=lon,
        dataset_name="nasa_coolr_events",
        dataset_version="feature_server_live",
        source_domain="nasa_coolr",
        domain_role=DomainRole.TARGET,
        hazard_type=PrdHazard.LANDSLIDE.value,
        label=1,
        labels=HazardLabelSet(landslide=1, subsidence=None, liquefaction=None),
        timestamp=str(props.get("event_date") or props.get("ev_date") or "") or None,
        target_domain="africa",
        quality_flags=[
            f"country={props.get('country_name') or props.get('country') or 'unknown'}",
            "inventory_presence=true",
        ],
        provenance={
            "provider": "NASA GSFC COOLR",
            "service": COOLR_QUERY_URL,
            "raw_properties_keys": sorted(str(k) for k in props.keys())[:40],
        },
    )


def ingest_coolr_africa(
    output_dir: Path,
    *,
    page_size: int = 1000,
    max_records: int = 20000,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = output_dir / "catalog.jsonl"
    samples: list[CatalogSample] = []
    offset = 0
    while offset < max_records:
        payload = _fetch_page(offset=offset, page_size=page_size, bbox=AFRICA_BBOX)
        features = payload.get("features") or []
        if not features:
            break
        for feature in features:
            sample = feature_to_sample(feature)
            if sample is not None:
                samples.append(sample)
        offset += len(features)
        logger.info("Fetched offset=%s page=%s total_kept=%s", offset, len(features), len(samples))
        if len(features) < page_size:
            break
        if payload.get("exceededTransferLimit") is False and len(features) < page_size:
            break

    # Deduplicate by sample_id
    unique: dict[str, CatalogSample] = {s.sample_id: s for s in samples}
    samples = list(unique.values())

    with catalog_path.open("w", encoding="utf-8") as handle:
        for sample in samples:
            handle.write(json.dumps(sample.to_dict()) + "\n")

    manifest = {
        "dataset_name": "nasa_coolr_africa",
        "dataset_version": "feature_server_live",
        "provider": "NASA GSFC COOLR",
        "url": COOLR_QUERY_URL,
        "license": "CHECK_PROVIDER_TERMS — cite Kirschbaum et al. / Juang et al.",
        "domain_role": "target",
        "geographic_extent": {
            "name": "continental_africa_approx",
            "bbox_wgs84": list(AFRICA_BBOX),
        },
        "hazard_type": "landslide",
        "sample_count": len(samples),
        "label_semantics": {
            "landslide": "1 = COOLR inventory presence",
            "subsidence": "missing",
            "liquefaction": "missing",
        },
        "status": "INGESTED" if samples else "EMPTY",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "African subset filtered by approximate continental bbox.",
            "Presence-only catalog; absences not included at ingest.",
            "Direct-transfer evaluation still requires FeatureStacks + absences.",
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    logger.info("Wrote %s samples to %s", len(samples), catalog_path)
    return catalog_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-records", type=int, default=20000)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    ingest_coolr_africa(
        args.output_dir, page_size=args.page_size, max_records=args.max_records
    )


if __name__ == "__main__":
    main()
