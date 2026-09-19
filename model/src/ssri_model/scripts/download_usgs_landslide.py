"""Download USGS landslide CSV bundle into data/catalogs/usgs_landslide_v3/.

Usage (from repo root, with network)::

    poetry run python -m ssri_model.scripts.download_usgs_landslide

If ScienceBase is unreachable, exits non-zero and prints the manual URL.
Does not fabricate inventory rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ssri_model.ingestion.download import (
    DatasetDownloadError,
    download_usgs_landslide_csv_bundle,
)
from ssri_model.ingestion.registry import registry_as_dicts
from ssri_model.ingestion.usgs_landslide import (
    USGS_LANDING_PAGE,
    catalog_manifest,
    ingest_usgs_csv,
    write_catalog_jsonl,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Default: <repo>/data/catalogs/usgs_landslide_v3",
    )
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--min-confidence", type=int, default=None)
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Only ingest an already-extracted CSV under output-dir/extracted",
    )
    args = parser.parse_args(argv)

    out = args.output_dir or (_repo_root() / "data" / "catalogs" / "usgs_landslide_v3")
    out.mkdir(parents=True, exist_ok=True)

    try:
        if not args.skip_download:
            extract_dir = download_usgs_landslide_csv_bundle(out)
        else:
            extract_dir = out / "extracted"
        csv_candidates = sorted(extract_dir.rglob("*.csv"))
        if not csv_candidates:
            raise DatasetDownloadError(
                f"No CSV files under {extract_dir}. "
                f"Download {USGS_LANDING_PAGE} manually."
            )
        # Prefer a points table if named distinctly; else first CSV.
        csv_path = next(
            (p for p in csv_candidates if "point" in p.name.lower()),
            csv_candidates[0],
        )
        samples = ingest_usgs_csv(
            csv_path,
            max_rows=args.max_rows,
            min_confidence=args.min_confidence,
        )
        catalog_path = out / "catalog.jsonl"
        write_catalog_jsonl(samples, catalog_path)
        manifest = catalog_manifest(
            samples,
            status="INGESTED" if samples else "EMPTY",
            notes=[f"source_csv={csv_path.name}"],
        )
        (out / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        (out / "dataset_registry_snapshot.json").write_text(
            json.dumps(registry_as_dicts(), indent=2) + "\n", encoding="utf-8"
        )
        print(f"OK samples={len(samples)} catalog={catalog_path}")
        return 0
    except DatasetDownloadError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        print(f"Manual: {USGS_LANDING_PAGE}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
