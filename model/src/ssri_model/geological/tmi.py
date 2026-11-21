"""Client TMI (Total Magnetic Intensity) point-survey validation and processing.

TMI is a geophysical conditioning measurement — never a hazard label.
It is not interchangeable with Stage 2.5 channel ``magnetics`` (EMAG2).
Does not modify the 13-channel SSRIModel contract.
"""

from __future__ import annotations

import csv
import io
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ssri_model.geological.models import MEASUREMENT_TOTAL_MAGNETIC_INTENSITY
from ssri_model.geological.validate import assert_column_mapping_consistent
from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES
from ssri_model.release_shell.point_grid_csv import detect_delimiter

SOFTWARE_ID = "ssri_model.geological.tmi"
SOFTWARE_VERSION = "1.0.0"

# Magnetics in Stage 2.5 is EMAG2 GeoTIFF at this index — not client survey TMI.
_MAGNETICS_CHANNEL = "magnetics"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_col_index(
    header: list[str] | None,
    column: str | int | None,
    default: int,
) -> int:
    if column is None:
        return default
    if isinstance(column, int):
        return column
    text = str(column).strip()
    if text.isdigit():
        return int(text)
    if header:
        lowered = {h.strip().lower(): i for i, h in enumerate(header)}
        key = text.lower()
        if key in lowered:
            return lowered[key]
        raise ValueError(f"Column '{text}' not found in header {header}")
    raise ValueError(f"Cannot resolve column name '{text}' without a header row")


def parse_tmi_points(
    content: bytes,
    *,
    x_column: str | int | None = None,
    y_column: str | int | None = None,
    z_column: str | int | None = None,
) -> dict[str, Any]:
    """Parse CSV into point arrays using explicit column mapping when provided."""
    assert_column_mapping_consistent(
        x_column=x_column, y_column=y_column, value_column=z_column
    )
    text = content.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    sample = "\n".join(lines[:50])
    delim = detect_delimiter(sample) if sample else ","
    stream = io.StringIO(text)
    peek = stream.readline()
    stream.seek(0)
    parts = peek.strip().split(delim) if delim != " " else peek.split()
    has_header = False
    header_row: list[str] | None = None
    if parts:
        try:
            float(parts[0].replace(",", ""))
        except Exception:
            has_header = True
            header_row = [p.strip() for p in parts]

    try:
        xi = _resolve_col_index(header_row, x_column, 0)
        yi = _resolve_col_index(header_row, y_column, 1)
        zi = _resolve_col_index(header_row, z_column, 2)
    except ValueError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "delimiter": delim,
            "header_row": header_row,
            "xs": [],
            "ys": [],
            "zs": [],
            "bad_rows": 0,
            "blank_rows": 0,
            "duplicate_xy": 0,
            "parse_errors": [str(exc)],
        }

    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    bad_rows = 0
    blank = 0
    missing_z = 0
    dups = 0
    seen: set[tuple[float, float]] = set()
    parse_errors: list[str] = []

    reader = csv.reader(stream, delimiter=delim)
    if has_header:
        next(reader, None)
    for row_i, row in enumerate(reader, start=2 if has_header else 1):
        if not row or not any(c.strip() for c in row):
            blank += 1
            continue
        need = max(xi, yi, zi)
        if len(row) <= need:
            bad_rows += 1
            if len(parse_errors) < 20:
                parse_errors.append(f"row {row_i}: fewer than {need + 1} columns")
            continue
        x_raw, y_raw, z_raw = row[xi].strip(), row[yi].strip(), row[zi].strip()
        if not z_raw:
            missing_z += 1
            bad_rows += 1
            continue
        try:
            x, y, z = float(x_raw), float(y_raw), float(z_raw)
        except ValueError:
            bad_rows += 1
            if len(parse_errors) < 20:
                parse_errors.append(f"row {row_i}: non-numeric values")
            continue
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
            bad_rows += 1
            continue
        key = (round(x, 8), round(y, 8))
        if key in seen:
            dups += 1
        else:
            seen.add(key)
        xs.append(x)
        ys.append(y)
        zs.append(z)

    return {
        "ok": True,
        "delimiter": delim,
        "header_present": has_header,
        "header_row": header_row,
        "column_indices": {"x": xi, "y": yi, "z": zi},
        "xs": xs,
        "ys": ys,
        "zs": zs,
        "bad_rows": bad_rows,
        "blank_rows": blank,
        "duplicate_xy": dups,
        "missing_z": missing_z,
        "parse_errors": parse_errors,
        "unique_xy": len(seen),
    }


def _is_geographic_crs(crs: str) -> bool:
    key = (crs or "").strip().upper().replace(" ", "")
    return key in {"EPSG:4326", "WGS84", "WGS84/EPSG:4326"} or "4326" in key


def _tmi_stats(zs: list[float]) -> dict[str, Any]:
    if not zs:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "stdev": None,
            "constant": False,
            "outlier_count_iqr": 0,
            "units": "unknown",
        }
    z_sorted = sorted(zs)
    mean = statistics.fmean(zs)
    stdev = statistics.pstdev(zs) if len(zs) > 1 else 0.0
    q1 = z_sorted[len(z_sorted) // 4]
    q3 = z_sorted[(3 * len(z_sorted)) // 4]
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = sum(1 for z in zs if z < lo or z > hi)
    return {
        "count": len(zs),
        "min": min(zs),
        "max": max(zs),
        "mean": mean,
        "stdev": stdev,
        "p01": z_sorted[max(0, int(0.01 * (len(z_sorted) - 1)))],
        "p50": z_sorted[len(z_sorted) // 2],
        "p99": z_sorted[min(len(z_sorted) - 1, int(0.99 * (len(z_sorted) - 1)))],
        "constant": stdev == 0.0,
        "outlier_count_iqr": outliers,
        "units": "unknown",
    }


def _spatial_assessment(xs: list[float], ys: list[float]) -> dict[str, Any]:
    if not xs:
        return {
            "point_count": 0,
            "extent": None,
            "unique_x": 0,
            "unique_y": 0,
            "gridding_suitable": False,
            "coverage_note": "no_points",
        }
    ux = sorted({round(x, 8) for x in xs})
    uy = sorted({round(y, 8) for y in ys})
    x_gaps = [ux[i + 1] - ux[i] for i in range(len(ux) - 1)] if len(ux) > 1 else []
    y_gaps = [uy[i + 1] - uy[i] for i in range(len(uy) - 1)] if len(uy) > 1 else []
    extent = [min(xs), min(ys), max(xs), max(ys)]
    span_x = extent[2] - extent[0]
    span_y = extent[3] - extent[1]
    density = len(xs) / max(span_x * span_y, 1e-12)
    # Lattice-like if unique X×Y ≈ point count
    expected = len(ux) * len(uy)
    fill = (len({(round(x, 8), round(y, 8)) for x, y in zip(xs, ys)}) / expected) if expected else 0.0
    lattice_like = expected > 0 and fill >= 0.85 and len(ux) >= 2 and len(uy) >= 2
    irregular = not lattice_like
    suitable = len(xs) >= 4 and span_x > 0 and span_y > 0
    return {
        "point_count": len(xs),
        "extent": extent,
        "span_x": span_x,
        "span_y": span_y,
        "unique_x": len(ux),
        "unique_y": len(uy),
        "median_gap_x": statistics.median(x_gaps) if x_gaps else None,
        "median_gap_y": statistics.median(y_gaps) if y_gaps else None,
        "approx_density_per_extent_unit2": density,
        "lattice_fill_ratio": fill if expected else None,
        "lattice_like": lattice_like,
        "irregular_point_cloud": irregular,
        "gridding_suitable": suitable,
        "coverage_note": (
            "regular_lattice_candidate"
            if lattice_like
            else "irregular_survey_cloud"
        ),
    }


def assess_feature_compatibility(
    *,
    crs: str | None,
    units: str | None,
    spatial: dict[str, Any],
    tmi_stats: dict[str, Any],
) -> dict[str, Any]:
    """Document why client TMI must not silently enter the 13-channel stack."""
    try:
        mag_idx = CHANNEL_NAMES.index(_MAGNETICS_CHANNEL)
    except ValueError:
        mag_idx = None

    units_known = bool((units or "").strip()) and (units or "").strip().lower() not in {
        "unknown",
        "n/a",
        "na",
    }
    geo_ok = _is_geographic_crs(crs or "") if crs else False

    return {
        "status": "feature_compatibility_review",
        "measurement_type": MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
        "corresponds_to_existing_channel": False,
        "existing_related_channel": {
            "name": _MAGNETICS_CHANNEL,
            "index_0_based": mag_idx,
            "source": "EMAG2 GeoTIFF (global magnetics product)",
            "same_as_client_tmi": False,
        },
        "channel_count_frozen": CHANNEL_COUNT,
        "may_replace_existing_channel": False,
        "may_add_as_14th_channel": False,
        "requires_spatial_interpolation_or_resampling": bool(
            spatial.get("irregular_point_cloud") or not spatial.get("lattice_like")
        ),
        "geographic_compatibility": (
            "review_required_after_alignment"
            if geo_ok and spatial.get("gridding_suitable")
            else "insufficient_or_unconfirmed"
        ),
        "coverage_and_resolution_sufficient": bool(
            spatial.get("gridding_suitable") and (tmi_stats.get("count") or 0) >= 4
        ),
        "units_confirmed": units_known,
        "assumes_nanotesla": False,
        "architecture_change_required_for_integration": True,
        "training_and_evaluation_change_required": True,
        "production_model_unchanged": True,
        "contributes_to_live_hazard_predictions": False,
        "is_hazard_label": False,
        "blocks_stage25_training_promotion": True,
        "recommendation": (
            "Keep TMI as a separate geophysical catalogue asset. "
            "Do not overwrite CHANNEL_NAMES magnetics (EMAG2). "
            "A future architecture RFC would be required before any "
            "optional extra-channel or replacement experiment."
        ),
        "assessed_at": _utc_now(),
    }


def validate_tmi_point_survey(
    content: bytes,
    *,
    filename: str,
    crs: str,
    units: str | None = None,
    x_column: str | int | None = None,
    y_column: str | int | None = None,
    z_column: str | int | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate client TMI CSV without requiring a regular lattice for PASS/WARN.

    Failed structural/coordinate checks set overall=FAIL and block processing.
    Irregular sampling yields WARN + gridding_suitable assessment — not FAIL.
    """
    checks: list[dict[str, Any]] = []
    prov = dict(provenance or {})

    try:
        assert_column_mapping_consistent(
            x_column=x_column, y_column=y_column, value_column=z_column
        )
    except Exception as exc:
        msg = getattr(exc, "message", str(exc))
        return {
            "overall": "FAIL",
            "can_train": False,
            "can_activate_reporting": False,
            "can_process": False,
            "measurement_type": MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
            "scientific_validation_status": "NOT_VALIDATED",
            "checks": [
                {
                    "name": "column_mapping",
                    "status": "FAIL",
                    "message": msg,
                }
            ],
            "feature_compatibility": assess_feature_compatibility(
                crs=crs,
                units=units,
                spatial={"gridding_suitable": False},
                tmi_stats={"count": 0},
            ),
        }

    parsed = parse_tmi_points(
        content, x_column=x_column, y_column=y_column, z_column=z_column
    )
    if not parsed.get("ok"):
        checks.append(
            {
                "name": "csv_parse",
                "status": "FAIL",
                "message": parsed.get("error") or "CSV parse failed.",
            }
        )
        return {
            "overall": "FAIL",
            "can_train": False,
            "can_activate_reporting": False,
            "can_process": False,
            "measurement_type": MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
            "scientific_validation_status": "NOT_VALIDATED",
            "checks": checks,
            "filename": filename,
        }

    xs, ys, zs = parsed["xs"], parsed["ys"], parsed["zs"]
    checks.append(
        {
            "name": "required_columns",
            "status": "PASS" if xs else "FAIL",
            "message": (
                f"Parsed {len(xs)} numeric X/Y/Z rows "
                f"(bad={parsed['bad_rows']}, blank={parsed['blank_rows']}, "
                f"dup_xy={parsed['duplicate_xy']})."
            ),
            "detail": {
                "column_indices": parsed.get("column_indices"),
                "parse_errors": parsed.get("parse_errors") or [],
            },
        }
    )

    geo = _is_geographic_crs(crs)
    crs_kind = (
        "geographic WGS84 family"
        if geo
        else "projected or other — coordinates must match this CRS; do not treat lon/lat as metres"
    )
    checks.append(
        {
            "name": "crs",
            "status": "PASS" if (crs or "").strip() else "FAIL",
            "message": f"Declared CRS '{crs}' ({crs_kind}).",
            "detail": {"geographic_wgs84_family": geo},
        }
    )

    invalid_geo = 0
    if geo and xs:
        for x, y in zip(xs, ys):
            if not (-180.0 <= x <= 180.0 and -90.0 <= y <= 90.0):
                invalid_geo += 1
        # Suspected metres mistaken for degrees
        if xs and (abs(statistics.fmean(xs)) > 180 or abs(statistics.fmean(ys)) > 90):
            checks.append(
                {
                    "name": "coordinate_units",
                    "status": "FAIL",
                    "message": (
                        "Declared geographic CRS but coordinate magnitudes look "
                        "like projected metres. Do not interpret lon/lat as metres."
                    ),
                }
            )
        checks.append(
            {
                "name": "geographic_ranges",
                "status": "FAIL" if invalid_geo else "PASS",
                "message": (
                    f"{invalid_geo} points outside lon[-180,180]/lat[-90,90]."
                    if invalid_geo
                    else "All points within geographic lon/lat ranges."
                ),
            }
        )
    elif xs:
        checks.append(
            {
                "name": "geographic_ranges",
                "status": "WARN",
                "message": (
                    "CRS is not EPSG:4326 family; geographic range checks skipped. "
                    "Original coordinates preserved; transform only with confirmed CRS."
                ),
            }
        )

    tmi_stats = _tmi_stats(zs)
    tmi_stats["units"] = (units or "").strip() or "unknown"
    tmi_status = "PASS"
    tmi_msg = (
        f"TMI min={tmi_stats['min']}, max={tmi_stats['max']}, "
        f"mean={tmi_stats['mean']}, stdev={tmi_stats['stdev']}, "
        f"IQR outliers={tmi_stats['outlier_count_iqr']}. "
        f"Units={tmi_stats['units']} (not assumed nT)."
    )
    if tmi_stats.get("constant"):
        tmi_status = "WARN"
        tmi_msg += " Values are constant — suspicious for a magnetic survey."
    if tmi_stats.get("outlier_count_iqr", 0) > max(3, int(0.05 * len(zs))):
        tmi_status = "WARN"
        tmi_msg += " Elevated outlier count under IQR rule."
    checks.append({"name": "tmi_distribution", "status": tmi_status, "message": tmi_msg})

    if not (units or "").strip():
        checks.append(
            {
                "name": "units",
                "status": "WARN",
                "message": "Measurement units unknown — not assumed to be nanotesla (nT).",
            }
        )
    else:
        checks.append(
            {
                "name": "units",
                "status": "PASS",
                "message": f"Units declared as '{units}'.",
            }
        )

    spatial = _spatial_assessment(xs, ys)
    spat_status = "PASS" if spatial.get("gridding_suitable") else "WARN"
    if not xs:
        spat_status = "FAIL"
    checks.append(
        {
            "name": "spatial_coverage",
            "status": spat_status,
            "message": (
                f"{spatial['point_count']} points; extent={spatial.get('extent')}; "
                f"{spatial.get('coverage_note')}; "
                f"gridding_suitable={spatial.get('gridding_suitable')}."
            ),
            "detail": spatial,
        }
    )
    if spatial.get("irregular_point_cloud"):
        checks.append(
            {
                "name": "lattice_requirement",
                "status": "WARN",
                "message": (
                    "Irregular point cloud is acceptable for TMI catalogue validation. "
                    "Regular lattice is not required to pass, but gridding remains a "
                    "separate processing stage."
                ),
            }
        )

    # Survey metadata — never fabricate
    meta_fields = (
        "survey_date",
        "survey_method",
        "sampling_spacing",
        "processing_history",
        "source_organization",
        "geographic_coverage",
    )
    unknown_meta = [k for k in meta_fields if not str(prov.get(k) or "").strip()]
    checks.append(
        {
            "name": "survey_metadata",
            "status": "WARN" if unknown_meta else "PASS",
            "message": (
                "Survey metadata incomplete; unknown fields left explicit."
                if unknown_meta
                else "Survey metadata fields provided."
            ),
            "detail": {
                "unknown_fields": unknown_meta,
                "provided_fields": [k for k in meta_fields if k not in unknown_meta],
            },
        }
    )

    fail = any(c["status"] == "FAIL" for c in checks)
    warn = any(c["status"] == "WARN" for c in checks)
    overall = "FAIL" if fail else ("WARN" if warn else "PASS")
    can_process = overall != "FAIL" and bool(spatial.get("gridding_suitable"))
    can_activate = overall in {"PASS", "WARN"} and bool((crs or "").strip())

    compatibility = assess_feature_compatibility(
        crs=crs, units=units, spatial=spatial, tmi_stats=tmi_stats
    )

    return {
        "overall": overall,
        "can_train": False,
        "can_activate_reporting": can_activate,
        "can_process": can_process,
        "measurement_type": MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
        "scientific_validation_status": "NOT_VALIDATED",
        "filename": filename,
        "checks": checks,
        "tmi_statistics": tmi_stats,
        "spatial": spatial,
        "coverage_bbox": spatial.get("extent"),
        "column_mapping": {
            "x_column": x_column,
            "y_column": y_column,
            "z_column": z_column,
            "applied": True,
            "indices": parsed.get("column_indices"),
        },
        "original_coordinates_preserved": True,
        "feature_compatibility": compatibility,
        "lifecycle": "validated" if overall != "FAIL" else "validation_failed",
        "messages": [
            "TMI is not a hazard label and does not unblock Stage 2.5 three-class training.",
            "Client TMI is not interchangeable with EMAG2 magnetics channel.",
            "Raw source bytes are never overwritten by processing.",
        ],
    }


def grid_tmi_nearest(
    xs: list[float],
    ys: list[float],
    zs: list[float],
    *,
    resolution: float,
    nodata: float = -9999.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Nearest-neighbour gridding of irregular TMI points (traceable, no RTP/UC)."""
    if len(xs) < 4:
        raise ValueError("Need at least 4 points to grid.")
    if resolution <= 0:
        raise ValueError("resolution must be positive.")
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    width = max(2, int(math.ceil((xmax - xmin) / resolution)) + 1)
    height = max(2, int(math.ceil((ymax - ymin) / resolution)) + 1)
    # Cap grid size for safety
    if width * height > 4_000_000:
        raise ValueError(
            f"Requested grid {width}×{height} exceeds safety limit; choose coarser resolution."
        )
    grid = np.full((height, width), nodata, dtype=np.float32)
    pts = np.column_stack([np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)])
    vals = np.asarray(zs, dtype=np.float64)
    for row in range(height):
        cy = ymax - row * resolution
        for col in range(width):
            cx = xmin + col * resolution
            d2 = (pts[:, 0] - cx) ** 2 + (pts[:, 1] - cy) ** 2
            grid[row, col] = float(vals[int(np.argmin(d2))])
    meta = {
        "method": "nearest_neighbour",
        "resolution": resolution,
        "width": width,
        "height": height,
        "xmin": xmin,
        "ymax": ymax,
        "ymin": ymin,
        "xmax": xmax,
        "nodata": nodata,
        "point_count": len(xs),
        "transform_affine": [resolution, 0.0, xmin, 0.0, -resolution, ymax],
    }
    return grid, meta


def write_tmi_geotiff(
    path: Path,
    grid: np.ndarray,
    meta: dict[str, Any],
    *,
    crs: str,
) -> None:
    import rasterio
    from rasterio.transform import from_origin

    path.parent.mkdir(parents=True, exist_ok=True)
    transform = from_origin(meta["xmin"], meta["ymax"], meta["resolution"], meta["resolution"])
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=grid.shape[0],
        width=grid.shape[1],
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=meta["nodata"],
    ) as dst:
        dst.write(grid, 1)
        dst.update_tags(
            MEASUREMENT=MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
            METHOD=meta["method"],
            SOFTWARE=SOFTWARE_ID,
            SOFTWARE_VERSION=SOFTWARE_VERSION,
        )


def process_tmi_to_grid(
    content: bytes,
    *,
    out_tif: Path,
    provenance_json: Path,
    source_geo_id: str,
    crs: str,
    units: str | None,
    resolution: float,
    x_column: str | int | None = None,
    y_column: str | int | None = None,
    z_column: str | int | None = None,
    nodata: float = -9999.0,
) -> dict[str, Any]:
    """Produce a derived TMI grid without modifying the original upload."""
    parsed = parse_tmi_points(
        content, x_column=x_column, y_column=y_column, z_column=z_column
    )
    if not parsed.get("ok") or not parsed["xs"]:
        raise ValueError(parsed.get("error") or "No points to process.")
    grid, meta = grid_tmi_nearest(
        parsed["xs"], parsed["ys"], parsed["zs"], resolution=resolution, nodata=nodata
    )
    write_tmi_geotiff(out_tif, grid, meta, crs=crs)
    report = {
        "source_dataset_id": source_geo_id,
        "processing_method": meta["method"],
        "parameters": {
            "resolution": resolution,
            "nodata": nodata,
            "column_mapping": {
                "x_column": x_column,
                "y_column": y_column,
                "z_column": z_column,
            },
        },
        "crs": crs,
        "resolution": resolution,
        "nodata": nodata,
        "units": (units or "").strip() or "unknown",
        "grid": {k: meta[k] for k in ("width", "height", "xmin", "ymin", "xmax", "ymax")},
        "derived_relpath": "working/derived/tmi_grid.tif",
        "software": SOFTWARE_ID,
        "software_version": SOFTWARE_VERSION,
        "processed_at": _utc_now(),
        "raw_source_unmodified": True,
        "geophysical_transforms_applied": [],
        "notes": [
            "No reduction-to-pole, upward continuation, or regional-residual "
            "separation was applied.",
            "Raw TMI is not assumed to be residual magnetic anomaly.",
        ],
        "feature_compatibility": assess_feature_compatibility(
            crs=crs,
            units=units,
            spatial=_spatial_assessment(parsed["xs"], parsed["ys"]),
            tmi_stats=_tmi_stats(parsed["zs"]),
        ),
    }
    provenance_json.parent.mkdir(parents=True, exist_ok=True)
    provenance_json.write_text(
        __import__("json").dumps(report, indent=2), encoding="utf-8"
    )
    return report
