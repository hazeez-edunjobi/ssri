"""Download helpers for PRD source inventories (USGS first).

Network access may fail in restricted environments. Callers must treat a failed
download as a documented blocker — never fabricate inventory rows.
"""

from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from ssri_model.ingestion.usgs_landslide import (
    USGS_CSV_ZIP_NAME,
    USGS_LANDING_PAGE,
    USGS_SCIENCEBASE_ITEM,
)

logger = logging.getLogger(__name__)

SCIENCEBASE_ITEM_JSON = (
    f"https://www.sciencebase.gov/catalog/item/{USGS_SCIENCEBASE_ITEM}?format=json"
)


class DatasetDownloadError(RuntimeError):
    """Raised when a legitimate remote dataset cannot be fetched."""


def fetch_sciencebase_item_json(timeout: float = 60.0) -> dict[str, Any]:
    """Fetch ScienceBase item metadata JSON."""
    request = Request(
        SCIENCEBASE_ITEM_JSON,
        headers={"User-Agent": "ssri-model/0.1 (research; dataset-ingest)"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 — fixed USGS URL
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise DatasetDownloadError(
            f"Failed to reach ScienceBase item metadata ({SCIENCEBASE_ITEM_JSON}): {exc}. "
            f"Manual download: {USGS_LANDING_PAGE} → {USGS_CSV_ZIP_NAME}"
        ) from exc


def resolve_usgs_csv_zip_url(item: dict[str, Any] | None = None) -> str:
    """Return the download URL for ``US_Landslide_v3_csv.zip``."""
    meta = item or fetch_sciencebase_item_json()
    for entry in meta.get("files") or []:
        name = entry.get("name") or ""
        if name == USGS_CSV_ZIP_NAME:
            url = entry.get("url") or entry.get("downloadUri")
            if url:
                return str(url)
    raise DatasetDownloadError(
        f"{USGS_CSV_ZIP_NAME} not listed on ScienceBase item {USGS_SCIENCEBASE_ITEM}. "
        f"Open {USGS_LANDING_PAGE} and download manually."
    )


def download_file(url: str, destination: Path, *, timeout: float = 600.0) -> Path:
    """Download ``url`` to ``destination``."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(
        url,
        headers={"User-Agent": "ssri-model/0.1 (research; dataset-ingest)"},
    )
    try:
        with urlopen(request, timeout=timeout) as response, destination.open("wb") as out:  # noqa: S310
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    except URLError as exc:
        raise DatasetDownloadError(f"Download failed for {url}: {exc}") from exc
    return destination


def extract_zip(zip_path: Path, destination_dir: Path) -> list[Path]:
    """Extract a zip archive; return extracted file paths."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(destination_dir)
        for name in archive.namelist():
            extracted.append(destination_dir / name)
    return extracted


def download_usgs_landslide_csv_bundle(
    output_dir: Path | str,
    *,
    timeout: float = 600.0,
) -> Path:
    """Download and extract the USGS v3 CSV bundle under ``output_dir``.

    Returns the directory containing extracted CSV files.
    """
    root = Path(output_dir)
    raw_dir = root / "raw"
    extract_dir = root / "extracted"
    zip_path = raw_dir / USGS_CSV_ZIP_NAME
    url = resolve_usgs_csv_zip_url()
    logger.info("Downloading USGS landslide CSV bundle from ScienceBase")
    download_file(url, zip_path, timeout=timeout)
    extract_zip(zip_path, extract_dir)
    return extract_dir
