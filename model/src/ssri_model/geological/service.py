"""Orchestration for geological catalogue upload / declare / validate / activate."""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
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
    is_tmi_measurement,
)
from ssri_model.geological.durable import write_bytes_atomic
from ssri_model.geological.storage import GeologicalStorage
from ssri_model.geological.tmi import process_tmi_to_grid
from ssri_model.geological.validate import validate_declared_point_grid
from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.manual_training.upload_limits import reject_if_upload_too_large

_SURVEY_PROVENANCE_KEYS = (
    "survey_date",
    "survey_method",
    "sampling_spacing",
    "processing_history",
    "source_organization",
    "geographic_coverage",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _extract_single_csv_from_zip(content: bytes) -> tuple[bytes, str]:
    """Extract exactly one CSV from a zip; reject path traversal and multi-CSV."""
    import io
    import zipfile

    if not zipfile.is_zipfile(io.BytesIO(content)):
        raise ManualTrainingError(
            "Upload is not a valid ZIP archive.",
            code="ZIP_INVALID",
        )
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        members = [
            n
            for n in zf.namelist()
            if not n.endswith("/") and not n.split("/")[-1].startswith(".")
        ]
        for name in members:
            # Path traversal / absolute paths
            parts = name.replace("\\", "/").split("/")
            if name.startswith("/") or ".." in parts:
                raise ManualTrainingError(
                    f"ZIP entry '{name}' has an unsafe path.",
                    code="ZIP_PATH_TRAVERSAL",
                )
        csvs = [n for n in members if n.lower().endswith(".csv")]
        if len(csvs) != 1:
            raise ManualTrainingError(
                f"ZIPCSV must contain exactly one CSV file (found {len(csvs)}).",
                code="ZIPCSV_COUNT",
            )
        name = csvs[0]
        data = zf.read(name)
        return data, name.split("/")[-1]


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
        write_bytes_atomic(original, content)

        # ZIPCSV: preserve original zip; extract a single CSV into working/.
        csv_bytes = content
        working_name = "layer.csv"
        lower = safe.lower()
        if lower.endswith(".zip"):
            csv_bytes, working_name = _extract_single_csv_from_zip(content)

        working_csv = self.storage.dataset_dir(geo_id) / "working" / "layer.csv"
        write_bytes_atomic(working_csv, csv_bytes)

        inspect = inspect_point_grid_bytes(csv_bytes, filename=working_name)
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
        write_bytes_atomic(original, content)

        lower = safe.lower()
        if lower.endswith(".gpkg"):
            geojson_bytes = load_gpkg_as_geojson(original)
            fmt = "gpkg"
        else:
            geojson_bytes, fmt = try_load_vector_archive(content, filename=safe)

        working = self.storage.dataset_dir(geo_id) / "working" / "lineaments.geojson"
        write_bytes_atomic(working, geojson_bytes)
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
            merged = dict(record.provenance or {})
            merged.update(dict(body["provenance"]))
            record.provenance = merged
        # Survey metadata fields — store only when provided; never fabricate.
        prov = dict(record.provenance or {})
        for key in _SURVEY_PROVENANCE_KEYS:
            if key in body:
                val = body.get(key)
                if val is None or (isinstance(val, str) and not val.strip()):
                    prov[key] = "unknown"
                else:
                    prov[key] = val
        if "source_organization" in body and body.get("source_organization"):
            if not record.source_client:
                record.source_client = str(body["source_organization"])
        record.provenance = prov
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
                provenance=record.provenance,
            )
            # Refresh spacing / bbox from validation when available
            if report.get("overall") != "FAIL":
                insp = record.inspect_report or {}
                record.coverage_bbox = (
                    report.get("coverage_bbox")
                    or record.coverage_bbox
                    or insp.get("coverage_bbox")
                )
                record.grid_spacing_x = record.grid_spacing_x or insp.get(
                    "dominant_spacing_x"
                )
                record.grid_spacing_y = record.grid_spacing_y or insp.get(
                    "dominant_spacing_y"
                )
            if report.get("feature_compatibility"):
                record.feature_compatibility = dict(report["feature_compatibility"])
                if record.processing_status == "not_started":
                    record.processing_status = "feature_compatibility_review"

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
        if status == "approved" and is_tmi_measurement(record.measurement_type):
            raise ManualTrainingError(
                "Client TMI cannot be approved into the Stage 2.5 feature stack. "
                "Use reporting_only for catalogue visibility, or mark "
                "accepted_with_limitations after feature-compatibility review.",
                code="TMI_NOT_APPROVABLE",
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

    def process_tmi(
        self,
        geo_id: str,
        *,
        resolution: float,
        nodata: float = -9999.0,
    ):
        """Grid validated TMI points into a derived GeoTIFF (original untouched)."""
        record = self.storage.get(geo_id)
        if not is_tmi_measurement(record.measurement_type):
            raise ManualTrainingError(
                "Processing is only available for total_magnetic_intensity datasets.",
                code="NOT_TMI",
            )
        if record.validation_status != "validated":
            raise ManualTrainingError(
                "Validate the TMI dataset before processing. Failed validation blocks processing.",
                code="PROCESS_REQUIRES_VALIDATED",
            )
        report = record.validation_report or {}
        if report.get("overall") == "FAIL" or not report.get("can_process", True):
            if report.get("overall") == "FAIL":
                raise ManualTrainingError(
                    "Validation failed; processing is blocked.",
                    code="PROCESS_BLOCKED",
                )
            if report.get("can_process") is False:
                raise ManualTrainingError(
                    "Dataset is not suitable for gridding yet "
                    "(insufficient spatial coverage or points).",
                    code="PROCESS_NOT_SUITABLE",
                )
        original = self.storage.original_path(record)
        if original is None or not original.exists():
            raise ManualTrainingError(
                "Original upload missing.",
                code="UPLOAD_REQUIRED",
            )
        if not record.crs:
            raise ManualTrainingError("CRS required for processing.", code="CRS_REQUIRED")

        # Prefer working CSV (ZIPCSV extracts here); never mutate original bytes.
        working = self.storage.working_path(record)
        if working and working.exists():
            csv_content = working.read_bytes()
        elif (original.name or "").lower().endswith(".zip"):
            csv_content, _ = _extract_single_csv_from_zip(original.read_bytes())
        else:
            csv_content = original.read_bytes()

        record.processing_status = "processing"
        self.storage.save(record)

        out_tif = self.storage.dataset_dir(geo_id) / "working" / "derived" / "tmi_grid.tif"
        prov_path = (
            self.storage.dataset_dir(geo_id) / "working" / "derived" / "tmi_process.json"
        )
        try:
            proc = process_tmi_to_grid(
                csv_content,
                out_tif=out_tif,
                provenance_json=prov_path,
                source_geo_id=geo_id,
                crs=record.crs,
                units=record.units,
                resolution=float(resolution),
                x_column=record.x_column,
                y_column=record.y_column,
                z_column=record.z_column,
                nodata=float(nodata),
            )
        except Exception as exc:
            record.processing_status = "processing_failed"
            record.processing_report = {
                "error": str(exc),
                "failed_at": _utc_now(),
            }
            self.storage.save(record)
            self.storage.append_event(
                {
                    "event": "processing_failed",
                    "geo_id": geo_id,
                    "at": _utc_now(),
                    "error": str(exc),
                }
            )
            raise ManualTrainingError(
                f"TMI processing failed: {exc}",
                code="PROCESS_FAILED",
            ) from exc

        record.processing_status = "processed"
        record.processing_report = proc
        record.derived_relpath = "working/derived/tmi_grid.tif"
        if proc.get("feature_compatibility"):
            record.feature_compatibility = dict(proc["feature_compatibility"])
        self.storage.save(record)
        self.storage.append_event(
            {
                "event": "processed",
                "geo_id": geo_id,
                "at": _utc_now(),
                "derived": record.derived_relpath,
                "method": proc.get("processing_method"),
            }
        )
        return record, proc

    def set_compatibility_decision(
        self,
        geo_id: str,
        *,
        decision: str,
        notes: str = "",
    ):
        """Operator decision after feature-compatibility review (not training-ready)."""
        record = self.storage.get(geo_id)
        if decision not in {"accepted_with_limitations", "rejected", "feature_compatibility_review"}:
            raise ManualTrainingError(
                "decision must be accepted_with_limitations, rejected, "
                "or feature_compatibility_review.",
                code="COMPATIBILITY_DECISION",
            )
        if is_tmi_measurement(record.measurement_type) and decision == "accepted_with_limitations":
            # Explicit: accepted for catalogue / research review only.
            record.processing_status = "accepted_with_limitations"
            record.notes = (
                (record.notes + "\n" if record.notes else "")
                + "accepted_with_limitations: not Stage 2.5 training-ready; "
                "not live magnetics channel; NOT_VALIDATED."
                + (f" {notes}" if notes else "")
            ).strip()
        else:
            record.processing_status = decision  # type: ignore[assignment]
            if notes:
                record.notes = (
                    (record.notes + "\n" if record.notes else "") + notes
                ).strip()
        record.scientific_validation_status = "NOT_VALIDATED"
        self.storage.save(record)
        self.storage.append_event(
            {
                "event": "compatibility_decision",
                "geo_id": geo_id,
                "at": _utc_now(),
                "decision": decision,
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
