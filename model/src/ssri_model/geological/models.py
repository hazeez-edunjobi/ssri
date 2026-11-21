"""Geological dataset catalogue models (point-grid CSV + vector lineaments).

Distinct from Stage 2.5 training datasets and platform training zips.
Measurement types are never silently aliased (depth ≠ thickness).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

AssetKind = Literal["point_grid_csv", "vector_lineament"]
ValidationStatus = Literal["pending", "inspected", "validated", "failed"]
ActivationStatus = Literal["inactive", "reporting_only", "approved"]
ProcessingStatus = Literal[
    "not_started",
    "processing",
    "processed",
    "processing_failed",
    "feature_compatibility_review",
    "accepted_with_limitations",
    "rejected",
]

# Canonical measurement identities for point-grid uploads.
MEASUREMENT_OVERBURDEN_THICKNESS = "overburden_thickness"
MEASUREMENT_DEPTH_TO_BEDROCK = "depth_to_bedrock"
MEASUREMENT_LINEAMENT = "lineament_vectors"
MEASUREMENT_TOTAL_MAGNETIC_INTENSITY = "total_magnetic_intensity"

KNOWN_MEASUREMENTS = frozenset(
    {
        MEASUREMENT_OVERBURDEN_THICKNESS,
        MEASUREMENT_DEPTH_TO_BEDROCK,
        MEASUREMENT_LINEAMENT,
        MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
    }
)

# Accepted declaration aliases → canonical store value (never depth→thickness).
MEASUREMENT_ALIASES: dict[str, str] = {
    "overburden_thickness": MEASUREMENT_OVERBURDEN_THICKNESS,
    "overburden": MEASUREMENT_OVERBURDEN_THICKNESS,
    "thickness": MEASUREMENT_OVERBURDEN_THICKNESS,
    "depth_to_bedrock": MEASUREMENT_DEPTH_TO_BEDROCK,
    "depth_to_interface": MEASUREMENT_DEPTH_TO_BEDROCK,
    "bedrock_depth": MEASUREMENT_DEPTH_TO_BEDROCK,
    "depth": MEASUREMENT_DEPTH_TO_BEDROCK,
    "lineament": MEASUREMENT_LINEAMENT,
    "lineaments": MEASUREMENT_LINEAMENT,
    "lineament_vectors": MEASUREMENT_LINEAMENT,
    "total_magnetic_intensity": MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
    "tmi": MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
    "magnetic_intensity": MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
    "total_magnetic": MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
    "magnetics_tmi": MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
}


def canonicalize_measurement_type(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    key = raw.lower().replace(" ", "_").replace("-", "_")
    if key.startswith("other:"):
        return key
    return MEASUREMENT_ALIASES.get(key, key)


def is_tmi_measurement(value: str | None) -> bool:
    return canonicalize_measurement_type(value) == MEASUREMENT_TOTAL_MAGNETIC_INTENSITY


@dataclass
class NodataPolicy:
    missing_cells: str = "FEATURE_NODATA"
    negatives: str = "report_only"
    sentinels: list[float] = field(default_factory=lambda: [-9999.0, -999.0])

    def to_dict(self) -> dict[str, Any]:
        return {
            "missing_cells": self.missing_cells,
            "negatives": self.negatives,
            "sentinels": list(self.sentinels),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> NodataPolicy:
        data = payload or {}
        return cls(
            missing_cells=str(data.get("missing_cells") or "FEATURE_NODATA"),
            negatives=str(data.get("negatives") or "report_only"),
            sentinels=[float(v) for v in (data.get("sentinels") or [-9999.0, -999.0])],
        )


@dataclass
class GeologicalDatasetRecord:
    geo_id: str
    display_name: str
    asset_kind: AssetKind
    original_filename: str
    uploaded_at: str
    content_sha256: str
    original_relpath: str
    working_relpath: str
    measurement_type: str | None = None
    measurement_description: str = ""
    description: str = ""
    source_client: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    x_column: str | int | None = None
    y_column: str | int | None = None
    z_column: str | int | None = None
    crs: str | None = None
    working_crs: str | None = None
    units: str | None = None
    z_to_metres: float | None = None
    coverage_bbox: list[float] | None = None  # [xmin, ymin, xmax, ymax] in declared CRS
    grid_spacing_x: float | None = None
    grid_spacing_y: float | None = None
    grid_spacing_units: str | None = None  # file_units | metres
    nodata_policy: NodataPolicy = field(default_factory=NodataPolicy)
    validation_status: ValidationStatus = "pending"
    validation_report: dict[str, Any] = field(default_factory=dict)
    inspect_report: dict[str, Any] = field(default_factory=dict)
    activation_status: ActivationStatus = "inactive"
    scientific_validation_status: str = "NOT_VALIDATED"
    notes: str = ""
    # Audit identity only — catalogue remains single-tenant / shared-operator (see F4).
    created_by_key_id: str | None = None
    # Lineament-specific
    geometry_type: str | None = None
    feature_count: int | None = None
    lineament_method: dict[str, Any] = field(default_factory=dict)
    # Geophysical processing / TMI lifecycle (derived only; never overwrites original)
    processing_status: ProcessingStatus = "not_started"
    processing_report: dict[str, Any] = field(default_factory=dict)
    feature_compatibility: dict[str, Any] = field(default_factory=dict)
    derived_relpath: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["nodata_policy"] = self.nodata_policy.to_dict()
        # Never expose absolute filesystem roots to API consumers.
        payload.pop("original_relpath", None)
        payload.pop("working_relpath", None)
        payload["has_original"] = bool(self.original_relpath)
        payload["has_working"] = bool(self.working_relpath)
        payload["has_derived"] = bool(self.derived_relpath)
        return payload

    def to_storage_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["nodata_policy"] = self.nodata_policy.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> GeologicalDatasetRecord:
        return cls(
            geo_id=str(payload["geo_id"]),
            display_name=str(payload.get("display_name") or ""),
            asset_kind=payload.get("asset_kind") or "point_grid_csv",  # type: ignore[arg-type]
            original_filename=str(payload.get("original_filename") or ""),
            uploaded_at=str(payload.get("uploaded_at") or ""),
            content_sha256=str(payload.get("content_sha256") or ""),
            original_relpath=str(payload.get("original_relpath") or ""),
            working_relpath=str(payload.get("working_relpath") or ""),
            measurement_type=payload.get("measurement_type"),
            measurement_description=str(payload.get("measurement_description") or ""),
            description=str(payload.get("description") or ""),
            source_client=str(payload.get("source_client") or ""),
            provenance=dict(payload.get("provenance") or {}),
            x_column=payload.get("x_column"),
            y_column=payload.get("y_column"),
            z_column=payload.get("z_column"),
            crs=payload.get("crs"),
            working_crs=payload.get("working_crs"),
            units=payload.get("units"),
            z_to_metres=payload.get("z_to_metres"),
            coverage_bbox=list(payload["coverage_bbox"])
            if payload.get("coverage_bbox")
            else None,
            grid_spacing_x=payload.get("grid_spacing_x"),
            grid_spacing_y=payload.get("grid_spacing_y"),
            grid_spacing_units=payload.get("grid_spacing_units"),
            nodata_policy=NodataPolicy.from_dict(payload.get("nodata_policy")),
            validation_status=payload.get("validation_status") or "pending",  # type: ignore[arg-type]
            validation_report=dict(payload.get("validation_report") or {}),
            inspect_report=dict(payload.get("inspect_report") or {}),
            activation_status=payload.get("activation_status") or "inactive",  # type: ignore[arg-type]
            scientific_validation_status=str(
                payload.get("scientific_validation_status") or "NOT_VALIDATED"
            ),
            notes=str(payload.get("notes") or ""),
            created_by_key_id=(
                str(payload["created_by_key_id"])
                if payload.get("created_by_key_id") is not None
                else None
            ),
            geometry_type=payload.get("geometry_type"),
            feature_count=payload.get("feature_count"),
            lineament_method=dict(payload.get("lineament_method") or {}),
            processing_status=payload.get("processing_status") or "not_started",  # type: ignore[arg-type]
            processing_report=dict(payload.get("processing_report") or {}),
            feature_compatibility=dict(payload.get("feature_compatibility") or {}),
            derived_relpath=payload.get("derived_relpath"),
        )
