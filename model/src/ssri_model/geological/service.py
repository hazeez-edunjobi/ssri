"""Orchestration for geological catalogue upload / declare / validate / activate."""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ssri_model.geological.coverage import match_aoi
from ssri_model.geological.inspect import inspect_point_grid_bytes
from ssri_model.geological.lineament_ingest import (
    inspect_lineament_geojson,
    load_gpkg_as_geojson,
    try_load_vector_archive,
    validate_lineament_geojson,
)
from ssri_model.geological.models import (
    MEASUREMENT_LINEAMENT,
    NodataPolicy,
    canonicalize_measurement_type,
)
from ssri_model.geological.storage import GeologicalStorage
from ssri_model.geological.validate import validate_declared_point_grid
from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.manual_training.upload_limits import reject_if_upload_too_large


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class GeologicalService:
    def __init__(self, storage: GeologicalStorage) -> None:
        self.storage = storage

    def create(
        self,
        *,
        display_name: str,
        asset_kind: str = "point_grid_csv",
        description: str = "",
        source_client: str = "",
        notes: str = "",
        created_by_key_id: str | None = None,
    ):
        if asset_kind not in {"point_grid_csv", "vector_lineament"}:
            raise ManualTrainingError(
                f"Unsupported asset_kind '{asset_kind}'.",
                code="ASSET_KIND",
            )
        return self.storage.create_shell(
            display_name=display_name,
            asset_kind=asset_kind,
            description=description,
            source_client=source_client,
            notes=notes,
            created_by_key_id=created_by_key_id,
        )

    def upload_csv(self, geo_id: str, *, filename: str, content: bytes):
        reject_if_upload_too_large(len(content))
        record = self.storage.get(geo_id)
        if record.asset_kind != "point_grid_csv":
            raise ManualTrainingError(
                "This dataset expects a vector lineament upload, not a CSV.",
                code="ASSET_KIND",
            )
        if record.original_relpath:
            raise ManualTrainingError(
                "An original file is already stored for this dataset. "
                "Create a new geological dataset for another upload "
                "(catalogue ids are never overwritten).",
                code="ORIGINAL_IMMUTABLE",
            )
        safe = self.storage.safe_filename(filename)
        original = self.storage.dataset_dir(geo_id) / "original" / safe
        original.write_bytes(content)
        working_csv = self.storage.dataset_dir(geo_id) / "working" / "layer.csv"
        shutil.copyfile(original, working_csv)

        inspect = inspect_point_grid_bytes(content, filename=safe)
        self.storage.write_working_json(geo_id, "inspect.json", inspect)

        record.original_filename = safe
        record.uploaded_at = _utc_now()
        record.content_sha256 = _sha256(content)
        record.original_relpath = f"original/{safe}"
        record.working_relpath = "working/layer.csv"
        record.inspect_report = inspect
        record.validation_status = "inspected"
        record.coverage_bbox = inspect.get("coverage_bbox")
        record.grid_spacing_x = inspect.get("dominant_spacing_x")
        record.grid_spacing_y = inspect.get("dominant_spacing_y")
        record.grid_spacing_units = "file_units"
        if inspect.get("detected_columns"):
            cols = inspect["detected_columns"]
            record.x_column = cols.get("x", 0)
            record.y_column = cols.get("y", 1)
            record.z_column = cols.get("z", 2)
        self.storage.save(record)
        self.storage.append_event(
            {
                "event": "uploaded",
                "geo_id": geo_id,
                "at": record.uploaded_at,
                "sha256": record.content_sha256,
                "filename": safe,
            }
        )
        return record

    def upload_lineament(self, geo_id: str, *, filename: str, content: bytes):
        reject_if_upload_too_large(len(content))
        record = self.storage.get(geo_id)
        if record.asset_kind != "vector_lineament":
            raise ManualTrainingError(
                "This dataset expects a point-grid CSV, not a lineament vector.",
                code="ASSET_KIND",
            )
        if record.original_relpath:
            raise ManualTrainingError(
                "An original file is already stored for this dataset. "
                "Create a new geological dataset for another upload.",
                code="ORIGINAL_IMMUTABLE",
            )
        safe = self.storage.safe_filename(filename)
        original = self.storage.dataset_dir(geo_id) / "original" / safe
        original.write_bytes(content)

        lower = safe.lower()
        if lower.endswith(".gpkg"):
            geojson_bytes = load_gpkg_as_geojson(original)
            fmt = "gpkg"
        else:
            geojson_bytes, fmt = try_load_vector_archive(content, filename=safe)

        working = self.storage.dataset_dir(geo_id) / "working" / "lineaments.geojson"
        working.write_bytes(geojson_bytes)
        inspect = inspect_lineament_geojson(geojson_bytes, filename=safe)
        inspect["source_format"] = fmt
        self.storage.write_working_json(geo_id, "inspect.json", inspect)

        record.original_filename = safe
        record.uploaded_at = _utc_now()
        record.content_sha256 = _sha256(content)
        record.original_relpath = f"original/{safe}"
        record.working_relpath = "working/lineaments.geojson"
        record.inspect_report = inspect
        record.validation_status = "inspected"
        record.coverage_bbox = inspect.get("coverage_bbox")
        record.geometry_type = ",".join(inspect.get("geometry_types") or []) or None
        record.feature_count = inspect.get("feature_count")
        record.measurement_type = MEASUREMENT_LINEAMENT
        record.lineament_method = inspect.get("method") or {}
        self.storage.save(record)
        self.storage.append_event(
            {
                "event": "uploaded_lineament",
                "geo_id": geo_id,
                "at": record.uploaded_at,
                "sha256": record.content_sha256,
                "filename": safe,
                "format": fmt,
            }
        )
        return record

    def declare(self, geo_id: str, body: dict[str, Any]):
        record = self.storage.get(geo_id)
        if "measurement_type" in body:
            mt = canonicalize_measurement_type(body.get("measurement_type"))
            record.measurement_type = mt
        if "measurement_description" in body:
            record.measurement_description = str(body.get("measurement_description") or "")
        if "description" in body:
            record.description = str(body.get("description") or "")
        if "source_client" in body:
            record.source_client = str(body.get("source_client") or "")
        if "notes" in body:
            record.notes = str(body.get("notes") or "")
        for key in ("x_column", "y_column", "z_column"):
            if key in body:
                setattr(record, key, body.get(key))
        if "crs" in body:
            record.crs = (body.get("crs") or None) and str(body.get("crs")).strip() or None
        if "working_crs" in body:
            wc = body.get("working_crs")
            record.working_crs = str(wc).strip() if wc else None
        if "units" in body:
            u = body.get("units")
            record.units = str(u).strip() if u else None
        if "z_to_metres" in body:
            ztm = body.get("z_to_metres")
            record.z_to_metres = float(ztm) if ztm is not None else None
        if "grid_spacing_units" in body:
            record.grid_spacing_units = body.get("grid_spacing_units")
        if "nodata_policy" in body and isinstance(body.get("nodata_policy"), dict):
            record.nodata_policy = NodataPolicy.from_dict(body["nodata_policy"])
        if "provenance" in body and isinstance(body.get("provenance"), dict):
            record.provenance = dict(body["provenance"])
        self.storage.save(record)
        self.storage.append_event(
            {
                "event": "declared",
                "geo_id": geo_id,
                "at": _utc_now(),
                "measurement_type": record.measurement_type,
                "crs": record.crs,
                "units": record.units,
            }
        )
        return record

    def validate(self, geo_id: str) -> tuple[Any, dict[str, Any]]:
        record = self.storage.get(geo_id)
        original = self.storage.original_path(record)
        if original is None or not original.exists():
            raise ManualTrainingError(
                "Upload a file before validating.",
                code="UPLOAD_REQUIRED",
            )

        if record.asset_kind == "vector_lineament":
            if not record.crs:
                raise ManualTrainingError(
                    "Declare CRS before validating lineaments.",
                    code="CRS_REQUIRED",
                )
            working = self.storage.resolve_under(geo_id, "working/lineaments.geojson")
            raw = working.read_bytes() if working.exists() else original.read_bytes()
            report = validate_lineament_geojson(
                raw, filename=record.original_filename, crs=record.crs
            )
        else:
            if not record.crs:
                raise ManualTrainingError(
                    "Declare CRS before validating.",
                    code="CRS_REQUIRED",
                )
            if not record.measurement_type:
                raise ManualTrainingError(
                    "Declare measurement_type before validating.",
                    code="MEASUREMENT_REQUIRED",
                )
            working = self.storage.working_path(record)
            content = (
                working.read_bytes()
                if working and working.exists()
                else original.read_bytes()
            )
            report = validate_declared_point_grid(
                content,
                filename=record.original_filename or "layer.csv",
                measurement_type=record.measurement_type,
                crs=record.crs,
                working_crs=record.working_crs,
                units=record.units,
                x_column=record.x_column,
                y_column=record.y_column,
                value_column=record.z_column,
            )
            # Refresh spacing / bbox from validation when available
            if report.get("overall") != "FAIL":
                insp = record.inspect_report or {}
                record.coverage_bbox = record.coverage_bbox or insp.get("coverage_bbox")
                record.grid_spacing_x = record.grid_spacing_x or insp.get(
                    "dominant_spacing_x"
                )
                record.grid_spacing_y = record.grid_spacing_y or insp.get(
                    "dominant_spacing_y"
                )

        self.storage.write_working_json(geo_id, "validate.json", report)
        record.validation_report = report
        if report.get("overall") == "FAIL":
            record.validation_status = "failed"
        else:
            record.validation_status = "validated"
        self.storage.save(record)
        self.storage.append_event(
            {
                "event": "validated",
                "geo_id": geo_id,
                "at": _utc_now(),
                "overall": report.get("overall"),
            }
        )
        return record, report

    def set_activation(
        self,
        geo_id: str,
        *,
        activation_status: str,
        acknowledged_warnings: list[str] | None = None,
    ):
        record = self.storage.get(geo_id)
        status = (activation_status or "").strip()
        if status not in {"inactive", "reporting_only", "approved"}:
            raise ManualTrainingError(
                "activation_status must be inactive, reporting_only, or approved.",
                code="ACTIVATION_STATUS",
            )
        if status == "inactive":
            record.activation_status = "inactive"
            self.storage.save(record)
            return record

        if record.validation_status != "validated":
            raise ManualTrainingError(
                "Validate the dataset before activation.",
                code="ACTIVATION_NOT_VALIDATED",
            )
        report = record.validation_report or {}
        if not report.get("can_activate_reporting") and report.get("overall") == "FAIL":
            raise ManualTrainingError(
                "Validation failed; cannot activate.",
                code="ACTIVATION_BLOCKED",
            )
        # WARN acknowledgements
        warn_names = [
            c.get("name")
            for c in (report.get("checks") or [])
            if c.get("status") == "WARN"
        ]
        ack = set(acknowledged_warnings or [])
        missing = [w for w in warn_names if w and w not in ack]
        if missing and status in {"reporting_only", "approved"}:
            raise ManualTrainingError(
                "Acknowledge validation warnings before activation: "
                + ", ".join(missing),
                code="ACTIVATION_WARNINGS",
            )
        if status == "approved":
            # Milestone: approved is catalogue-only; never means live inference.
            record.activation_status = "approved"
            record.notes = (
                (record.notes + "\n" if record.notes else "")
                + "approved = catalogue approval for offline/reporting; "
                "not live 13-channel inference."
            ).strip()
        else:
            record.activation_status = "reporting_only"
        self.storage.save(record)
        self.storage.append_event(
            {
                "event": "activation",
                "geo_id": geo_id,
                "at": _utc_now(),
                "activation_status": record.activation_status,
                "acknowledged_warnings": list(ack),
            }
        )
        return record

    def coverage_query(
        self,
        *,
        aoi_bbox: list[float],
        aoi_crs: str | None = None,
        measurement_type: str | None = None,
        require_validated: bool = True,
        require_activated: bool = True,
    ) -> dict[str, Any]:
        records, _ = self.storage.list(limit=10_000, offset=0)
        return match_aoi(
            records,
            aoi_bbox=aoi_bbox,
            measurement_type=measurement_type,
            require_validated=require_validated,
            require_activated=require_activated,
            aoi_crs=aoi_crs,
            storage=self.storage,
        )
