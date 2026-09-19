"""Ingest UGLC point records for African / Nigerian target evaluation.

Downloads the Zenodo UGLC point CSV when possible, filters Africa/Nigeria,
and writes an SSRI catalog with ``domain_role=target``.

Does not fabricate labels. Inventory points → ``landslide=1``; other PRD tasks
remain missing. Does **not** assign TARGET-HELD-OUT vs TARGET-UNLABELED roles
beyond cataloguing — that split is applied later for DANN evaluation design.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from ssri_model.ingestion.schema import (
    CatalogSample,
    DomainRole,
    HazardLabelSet,
    PrdHazard,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUT = REPO_ROOT / "data" / "catalogs" / "uglc_africa"

# Zenodo record for UGLC (Mancino et al.) — try known DOI/record IDs.
ZENODO_RECORD_CANDIDATES = (
    "18643456",
    "16755044",
)

AFRICA_BBOX = (-20.0, -35.0, 55.0, 38.0)
NIGERIA_BBOX = (2.5, 4.0, 15.0, 14.0)


def _http_get(url: str, timeout: float = 180.0) -> bytes:
    req = Request(url, headers={"User-Agent": "SSRI-research/1.0"})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — fixed Zenodo/GitHub HTTPS
        return resp.read()


def discover_zenodo_csv_url(record_id: str) -> str | None:
    meta_url = f"https://zenodo.org/api/records/{record_id}"
    try:
        payload = json.loads(_http_get(meta_url).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Zenodo metadata failed for %s: %s", record_id, exc)
        return None
    files = payload.get("files") or []
    for f in files:
        key = str(f.get("key") or "")
        link = (f.get("links") or {}).get("self") or (f.get("links") or {}).get("download")
        if not link:
            continue
        lower = key.lower()
        if lower.endswith(".csv") and ("point" in lower or "uglc" in lower):
            return str(link)
    # Prefer any csv
    for f in files:
        key = str(f.get("key") or "")
        link = (f.get("links") or {}).get("self") or (f.get("links") or {}).get("download")
        if link and key.lower().endswith(".csv"):
            return str(link)
    # Zip containing csv
    for f in files:
        key = str(f.get("key") or "")
        link = (f.get("links") or {}).get("self") or (f.get("links") or {}).get("download")
        if link and key.lower().endswith(".zip"):
            return str(link)
    return None


def _parse_lat_lon(row: dict[str, str]) -> tuple[float, float] | None:
    candidates = [
        ("LAT", "LON"),
        ("lat", "lon"),
        ("Latitude", "Longitude"),
        ("latitude", "longitude"),
        ("Y", "X"),
        ("y", "x"),
    ]
    for lat_k, lon_k in candidates:
        if lat_k in row and lon_k in row:
            try:
                lat = float(str(row[lat_k]).strip())
                lon = float(str(row[lon_k]).strip())
            except ValueError:
                continue
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
    return None


def _country_name(row: dict[str, str]) -> str:
    for key in ("COUNTRY", "country", "Country", "COUNTRY_NAME", "ADM0_NAME"):
        if key in row and str(row[key]).strip():
            return str(row[key]).strip()
    return ""


def _in_bbox(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> bool:
    west, south, east, north = bbox
    return south <= lat <= north and west <= lon <= east


def row_to_sample(row: dict[str, str], *, region: str) -> CatalogSample | None:
    coords = _parse_lat_lon(row)
    if coords is None:
        return None
    lat, lon = coords
    country = _country_name(row)
    event_id = (
        row.get("UGLC_ID")
        or row.get("ID")
        or row.get("id")
        or row.get("OBJECTID")
        or f"{lat:.5f}_{lon:.5f}"
    )
    return CatalogSample(
        sample_id=f"uglc-{region}-{event_id}",
        latitude=lat,
        longitude=lon,
        dataset_name="uglc_point",
        dataset_version="zenodo",
        source_domain="uglc",
        domain_role=DomainRole.TARGET,
        hazard_type=PrdHazard.LANDSLIDE.value,
        label=1,
        labels=HazardLabelSet(landslide=1, subsidence=None, liquefaction=None),
        timestamp=(row.get("DATE") or row.get("date") or "") or None,
        target_domain=region,
        quality_flags=[
            f"country={country or 'unknown'}",
            "inventory_presence=true",
            "uglc_harmonized=true",
        ],
        provenance={
            "provider": "UGLC (Mancino et al.)",
            "zenodo": "https://doi.org/10.5281/zenodo.18643456",
            "license_note": "Open Zenodo deposit — confirm file-level license before redistribution",
            "columns_present": sorted(row.keys())[:40],
        },
    )


def load_csv_text_from_bytes(raw: bytes, source_name: str) -> str:
    if source_name.lower().endswith(".zip") or raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not names:
                raise RuntimeError("ZIP archive contained no CSV files")
            # Prefer point catalogue
            names_sorted = sorted(
                names,
                key=lambda n: (0 if "point" in n.lower() else 1, len(n)),
            )
            return zf.read(names_sorted[0]).decode("utf-8", errors="replace")
    return raw.decode("utf-8", errors="replace")


def ingest_uglc(
    output_dir: Path,
    *,
    local_csv: Path | None = None,
    africa_only: bool = True,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    if local_csv is not None:
        text = local_csv.read_text(encoding="utf-8", errors="replace")
        source_url = str(local_csv)
    else:
        source_url = None
        text = None
        for record_id in ZENODO_RECORD_CANDIDATES:
            url = discover_zenodo_csv_url(record_id)
            if not url:
                continue
            logger.info("Downloading UGLC from Zenodo record %s: %s", record_id, url)
            raw = _http_get(url)
            (raw_dir / f"zenodo_{record_id}_download.bin").write_bytes(raw)
            text = load_csv_text_from_bytes(raw, url)
            source_url = url
            break
        if text is None:
            raise RuntimeError(
                "Could not download UGLC from Zenodo. Place a local CSV and pass --local-csv."
            )

    # Detect delimiter
    sample = text[:4096]
    dialect = csv.Sniffer().sniff(sample, delimiters=",|;|\t")
    reader = csv.DictReader(io.StringIO(text), delimiter=dialect.delimiter)
    africa: list[CatalogSample] = []
    nigeria: list[CatalogSample] = []
    total = 0
    for row in reader:
        total += 1
        coords = _parse_lat_lon(row)
        if coords is None:
            continue
        lat, lon = coords
        country = _country_name(row).lower()
        if _in_bbox(lat, lon, NIGERIA_BBOX) or "nigeria" in country:
            sample_obj = row_to_sample(row, region="nigeria")
            if sample_obj:
                nigeria.append(sample_obj)
        if (not africa_only) or _in_bbox(lat, lon, AFRICA_BBOX) or any(
            tok in country
            for tok in (
                "nigeria",
                "kenya",
                "ethiopia",
                "uganda",
                "tanzania",
                "rwanda",
                "ghana",
                "cameroon",
                "congo",
                "south africa",
                "morocco",
                "algeria",
                "sudan",
                "malawi",
                "mozambique",
                "madagascar",
            )
        ):
            if _in_bbox(lat, lon, AFRICA_BBOX) or country:
                if _in_bbox(lat, lon, AFRICA_BBOX):
                    sample_obj = row_to_sample(row, region="africa")
                    if sample_obj:
                        africa.append(sample_obj)

    # Deduplicate
    africa_u = {s.sample_id: s for s in africa}
    nigeria_u = {s.sample_id: s for s in nigeria}

    africa_path = output_dir / "catalog_africa.jsonl"
    nigeria_path = output_dir / "catalog_nigeria.jsonl"
    with africa_path.open("w", encoding="utf-8") as handle:
        for s in africa_u.values():
            handle.write(json.dumps(s.to_dict()) + "\n")
    with nigeria_path.open("w", encoding="utf-8") as handle:
        for s in nigeria_u.values():
            handle.write(json.dumps(s.to_dict()) + "\n")

    # DANN role placeholders (no labels leaked into adaptation by default)
    roles = {
        "SOURCE": "USGS/BGS/IFFI labelled (source domain)",
        "TARGET_UNLABELED": (
            "African FeatureStacks for DANN adaptation — labels must not be used "
            "for training decisions"
        ),
        "TARGET_HELD_OUT": (
            "Independent labelled African/Nigerian samples reserved exclusively "
            "for final DIRECT TRANSFER vs DANN evaluation"
        ),
        "note": (
            "This ingest creates presence catalogs only. Held-out vs unlabeled "
            "partition must be created before DANN training and must not leak "
            "TARGET_HELD_OUT labels into hyperparameter tuning."
        ),
    }
    (output_dir / "dann_role_design.json").write_text(
        json.dumps(roles, indent=2),
        encoding="utf-8",
    )

    manifest = {
        "dataset_name": "uglc_africa",
        "provider": "UGLC / Zenodo",
        "source_url": source_url,
        "doi": "10.5281/zenodo.18643456",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rows_scanned": total,
        "africa_sample_count": len(africa_u),
        "nigeria_sample_count": len(nigeria_u),
        "domain_role": "target",
        "label_semantics": {
            "landslide": "1 = UGLC inventory presence",
            "subsidence": "missing",
            "liquefaction": "missing",
        },
        "status": "INGESTED" if africa_u or nigeria_u else "EMPTY",
        "usable_as": {
            "labelled_target_evaluation": True if nigeria_u or africa_u else False,
            "unlabelled_target_adaptation": True if nigeria_u or africa_u else False,
            "susceptibility_map_as_truth": False,
        },
        "catalog_africa": str(africa_path),
        "catalog_nigeria": str(nigeria_path),
        "notes": [
            "Presence-only; absences not included at ingest.",
            "Partition TARGET_UNLABELED vs TARGET_HELD_OUT before DANN.",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info(
        "UGLC ingest complete: africa=%s nigeria=%s",
        len(africa_u),
        len(nigeria_u),
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--local-csv", type=Path, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    ingest_uglc(args.output_dir, local_csv=args.local_csv)


if __name__ == "__main__":
    main()
