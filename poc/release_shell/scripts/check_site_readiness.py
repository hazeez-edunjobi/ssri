"""Owner-facing readiness check for a folder of client files.

Reports, in plain language, which of the five owner inputs are present:

  1. CRS (coordinate reference system)
  2. Layer meaning / units
  3. Labels for each hazard (subsidence, landslide, sinkhole)
  4. Lineament vectors
  5. Enough tiles / blocks for a spatial split

This script NEVER trains and NEVER invents data. It only inspects file names,
CSV headers, small text previews, and (optionally, if rasterio is installed)
GeoTIFF metadata. Anything it cannot confirm is reported as "can't tell" rather
than guessed.

Usage:
    python check_site_readiness.py <folder> [--block-size-km N] [--json out.json]

LOCAL ONLY. Read-only: it does not write anywhere unless --json is given.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from pathlib import Path

HAZARDS = ("subsidence", "landslide", "sinkhole")
VECTOR_EXTS = {".geojson", ".shp", ".gpkg", ".kml"}
RASTER_EXTS = {".tif", ".tiff", ".img"}
TABLE_EXTS = {".csv", ".tsv"}
M_PER_DEG_LAT = 111_320.0

PRESENT, MISSING, UNKNOWN = "PRESENT", "MISSING", "CAN'T TELL"


def _default_minimums() -> dict:
    return {
        "tiles": int(os.getenv("SSRI_RELEASE_SHELL_MIN_TILES", "300")),
        "blocks": int(os.getenv("SSRI_RELEASE_SHELL_MIN_BLOCKS", "8")),
        "held_out_blocks": int(os.getenv("SSRI_RELEASE_SHELL_MIN_HELD_OUT", "3")),
        "buffer_km": float(os.getenv("SSRI_RELEASE_SHELL_BUFFER_KM", "50")),
    }


def _list_files(folder: Path) -> list[Path]:
    return [p for p in folder.rglob("*") if p.is_file()]


def _preview(path: Path, limit: int = 8192) -> str:
    try:
        with path.open("rb") as fh:
            raw = fh.read(limit)
    except OSError:
        return ""
    return raw.decode("utf-8", errors="ignore").lower()


def _csv_header(path: Path) -> list[str]:
    try:
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as fh:
            reader = csv.reader(fh)
            for _ in range(5):
                row = next(reader, None)
                if row and any(cell.strip() for cell in row):
                    return [c.strip().lower() for c in row]
    except OSError:
        pass
    return []


def detect_crs(files: list[Path]) -> tuple[str, list[str]]:
    evidence: list[str] = []
    for p in files:
        suffix = p.suffix.lower()
        name = p.name.lower()
        if suffix == ".prj":
            evidence.append(f"{p.name}: projection sidecar file")
            continue
        if "epsg" in name or "crs" in name:
            evidence.append(f"{p.name}: name mentions a CRS/EPSG")
            continue
        if suffix == ".json":
            text = _preview(p)
            if '"crs"' in text or "epsg" in text:
                evidence.append(f"{p.name}: declares a CRS in JSON")
                continue
        if suffix in TABLE_EXTS:
            header = _csv_header(p)
            if any(("crs" in h) or ("epsg" in h) for h in header):
                evidence.append(f"{p.name}: CSV has a CRS/EPSG column")
                continue
        if suffix in RASTER_EXTS:
            try:
                import rasterio  # type: ignore

                with rasterio.open(p) as ds:
                    if ds.crs:
                        evidence.append(f"{p.name}: GeoTIFF CRS = {ds.crs}")
                        continue
            except Exception:  # noqa: BLE001
                pass
    if evidence:
        return PRESENT, evidence[:6]
    return MISSING, []


def detect_layers(files: list[Path]) -> tuple[str, list[str]]:
    evidence: list[str] = []
    layer_words = ("layer", "channel", "band", "variable", "unit", "legend")
    for p in files:
        lower = p.name.lower()
        if p.suffix.lower() in {".json", ".csv", ".md", ".txt", ".yaml", ".yml"} and any(
            w in lower for w in layer_words
        ):
            evidence.append(f"{p.name}: looks like a layer/legend description")
            continue
        if p.suffix.lower() == ".json":
            text = _preview(p)
            if '"channels"' in text or '"layers"' in text or '"units"' in text:
                evidence.append(f"{p.name}: JSON lists channels/layers/units")
    if evidence:
        return PRESENT, evidence[:6]
    return MISSING, []


def detect_labels(files: list[Path]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {h: [] for h in HAZARDS}
    for p in files:
        stem = p.stem.lower()
        parent = p.parent.name.lower()
        for h in HAZARDS:
            if h in stem or h in parent:
                found[h].append(p.name)
    return found


def detect_lineaments(files: list[Path]) -> tuple[str, list[str]]:
    evidence: list[str] = []
    for p in files:
        lower = p.name.lower()
        if "lineament" in lower:
            evidence.append(f"{p.name}: name mentions lineaments")
            continue
        if p.suffix.lower() == ".geojson":
            if "lineament" in _preview(p):
                evidence.append(f"{p.name}: GeoJSON references lineaments")
    if evidence:
        return PRESENT, evidence[:6]
    return MISSING, []


def _block_id(lat: float, lon: float, size_deg: float) -> str:
    lat_b = math.floor(lat / size_deg) * size_deg
    lon_b = math.floor(lon / size_deg) * size_deg
    return f"{round(lat_b, 6)}_{round(lon_b, 6)}"


def detect_tiles_blocks(
    files: list[Path], block_size_km: float | None
) -> tuple[str, dict]:
    """Count tiles and distinct blocks from a manifest and/or a points CSV."""
    info: dict = {"tiles": None, "blocks": None, "block_size_km": block_size_km}
    size_deg = (
        (block_size_km * 1000.0 / M_PER_DEG_LAT)
        if block_size_km
        else 5.0
    )
    info["block_size_deg"] = round(size_deg, 6)

    # 1) manifest splits (tile counts)
    for p in files:
        if p.name.lower() == "manifest.json":
            try:
                man = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            splits = man.get("splits") or {}
            if isinstance(splits, dict):
                counts = [
                    len(v) for v in splits.values() if isinstance(v, (list, tuple))
                ]
                if counts:
                    info["tiles"] = int(sum(counts))
                    info["manifest"] = p.name
            break

    # 2) points/tiles CSV with lat/lon columns → distinct blocks
    coords = []
    lat_names = {"lat", "latitude", "y", "centroid_lat"}
    lon_names = {"lon", "lng", "longitude", "x", "centroid_lon"}
    for p in files:
        if p.suffix.lower() not in TABLE_EXTS:
            continue
        header = _csv_header(p)
        if not header:
            continue
        lat_c = next((h for h in header if h in lat_names), None)
        lon_c = next((h for h in header if h in lon_names), None)
        if not (lat_c and lon_c):
            continue
        try:
            with p.open("r", encoding="utf-8", errors="ignore", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    try:
                        lat = float(row[lat_c])
                        lon = float(row[lon_c])
                    except (TypeError, ValueError, KeyError):
                        continue
                    coords.append((lat, lon))
        except OSError:
            continue
        if coords:
            info.setdefault("points_csv", p.name)
            break

    if coords:
        info["tiles"] = max(info["tiles"] or 0, len(coords))
        info["blocks"] = len({_block_id(la, lo, size_deg) for la, lo in coords})

    if info["tiles"] is None:
        return UNKNOWN, info
    return PRESENT, info


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--block-size-km", type=float, default=None)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)

    folder: Path = args.folder
    if not folder.is_dir():
        print(f"ERROR: not a folder: {folder}")
        return 2

    files = _list_files(folder)
    minimums = _default_minimums()

    crs_status, crs_ev = detect_crs(files)
    layer_status, layer_ev = detect_layers(files)
    labels = detect_labels(files)
    line_status, line_ev = detect_lineaments(files)
    tile_status, tile_info = detect_tiles_blocks(files, args.block_size_km)

    print(f"SSRI site readiness check — {folder}")
    print("Read-only. No training. Nothing is guessed: unclear = \"CAN'T TELL\".")
    print(f"Scanned {len(files)} file(s).\n")

    def line(step: str, status: str, detail: str = "") -> None:
        print(f"[{step}] {status}")
        if detail:
            print(f"      {detail}")

    line("1/5 CRS (coordinate reference system)", crs_status, "; ".join(crs_ev))
    line("2/5 Layer meaning and units", layer_status, "; ".join(layer_ev))

    missing_hazards = [h for h in HAZARDS if not labels[h]]
    if not missing_hazards:
        line("3/5 Labels for each hazard", PRESENT, "found subsidence, landslide, sinkhole")
    elif len(missing_hazards) == len(HAZARDS):
        line("3/5 Labels for each hazard", MISSING, "no hazard label files found")
    else:
        line(
            "3/5 Labels for each hazard",
            "PARTIAL",
            "found: " + ", ".join(h for h in HAZARDS if labels[h])
            + " | missing: " + ", ".join(missing_hazards),
        )

    line("4/5 Lineament vectors", line_status, "; ".join(line_ev))

    if tile_status == PRESENT:
        tiles = tile_info.get("tiles")
        blocks = tile_info.get("blocks")
        detail = f"tiles≈{tiles}"
        if blocks is not None:
            detail += (
                f", distinct blocks≈{blocks} at {tile_info['block_size_km'] or '5.0'} km"
                if tile_info.get("block_size_km")
                else f", distinct blocks≈{blocks} at 5.0° default"
            )
        warnings = []
        if tiles is not None and tiles < minimums["tiles"]:
            warnings.append(f"below {minimums['tiles']} minimum tiles")
        if blocks is not None and blocks < minimums["blocks"]:
            warnings.append(f"below {minimums['blocks']} minimum blocks")
        status = PRESENT if not warnings else "PARTIAL"
        line("5/5 Enough tiles / blocks", status, detail + (" | " + "; ".join(warnings) if warnings else ""))
    else:
        line(
            "5/5 Enough tiles / blocks",
            UNKNOWN,
            "no manifest splits or lat/lon CSV found — cannot count tiles/blocks",
        )

    print("\nMinimums in force (from defaults unless overridden):")
    print(
        f"  tiles >= {minimums['tiles']}, blocks >= {minimums['blocks']}, "
        f"held-out blocks >= {minimums['held_out_blocks']}, buffer = {minimums['buffer_km']} km"
    )

    next_steps: list[str] = []
    if crs_status != PRESENT:
        next_steps.append("Ask the client for the CRS (EPSG code or full definition).")
    if layer_status != PRESENT:
        next_steps.append("Ask which layer is which and its units (e.g. metres).")
    if missing_hazards:
        next_steps.append(
            "Ask for label locations per hazard: " + ", ".join(missing_hazards) + "."
        )
    if line_status != PRESENT:
        next_steps.append("Ask for lineament vectors (optional but useful).")
    if tile_status != PRESENT:
        next_steps.append("Ask for per-tile coordinates so we can count blocks.")

    if next_steps:
        print("\nWhat to ask the client:")
        for s in next_steps:
            print(f"  - {s}")
    else:
        print("\nAll five inputs look present. Next: declare CRS per layer, then validate.")

    if args.json:
        report = {
            "folder": str(folder),
            "files_scanned": len(files),
            "crs": {"status": crs_status, "evidence": crs_ev},
            "layers": {"status": layer_status, "evidence": layer_ev},
            "labels": {h: labels[h] for h in HAZARDS},
            "lineaments": {"status": line_status, "evidence": line_ev},
            "tiles_blocks": {"status": tile_status, **tile_info},
            "minimums": minimums,
            "next_steps": next_steps,
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json}")

    # Exit 0 always: this is an advisory report, not a gate.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
