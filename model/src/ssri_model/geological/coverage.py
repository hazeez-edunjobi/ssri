"""AOI ∩ geological dataset coverage reporting (no inference side-effects).

Coverage metrics in this module are **axis-aligned bounding-box intersection**
only. They are not valid-cell / non-NoData AOI coverage percentages.
"""

from __future__ import annotations

from typing import Any, Sequence

from ssri_model.geological.models import GeologicalDatasetRecord
from ssri_model.geological.storage import GeologicalStorage

CoverageClass = str  # full | partial | none | unknown

# Explicit metric identity for API / UI consumers.
COVERAGE_METRIC_BBOX_INTERSECTION = "aoi_bbox_intersection"


def _bbox_intersects(a: Sequence[float], b: Sequence[float]) -> bool:
    """Axis-aligned bbox [xmin, ymin, xmax, ymax] intersection test."""
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def _intersection_area(a: Sequence[float], b: Sequence[float]) -> float:
    xmin = max(a[0], b[0])
    ymin = max(a[1], b[1])
    xmax = min(a[2], b[2])
    ymax = min(a[3], b[3])
    if xmax <= xmin or ymax <= ymin:
        return 0.0
    return float((xmax - xmin) * (ymax - ymin))


def _area(b: Sequence[float]) -> float:
    return max(0.0, float((b[2] - b[0]) * (b[3] - b[1])))


def classify_coverage(
    aoi_bbox: Sequence[float],
    dataset_bbox: Sequence[float] | None,
    *,
    full_threshold: float = 0.95,
) -> tuple[CoverageClass, float | None]:
    """Return (coverage_class, fraction of AOI bbox overlapped by dataset bbox).

    Approximation is **bbox-based only** (catalogue reporting). This is not a
    pixel-exact valid-data mask. Returns unknown when dataset bbox is missing.
    """
    if not dataset_bbox or len(dataset_bbox) != 4:
        return "unknown", None
    if not _bbox_intersects(aoi_bbox, dataset_bbox):
        return "none", 0.0
    aoi_a = _area(aoi_bbox)
    if aoi_a <= 0:
        return "unknown", None
    inter = _intersection_area(aoi_bbox, dataset_bbox)
    pct = inter / aoi_a
    if pct >= full_threshold:
        return "full", pct
    if pct > 0:
        return "partial", pct
    return "none", 0.0


def dataset_coverage_summary(
    record: GeologicalDatasetRecord,
    *,
    storage: GeologicalStorage | None = None,
) -> dict[str, Any]:
    inspect = record.inspect_report or {}
    missing = inspect.get("missing_lattice_cells")
    row_count = inspect.get("row_count")
    expected = inspect.get("expected_full_grid_cells")
    nodata_fraction = None
    if isinstance(expected, int) and expected > 0 and isinstance(missing, int):
        nodata_fraction = missing / expected

    app_status: dict[str, Any]
    if storage is not None:
        app_status = storage.feature_application_status(record)
    else:
        app_status = {
            "used_in_feature_application": False,
            "feature_application_count": 0,
            "feature_applications": [],
            "feature_application_status": "unknown_no_storage",
        }

    return {
        "geo_id": record.geo_id,
        "display_name": record.display_name,
        "asset_kind": record.asset_kind,
        "measurement_type": record.measurement_type,
        "units": record.units,
        "crs": record.crs,
        "working_crs": record.working_crs,
        "coverage_bbox": record.coverage_bbox,
        "dataset_footprint_bbox": record.coverage_bbox,
        "grid_spacing_x": record.grid_spacing_x,
        "grid_spacing_y": record.grid_spacing_y,
        "grid_spacing_units": record.grid_spacing_units,
        "validation_status": record.validation_status,
        "activation_status": record.activation_status,
        "scientific_validation_status": record.scientific_validation_status,
        "provenance": {
            "source_client": record.source_client,
            "original_filename": record.original_filename,
            "content_sha256": record.content_sha256,
            "uploaded_at": record.uploaded_at,
            "created_by_key_id": record.created_by_key_id,
            **dict(record.provenance or {}),
        },
        "valid_data": {
            "row_count": row_count,
            "missing_lattice_cells": missing,
            # Dataset-global lattice stats from inspect — NOT AOI-masked valid cells.
            "approx_nodata_fraction_on_lattice": nodata_fraction,
            "negative_z_count": inspect.get("negative_z_count"),
            "note": (
                "Lattice NoData stats are dataset-global from inspect, not "
                "AOI-masked valid-cell coverage."
            ),
        },
        "exists": True,
        "is_validated": record.validation_status == "validated",
        "is_activated": record.activation_status in {"reporting_only", "approved"},
        "used_in_feature_application": bool(app_status.get("used_in_feature_application")),
        "feature_application_status": app_status.get("feature_application_status"),
        "feature_application_count": app_status.get("feature_application_count"),
        "feature_applications": app_status.get("feature_applications"),
        "latest_feature_application_at": app_status.get("latest_feature_application_at"),
        "latest_target_dataset_id": app_status.get("latest_target_dataset_id"),
        "used_in_inference": False,
    }


def match_aoi(
    records: Sequence[GeologicalDatasetRecord],
    *,
    aoi_bbox: Sequence[float],
    measurement_type: str | None = None,
    require_validated: bool = True,
    require_activated: bool = True,
    aoi_crs: str | None = None,
    storage: GeologicalStorage | None = None,
) -> dict[str, Any]:
    """Report which catalogue datasets' bboxes intersect an AOI bbox.

    Selection policy (documented, explicit):
    1. Optional measurement_type filter (exact canonical match).
    2. validation_status == validated (if require_validated).
    3. activation_status in {reporting_only, approved} (if require_activated).
    4. bbox intersection in the **dataset's declared CRS** — caller must supply
       ``aoi_bbox`` already expressed in a CRS comparable to each dataset, or
       accept CRS-mismatch warnings when ``aoi_crs`` ≠ dataset.crs.
    5. Overlapping eligible datasets with the **same** measurement_type are
       reported as a **conflict**; none is auto-selected.
    6. Filename / place-name matching is never used.

    Metric: ``coverage_metric = aoi_bbox_intersection`` — not valid-cell coverage.
    """
    if len(aoi_bbox) != 4:
        raise ValueError("aoi_bbox must be [xmin, ymin, xmax, ymax]")

    matches: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for rec in records:
        summary = dataset_coverage_summary(rec, storage=storage)
        reasons: list[str] = []
        if measurement_type and rec.measurement_type != measurement_type:
            reasons.append("measurement_type_mismatch")
        if require_validated and rec.validation_status != "validated":
            reasons.append("not_validated")
        if require_activated and rec.activation_status not in {
            "reporting_only",
            "approved",
        }:
            reasons.append("not_activated")
        if reasons:
            skipped.append({**summary, "skip_reasons": reasons})
            continue

        cov_class, pct = classify_coverage(aoi_bbox, rec.coverage_bbox)
        crs_warning = None
        if aoi_crs and rec.crs and aoi_crs.strip() != rec.crs.strip():
            crs_warning = (
                f"AOI CRS '{aoi_crs}' differs from dataset CRS '{rec.crs}'. "
                "Bbox comparison assumes coordinates are already comparable; "
                "reproject before relying on bbox intersection percentages."
            )
        resolution_note = None
        if rec.grid_spacing_x is not None and rec.grid_spacing_y is not None:
            resolution_note = (
                f"Grid spacing {rec.grid_spacing_x:g} × {rec.grid_spacing_y:g} "
                f"({rec.grid_spacing_units or 'file_units'}). "
                "Appropriateness for the AOI workflow is operator-judged."
            )
        entry = {
            **summary,
            "intersects_aoi": cov_class in {"full", "partial"},
            "coverage_metric": COVERAGE_METRIC_BBOX_INTERSECTION,
            "coverage_class": cov_class,
            # Canonical name for the bbox metric.
            "aoi_bbox_intersection_fraction": pct,
            # Backwards-compatible alias (same bbox math; not valid-cell coverage).
            "approx_aoi_coverage_fraction": pct,
            "crs_transform_required": bool(crs_warning),
            "crs_warning": crs_warning,
            "resolution_note": resolution_note,
            "selected_for_application": False,
            "used_in_inference": False,
        }
        if cov_class == "none":
            skipped.append({**entry, "skip_reasons": ["no_intersection"]})
        else:
            matches.append(entry)

    # Conflict detection: multiple eligible matches with same measurement_type.
    by_mt: dict[str, list[dict[str, Any]]] = {}
    for m in matches:
        mt = str(m.get("measurement_type") or "undeclared")
        by_mt.setdefault(mt, []).append(m)
    for mt, group in by_mt.items():
        if len(group) > 1:
            conflicts.append(
                {
                    "measurement_type": mt,
                    "geo_ids": [g["geo_id"] for g in group],
                    "policy": (
                        "No automatic priority. Operator must choose one dataset "
                        "explicitly; overlapping conflicting measurements are never "
                        "silently combined."
                    ),
                }
            )

    available_types = sorted(
        {m["measurement_type"] for m in matches if m.get("measurement_type")}
    )
    return {
        "aoi_bbox": list(aoi_bbox),
        "aoi_crs": aoi_crs,
        "coverage_metric": COVERAGE_METRIC_BBOX_INTERSECTION,
        "coverage_metric_description": (
            "Axis-aligned bounding-box intersection between the AOI bbox and each "
            "dataset footprint bbox. This is not valid-cell / non-NoData coverage "
            "of the AOI. Dataset-global lattice NoData stats are reported separately "
            "under valid_data and are not AOI-masked."
        ),
        "matches": matches,
        "conflicts": conflicts,
        "skipped": skipped,
        "available_measurement_types": available_types,
        "selection_policy": (
            "bbox intersection + measurement_type + validated + activated; "
            "conflicts reported, never auto-merged; no filename matching."
        ),
        "used_in_inference": False,
        "note": (
            "Bounding-box intersection reporting only. Intersection does not mean "
            "valid measurements exist at every AOI cell, and does not mean the layer "
            "was used in live assessment inference."
        ),
    }
