"""Independent lineament vector ingestion (not point-grid CSV).

Reuses ``release_shell.lineaments`` for GeoJSON segment loading. GeoPackage /
Shapefile zip support uses optional fiona/rasterio when available; otherwise
GeoJSON is the required path and other formats fail closed with a clear code.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.release_shell.lineaments import (
    LineamentMethod,
    load_lineament_segments,
)
from ssri_model.release_shell.point_grid_csv import require_declared_crs


def _bbox_from_segments(
    segments: list[tuple[float, float, float, float]],
) -> list[float] | None:
    if not segments:
        return None
    xs: list[float] = []
    ys: list[float] = []
    for x1, y1, x2, y2 in segments:
        xs.extend([x1, x2])
        ys.extend([y1, y2])
    return [min(xs), min(ys), max(xs), max(ys)]


def inspect_lineament_geojson(
    content: bytes,
    *,
    filename: str = "lineaments.geojson",
    crs: str | None = None,
) -> dict[str, Any]:
    """Inspect GeoJSON lineaments; CRS may be missing at inspect (reported)."""
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManualTrainingError(
            f"{filename} is not valid GeoJSON text.",
            code="LINEAMENT_FORMAT",
        ) from exc

    segments = load_lineament_segments(payload)
    empty = 0
    invalid = 0
    # Count features for reporting
    features = []
    if payload.get("type") == "FeatureCollection":
        features = payload.get("features") or []
    elif payload.get("type") == "Feature":
        features = [payload]

    geom_types: set[str] = set()
    for feat in features:
        geom = (feat or {}).get("geometry") or {}
        gtype = geom.get("type")
        if not gtype:
            empty += 1
            continue
        geom_types.add(str(gtype))
        coords = geom.get("coordinates")
        if not coords:
            empty += 1

    if not segments and features:
        invalid = len(features)

    return {
        "overall": "INSPECTED",
        "filename": filename,
        "format": "geojson",
        "geometry_types": sorted(geom_types),
        "feature_count": len(features),
        "segment_count": len(segments),
        "empty_or_invalid_geometries": empty + invalid,
        "coverage_bbox": _bbox_from_segments(segments),
        "crs": crs,
        "crs_declared": bool((crs or "").strip()),
        "messages": [
            "Lineament vectors are catalogued separately from X,Y,Z point grids.",
            "CRS must be declared before validation/activation.",
            "Empty segment sets are not treated as evidence that no lineaments exist.",
        ],
        "method": LineamentMethod().to_dict(),
    }


def validate_lineament_geojson(
    content: bytes,
    *,
    filename: str,
    crs: str,
) -> dict[str, Any]:
    """Fail closed without CRS; reuse segment loader for integrity."""
    declared = require_declared_crs(crs)
    inspect = inspect_lineament_geojson(content, filename=filename, crs=declared)
    checks: list[dict[str, Any]] = [
        {
            "name": "crs_declared",
            "status": "PASS",
            "message": f"Declared CRS '{declared}' parsed.",
            "detail": {"crs": declared},
        }
    ]
    if inspect["segment_count"] == 0:
        checks.append(
            {
                "name": "segments",
                "status": "WARN",
                "message": (
                    "No line segments derived. An empty file is not evidence that "
                    "lineaments are absent in the landscape."
                ),
            }
        )
    else:
        checks.append(
            {
                "name": "segments",
                "status": "PASS",
                "message": f"{inspect['segment_count']} segment(s) loaded.",
            }
        )
    if inspect["empty_or_invalid_geometries"]:
        checks.append(
            {
                "name": "geometry_integrity",
                "status": "WARN",
                "message": (
                    f"{inspect['empty_or_invalid_geometries']} empty/invalid "
                    "geometry record(s) noted; original upload is preserved unaltered."
                ),
            }
        )
    else:
        checks.append(
            {
                "name": "geometry_integrity",
                "status": "PASS",
                "message": "No empty/invalid geometries flagged.",
            }
        )

    overall = "WARN" if any(c["status"] == "WARN" for c in checks) else "PASS"
    if any(c["status"] == "FAIL" for c in checks):
        overall = "FAIL"
    return {
        "overall": overall,
        "can_activate_reporting": overall in {"PASS", "WARN"},
        "can_train": False,
        "checks": checks,
        "inspect": inspect,
        "crs": declared,
        "measurement_type": "lineament_vectors",
        "scientific_validation_status": "NOT_VALIDATED",
        "status": "FEATURE_LAYER_ONLY",
        "method": LineamentMethod().to_dict(),
    }


def try_load_vector_archive(
    content: bytes,
    *,
    filename: str,
) -> tuple[bytes, str]:
    """Normalize upload to GeoJSON bytes when possible.

    - ``.geojson`` / ``.json``: returned as-is
    - ``.zip`` shapefile: attempted via fiona if installed; else FAIL closed
    - ``.gpkg``: attempted via fiona if installed; else FAIL closed
    """
    lower = filename.lower()
    if lower.endswith((".geojson", ".json")):
        return content, "geojson"

    if lower.endswith(".zip") or lower.endswith(".gpkg"):
        try:
            import fiona  # type: ignore
        except ImportError as exc:
            raise ManualTrainingError(
                f"{filename}: GeoPackage/Shapefile support requires fiona. "
                "Upload GeoJSON, or install fiona in the API environment.",
                code="LINEAMENT_BACKEND",
            ) from exc

        if lower.endswith(".gpkg"):
            # Write temp is caller's responsibility; operate from BytesIO via zip? gpkg is file
            raise ManualTrainingError(
                "GeoPackage upload must be saved to disk before open; "
                "use the service upload path which stages the file.",
                code="LINEAMENT_GPKG_STAGED",
            )

        # Shapefile zip: extract to memory listing and open with fiona.zip
        if not zipfile.is_zipfile(io.BytesIO(content)):
            raise ManualTrainingError(
                f"{filename} is not a valid zip archive.",
                code="LINEAMENT_FORMAT",
            )
        # Convert via fiona to GeoJSON FeatureCollection
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                for info in zf.infolist():
                    name = info.filename.replace("\\", "/")
                    if name.startswith("/") or ".." in Path(name).parts:
                        raise ManualTrainingError(
                            f"Unsafe path in archive: {info.filename}",
                            code="UNSAFE_PATH",
                        )
                    zf.extract(info, tmp_path)
            shp = next(tmp_path.rglob("*.shp"), None)
            if shp is None:
                raise ManualTrainingError(
                    "Zip archive contains no .shp file.",
                    code="LINEAMENT_FORMAT",
                )
            features: list[dict[str, Any]] = []
            with fiona.open(shp) as src:
                for feat in src:
                    features.append(
                        {
                            "type": "Feature",
                            "geometry": feat.get("geometry"),
                            "properties": dict(feat.get("properties") or {}),
                        }
                    )
            geojson = {
                "type": "FeatureCollection",
                "features": features,
            }
            return json.dumps(geojson).encode("utf-8"), "shapefile_zip"

    raise ManualTrainingError(
        f"Unsupported lineament format for '{filename}'. "
        "Use GeoJSON, or a Shapefile zip / GeoPackage when fiona is available.",
        code="LINEAMENT_FORMAT",
    )


def load_gpkg_as_geojson(path: Path) -> bytes:
    try:
        import fiona  # type: ignore
    except ImportError as exc:
        raise ManualTrainingError(
            "GeoPackage support requires fiona.",
            code="LINEAMENT_BACKEND",
        ) from exc
    features: list[dict[str, Any]] = []
    with fiona.open(path) as src:
        for feat in src:
            features.append(
                {
                    "type": "Feature",
                    "geometry": feat.get("geometry"),
                    "properties": dict(feat.get("properties") or {}),
                }
            )
    return json.dumps({"type": "FeatureCollection", "features": features}).encode(
        "utf-8"
    )
