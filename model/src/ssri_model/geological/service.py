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
        from ssri_model.geological.abeokuta_tmi import (
            apply_abeokuta_tmi_defaults,
            looks_like_abeokuta_filename,
        )

        record = self.storage.get(geo_id)
        apply_preset = bool(body.get("apply_abeokuta_tmi_preset")) or looks_like_abeokuta_filename(
            record.original_filename or record.display_name
        )
        if apply_preset:
            # Authoritative Abeokuta owner metadata — do not re-prompt for columns/CRS.
            body = apply_abeokuta_tmi_defaults(body)

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
            # Refresh spacing / bbox from validation when available.
            # Geographic coverage from inspect remains usable even when overall=FAIL
            # so the map can show an honest footprint without inventing a location.
            insp = record.inspect_report or {}
            coverage = (
                report.get("coverage_bbox")
                or record.coverage_bbox
                or insp.get("coverage_bbox")
            )
            if coverage:
                record.coverage_bbox = coverage
            if report.get("overall") != "FAIL":
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
            # Persist verified WGS84 display footprint for map overlays (never invent).
            crs_ver = report.get("crs_verification") or {}
            display_extent = crs_ver.get("display_extent")
            if (
                isinstance(display_extent, list)
                and len(display_extent) == 4
                and all(isinstance(v, (int, float)) for v in display_extent)
            ):
                prov = dict(record.provenance or {})
                prov["display_bbox_wgs84"] = [float(v) for v in display_extent]
                record.provenance = prov
            elif coverage and (
                (record.crs or "").upper().replace(" ", "").endswith("4326")
                or (record.crs or "").upper() == "WGS84"
            ):
                prov = dict(record.provenance or {})
                prov["display_bbox_wgs84"] = [float(v) for v in coverage]
                record.provenance = prov

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

    def preview_tmi(self, geo_id: str, *, max_points: int = 5000) -> dict[str, Any]:
        """Sampled GeoJSON / survey-local preview for map or local scatter."""
        from ssri_model.geological.abeokuta_tmi import looks_like_abeokuta_filename
        from ssri_model.geological.tmi import build_tmi_preview

        record = self.storage.get(geo_id)
        is_tmi = is_tmi_measurement(record.measurement_type) or looks_like_abeokuta_filename(
            record.original_filename or record.display_name
        )
        if record.measurement_type and not is_tmi:
            raise ManualTrainingError(
                "Preview is available for TMI / Abeokuta magnetic surveys.",
                code="NOT_TMI",
            )
        original = self.storage.original_path(record)
        if original is None or not original.exists():
            raise ManualTrainingError("Upload a file before preview.", code="UPLOAD_REQUIRED")
        working = self.storage.working_path(record)
        if working and working.exists():
            content = working.read_bytes()
        elif (original.name or "").lower().endswith(".zip"):
            content, _ = _extract_single_csv_from_zip(original.read_bytes())
        else:
            content = original.read_bytes()
        crs = record.crs or "EPSG:4326"
        prov = dict(record.provenance or {})
        return build_tmi_preview(
            content,
            crs=crs,
            x_column=record.x_column or "X",
            y_column=record.y_column or "Y",
            z_column=record.z_column or "Z",
            max_points=max_points,
            processing_crs=record.working_crs or prov.get("processing_crs"),
            display_crs=prov.get("display_crs") or "EPSG:4326",
        )

    def _load_tmi_csv_bytes(self, record) -> bytes:
        original = self.storage.original_path(record)
        if original is None or not original.exists():
            raise ManualTrainingError(
                "Original upload missing.",
                code="UPLOAD_REQUIRED",
            )
        working = self.storage.working_path(record)
        if working and working.exists():
            return working.read_bytes()
        if (original.name or "").lower().endswith(".zip"):
            content, _ = _extract_single_csv_from_zip(original.read_bytes())
            return content
        return original.read_bytes()

    def _require_validated_tmi(self, record):
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
        if not record.crs:
            raise ManualTrainingError("CRS required for processing.", code="CRS_REQUIRED")

    def process_tmi(
        self,
        geo_id: str,
        *,
        resolution: float,
        nodata: float = -9999.0,
    ):
        """Grid validated TMI points into a derived GeoTIFF (original untouched).

        For Abeokuta Sheet 260 (EPSG:32632 source), points are reprojected to
        EPSG:32631 for metric gridding; original CSV easting/northing/TMI stay immutable.
        """
        record = self.storage.get(geo_id)
        self._require_validated_tmi(record)
        csv_content = self._load_tmi_csv_bytes(record)

        record.processing_status = "processing"
        self.storage.save(record)

        out_tif = self.storage.dataset_dir(geo_id) / "working" / "derived" / "tmi_grid.tif"
        prov_path = (
            self.storage.dataset_dir(geo_id) / "working" / "derived" / "tmi_process.json"
        )
        try:
            from ssri_model.geological.abeokuta_tmi import looks_like_abeokuta_filename
            from ssri_model.geological.tmi import _is_utm32n

            use_pub = _is_utm32n(record.crs) or looks_like_abeokuta_filename(
                record.original_filename or record.display_name
            )
            if use_pub:
                proc = self._process_abeokuta_tmi_grid(
                    geo_id,
                    record,
                    csv_content,
                    out_tif=out_tif,
                    provenance_json=prov_path,
                    resolution=float(resolution),
                    nodata=float(nodata),
                )
            else:
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
        except ManualTrainingError:
            raise
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

    def _process_abeokuta_tmi_grid(
        self,
        geo_id: str,
        record,
        csv_content: bytes,
        *,
        out_tif,
        provenance_json,
        resolution: float,
        nodata: float,
    ) -> dict[str, Any]:
        import json

        import numpy as np

        from ssri_model.geological.abeokuta_crs import (
            reproject_points_for_processing,
            verify_abeokuta_crs_pipeline,
        )
        from ssri_model.geological.magnetic_processing import (
            OPERATION_TMI,
            SOFTWARE_ID,
            SOFTWARE_VERSION,
            append_processing_history,
            build_operation_provenance,
            grid_points_to_array,
            grid_stats,
            sha256_array,
            sha256_file,
            source_lattice_reconciliation,
            write_geotiff,
            write_preview_png,
        )
        from ssri_model.geological.tmi import (
            assess_feature_compatibility,
            parse_tmi_points,
            _spatial_assessment,
            _tmi_stats,
        )

        parsed = parse_tmi_points(
            csv_content,
            x_column=record.x_column,
            y_column=record.y_column,
            z_column=record.z_column,
        )
        if not parsed.get("ok") or not parsed["xs"]:
            raise ValueError(parsed.get("error") or "No points to process.")

        xs = np.asarray(parsed["xs"], dtype=np.float64)
        ys = np.asarray(parsed["ys"], dtype=np.float64)
        zs = np.asarray(parsed["zs"], dtype=np.float64)
        source_crs = record.crs or "EPSG:32632"
        processing_crs = record.working_crs or "EPSG:32631"
        display_crs = str((record.provenance or {}).get("display_crs") or "EPSG:4326")

        verification = verify_abeokuta_crs_pipeline(
            xs, ys, zs, source_crs=source_crs, processing_crs=processing_crs, display_crs=display_crs
        )
        if not verification.get("ok"):
            raise ManualTrainingError(
                "CRS verification failed; cannot grid until the publication CRS "
                "pipeline is consistent with the uploaded coordinates.",
                code="CRS_VERIFICATION_FAILED",
            )

        source_lattice = source_lattice_reconciliation(xs, ys, spacing=100.0)
        e31, n31, xform_meta = reproject_points_for_processing(
            xs, ys, source_crs=source_crs, processing_crs=processing_crs
        )
        res = float(resolution)
        if res < 1.0:
            res = 100.0
        grid, mask, gmeta = grid_points_to_array(
            e31, n31, zs, resolution=res, nodata=nodata, method="scatter_bin"
        )
        gmeta["resolution"] = gmeta["resolution_x_m"]
        write_geotiff(
            out_tif,
            grid,
            gmeta,
            crs=processing_crs,
            nodata=nodata,
            tags={"OPERATION": OPERATION_TMI, "SOURCE_CRS": source_crs},
        )
        png = out_tif.with_name("tmi_preview.png")
        preview_stats = write_preview_png(
            png, grid, mask, title="TMI (Sheet 260)", cmap="RdBu_r", units="nT"
        )

        derived_dir = self.storage.dataset_dir(geo_id) / "working" / "derived"
        history_path = derived_dir / "processing_history.json"
        input_sha = record.content_sha256
        out_paths = {
            "geotiff": "working/derived/tmi_grid.tif",
            "preview_png": "working/derived/tmi_preview.png",
            "arrays_npz": "working/derived/tmi_grid_arrays.npz",
        }
        out_checksums = {
            "geotiff": sha256_file(out_tif),
            "preview_png": sha256_file(png),
            "grid_array": sha256_array(grid),
            "mask_array": sha256_array(mask.astype(np.uint8)),
        }
        gridding_reconciliation = {
            "source_crs_lattice": source_lattice,
            "processing_crs_scatter_bin": {
                k: gmeta.get(k)
                for k in (
                    "original_observation_count",
                    "expected_lattice_cells",
                    "observed_lattice_cell_count",
                    "empty_lattice_positions",
                    "cells_populated_by_direct_observations",
                    "cells_populated_by_interpolation",
                    "cells_remaining_nodata",
                    "collision_cells_mean_aggregated",
                    "collision_policy",
                    "method",
                    "resolution_x_m",
                    "resolution_y_m",
                    "width",
                    "height",
                    "xmin",
                    "ymin",
                    "xmax",
                    "ymax",
                )
            },
            "reconciliation_note": (
                f"Inspect missing_lattice_cells={source_lattice['empty_lattice_positions']} "
                "counts empty positions on the source-CRS unique-X×unique-Y lattice. "
                f"Processing-CRS scatter-bin NoData={gmeta.get('cells_remaining_nodata')} "
                "on a regular metre grid after EPSG:32632→32631. These differ because the "
                "UTM zone change warps the lattice (cell collisions + empty bins). "
                "Nearest-neighbour fill previously reported 0 NoData by interpolating every cell — "
                "that fabricated values for empty positions and is not the default."
            ),
        }
        entry = build_operation_provenance(
            operation=OPERATION_TMI,
            op_meta={
                "definition": "Gridded TMI observations",
                "units": "nT",
                "gridding": gmeta,
                "transform": xform_meta,
                "crs_verification_overall": verification.get("overall"),
            },
            params={"resolution_m": res, "nodata": nodata},
            input_artifact=record.original_relpath or "original/sheet_260_Abeokuta.csv",
            input_checksum=input_sha,
            output_artifacts=out_paths,
            output_checksums=out_checksums,
            source_crs=source_crs,
            processing_crs=processing_crs,
            grid_spacing={"dx": gmeta["resolution_x_m"], "dy": gmeta["resolution_y_m"]},
            nodata_policy={
                "missing_cells": "NoData",
                "interpolation": "none_in_scatter_bin",
                "collision_aggregation": "mean_of_observations",
            },
            statistics=grid_stats(grid, mask),
        )
        entry["gridding_reconciliation"] = gridding_reconciliation
        entry["raw_source_unmodified"] = True
        entry["algorithm"] = SOFTWARE_ID
        entry["software_version"] = SOFTWARE_VERSION
        history = append_processing_history(history_path, entry)

        report = {
            "source_dataset_id": geo_id,
            "processing_method": gmeta["method"],
            "parameters": {"resolution_m": res, "nodata": nodata},
            "crs": processing_crs,
            "source_crs": source_crs,
            "processing_crs": processing_crs,
            "display_crs": display_crs,
            "crs_verification": verification,
            "coordinate_transform": xform_meta,
            "gridding_reconciliation": gridding_reconciliation,
            "gridding_provenance": gmeta,
            "resolution": res,
            "nodata": nodata,
            "units": (record.units or "").strip() or "nT",
            "grid": {
                k: gmeta[k]
                for k in (
                    "width",
                    "height",
                    "xmin",
                    "ymin",
                    "xmax",
                    "ymax",
                    "method",
                    "nodata_cells",
                    "filled_cells",
                    "cells_populated_by_direct_observations",
                    "cells_populated_by_interpolation",
                    "cells_remaining_nodata",
                    "collision_cells_mean_aggregated",
                )
                if k in gmeta
            },
            "tmi_statistics": _tmi_stats(parsed["zs"]),
            "grid_statistics": preview_stats,
            "derived_relpath": "working/derived/tmi_grid.tif",
            "preview_relpath": "working/derived/tmi_preview.png",
            "processing_history": history,
            "software": SOFTWARE_ID,
            "software_version": SOFTWARE_VERSION,
            "processed_at": _utc_now(),
            "raw_source_unmodified": True,
            "geophysical_transforms_applied": [],
            "notes": [
                "Gridded in EPSG:32631 after verified transform from EPSG:32632.",
                "scatter_bin leaves empty cells as NoData; collisions use observation mean.",
                "Source-CRS missing lattice ≠ processing-CRS NoData (UTM warp).",
                "No RTE/derivatives in this base step — run magnetic operations explicitly.",
                "Original CSV X/Y/Z unchanged.",
            ],
            "feature_compatibility": assess_feature_compatibility(
                crs=processing_crs,
                units=record.units,
                spatial=_spatial_assessment(e31.tolist(), n31.tolist()),
                tmi_stats=_tmi_stats(parsed["zs"]),
            ),
            "scientific_validation_status": "NOT_VALIDATED",
        }
        provenance_json.parent.mkdir(parents=True, exist_ok=True)
        provenance_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        np.savez_compressed(
            derived_dir / "tmi_grid_arrays.npz",
            grid=grid,
            mask=mask.astype(np.uint8),
            dx=np.array([gmeta["resolution_x_m"]], dtype=np.float64),
            dy=np.array([gmeta["resolution_y_m"]], dtype=np.float64),
            xmin=np.array([gmeta["xmin"]], dtype=np.float64),
            ymax=np.array([gmeta["ymax"]], dtype=np.float64),
            nodata=np.array([nodata], dtype=np.float64),
        )
        return report

    def list_magnetic_products(self, geo_id: str) -> dict[str, Any]:
        import json

        from ssri_model.geological.magnetic_processing import (
            SUPPORTED_OPERATIONS,
            operation_catalog,
            publication_comparison_notes,
        )

        record = self.storage.get(geo_id)
        derived = self.storage.dataset_dir(geo_id) / "working" / "derived"
        history_path = derived / "processing_history.json"
        history: list[Any] = []
        if history_path.exists():
            try:
                history = json.loads(history_path.read_text(encoding="utf-8"))
            except Exception:
                history = []
        catalog = {c["operation"]: c for c in operation_catalog()}
        products = []
        for op in SUPPORTED_OPERATIONS:
            tif = derived / f"{op}.tif" if op != "tmi" else derived / "tmi_grid.tif"
            png = derived / f"{op}_preview.png" if op != "tmi" else derived / "tmi_preview.png"
            raps = derived / "raps.json"
            raps_png = derived / "raps_preview.png"
            is_raps = op == "radially_averaged_power_spectrum"
            products.append(
                {
                    "operation": op,
                    **(catalog.get(op) or {}),
                    "geotiff_exists": tif.exists() if not is_raps else False,
                    "preview_exists": (raps_png.exists() if is_raps else png.exists()),
                    "raps_exists": raps.exists() if is_raps else False,
                    "geotiff_relpath": (
                        f"working/derived/{tif.name}" if tif.exists() and not is_raps else None
                    ),
                    "preview_relpath": (
                        f"working/derived/{raps_png.name}"
                        if is_raps and raps_png.exists()
                        else (f"working/derived/{png.name}" if png.exists() and not is_raps else None)
                    ),
                    "raps_relpath": (
                        f"working/derived/{raps.name}" if is_raps and raps.exists() else None
                    ),
                }
            )
        lineament_dir = derived / "lineaments"
        lineament_qc = None
        if (lineament_dir / "lineament_extraction_qc.json").exists():
            try:
                lineament_qc = json.loads(
                    (lineament_dir / "lineament_extraction_qc.json").read_text(encoding="utf-8")
                )
            except Exception:
                lineament_qc = None
        products.append(
            {
                "operation": "candidate_lineament_extraction",
                "title": "Candidate magnetic lineaments",
                "summary": (
                    "Edge-enhanced TMI ridge extraction. Candidates are NOT confirmed "
                    "faults or fractures. used_in_inference=false."
                ),
                "units": "vector + m/m² + m",
                "geotiff_exists": (lineament_dir / "lineament_density.tif").exists(),
                "preview_exists": (
                    lineament_dir / "candidate_lineaments_preview.png"
                ).exists(),
                "geojson_exists": (lineament_dir / "candidate_lineaments.geojson").exists(),
                "geotiff_relpath": (
                    "working/derived/lineaments/lineament_density.tif"
                    if (lineament_dir / "lineament_density.tif").exists()
                    else None
                ),
                "preview_relpath": (
                    "working/derived/lineaments/candidate_lineaments_preview.png"
                    if (lineament_dir / "candidate_lineaments_preview.png").exists()
                    else None
                ),
                "geojson_relpath": (
                    "working/derived/lineaments/candidate_lineaments.geojson"
                    if (lineament_dir / "candidate_lineaments.geojson").exists()
                    else None
                ),
                "qc": lineament_qc,
            }
        )
        prov = dict(record.provenance or {})
        proc = dict(record.processing_report or {})
        inspect = dict(record.inspect_report or {})
        raps_payload = None
        raps_path = derived / "raps.json"
        if raps_path.exists():
            try:
                raps_payload = json.loads(raps_path.read_text(encoding="utf-8"))
            except Exception:
                raps_payload = None
        return {
            "geo_id": geo_id,
            "supported_operations": list(SUPPORTED_OPERATIONS),
            "operation_catalog": operation_catalog(),
            "candidate_lineaments": prov.get("candidate_lineaments"),
            "products": products,
            "processing_history": history,
            "gridding_reconciliation": proc.get("gridding_reconciliation"),
            "gridding_provenance": proc.get("gridding_provenance"),
            "inspect_missing_lattice_cells": inspect.get("missing_lattice_cells"),
            "inspect_expected_full_grid_cells": inspect.get("expected_full_grid_cells"),
            "crs_roles": {
                "source_crs": record.crs,
                "processing_crs": record.working_crs or prov.get("processing_crs"),
                "display_crs": prov.get("display_crs") or "EPSG:4326",
                "crs_declaration_history": prov.get("crs_declaration_history"),
            },
            "publication_magnetic_params": prov.get("publication_magnetic_params"),
            "publication_comparison": publication_comparison_notes(),
            "raps": raps_payload,
            "scientific_validation_status": "NOT_VALIDATED",
            "tmi_statistics": (record.validation_report or {}).get("tmi_statistics"),
            "spatial": (record.validation_report or {}).get("spatial"),
            "grid_spacing_x": record.grid_spacing_x,
            "grid_spacing_y": record.grid_spacing_y,
            "not_hazard_labels": True,
        }

    def run_magnetic_operation(
        self,
        geo_id: str,
        *,
        operation: str,
        params: dict[str, Any] | None = None,
        resolution: float | None = None,
        nodata: float = -9999.0,
    ):
        """Run one publication-guided magnetic operation; record history."""
        import json

        import numpy as np

        from ssri_model.geological.magnetic_processing import (
            OPERATION_RAPS,
            OPERATION_TMI,
            SOFTWARE_ID,
            SOFTWARE_VERSION,
            SUPPORTED_OPERATIONS,
            append_processing_history,
            build_operation_provenance,
            grid_stats,
            merge_magnetic_params,
            publication_comparison_notes,
            run_magnetic_operation,
            sha256_array,
            sha256_file,
            write_geotiff,
            write_preview_png,
            write_raps_chart_png,
        )

        record = self.storage.get(geo_id)
        self._require_validated_tmi(record)
        op = (operation or "").strip().lower()
        if op not in SUPPORTED_OPERATIONS:
            raise ManualTrainingError(
                f"Unsupported operation '{operation}'.",
                code="MAGNETIC_OPERATION",
            )

        mag_params = merge_magnetic_params(
            {
                **(dict((record.provenance or {}).get("publication_magnetic_params") or {})),
                **(params or {}),
            }
        )

        derived = self.storage.dataset_dir(geo_id) / "working" / "derived"
        npz_path = derived / "tmi_grid_arrays.npz"
        if not npz_path.exists():
            res = float(resolution) if resolution else 100.0
            self.process_tmi(geo_id, resolution=res, nodata=nodata)
            record = self.storage.get(geo_id)

        if op == OPERATION_TMI:
            return record, self.list_magnetic_products(geo_id)

        data = np.load(npz_path)
        grid = data["grid"]
        mask = data["mask"].astype(bool)
        dx = float(data["dx"][0])
        dy = float(data["dy"][0])
        xmin = float(data["xmin"][0])
        ymax = float(data["ymax"][0])
        nd = float(data["nodata"][0]) if "nodata" in data.files else float(nodata)
        input_checksum = sha256_file(npz_path)

        try:
            product, op_meta = run_magnetic_operation(
                op, grid, mask, dx=dx, dy=dy, params=mag_params, nodata=nd
            )
        except Exception as exc:
            raise ManualTrainingError(
                f"Magnetic operation '{op}' failed: {exc}",
                code="MAGNETIC_FAILED",
            ) from exc

        processing_crs = record.working_crs or "EPSG:32631"
        source_crs = record.crs
        outputs: dict[str, Any] = {}
        out_checksums: dict[str, Any] = {}
        stats: dict[str, Any] = {}
        units = str(op_meta.get("units") or "")

        if op == OPERATION_RAPS:
            raps_path = derived / "raps.json"
            raps_path.write_text(json.dumps(product, indent=2), encoding="utf-8")
            raps_png = derived / "raps_preview.png"
            write_raps_chart_png(raps_png, product)  # type: ignore[arg-type]
            outputs = {
                "raps_json": "working/derived/raps.json",
                "preview_png": "working/derived/raps_preview.png",
            }
            out_checksums = {
                "raps_json": sha256_file(raps_path),
                "preview_png": sha256_file(raps_png),
            }
            stats = {
                "n_bins": product.get("n_bins"),
                "wavenumber_count": len(product.get("wavenumber_rad_per_m") or []),
                "depth_interpretation": product.get("depth_interpretation"),
            }
        else:
            assert isinstance(product, np.ndarray)
            out_mask = mask & (product != nd) & np.isfinite(product)
            tif = derived / f"{op}.tif"
            png = derived / f"{op}_preview.png"
            gmeta = {
                "xmin": xmin,
                "ymax": ymax,
                "resolution_x_m": dx,
                "resolution_y_m": dy,
                "resolution": dx,
                "dx_m": dx,
                "dy_m": dy,
            }
            write_geotiff(
                tif,
                product,
                gmeta,
                crs=processing_crs,
                nodata=nd,
                tags={"OPERATION": op, "SOFTWARE_VERSION": SOFTWARE_VERSION},
            )
            cmap = {
                "rte": "RdBu_r",
                "gaussian": "RdBu_r",
                "analytic_signal": "viridis",
                "first_vertical_derivative": "coolwarm",
                "first_horizontal_derivative": "inferno",
                "tilt_derivative": "twilight",
            }.get(op, "RdBu_r")
            stats = write_preview_png(
                png, product, out_mask, title=f"{op} [{units}]", cmap=cmap, units=units or None
            )
            outputs = {
                "geotiff": f"working/derived/{op}.tif",
                "preview_png": f"working/derived/{op}_preview.png",
            }
            out_checksums = {
                "geotiff": sha256_file(tif),
                "preview_png": sha256_file(png),
                "array": sha256_array(product),
            }
            stats = {**stats, **grid_stats(product, out_mask), "units": units}

        entry = build_operation_provenance(
            operation=op,
            op_meta=op_meta,
            params=mag_params,
            input_artifact="working/derived/tmi_grid_arrays.npz",
            input_checksum=input_checksum,
            output_artifacts=outputs,
            output_checksums=out_checksums,
            source_crs=source_crs,
            processing_crs=processing_crs,
            grid_spacing={"dx": dx, "dy": dy},
            nodata_policy={
                "input_nodata_propagated": True,
                "fft_nodata_fill": "valid_mean_temporary",
                "output_nodata_restored": True,
            },
            statistics=stats,
        )
        entry["publication_comparison"] = publication_comparison_notes()
        entry["raw_source_unmodified"] = True
        entry["algorithm"] = SOFTWARE_ID
        entry["software_version"] = SOFTWARE_VERSION
        history = append_processing_history(derived / "processing_history.json", entry)
        report = {
            "operation": op,
            "entry": entry,
            "processing_history": history,
            "products": self.list_magnetic_products(geo_id),
        }
        # Merge into record processing report without dropping base TMI info
        base = dict(record.processing_report or {})
        ops = list(base.get("magnetic_operations") or [])
        ops.append(entry)
        base["magnetic_operations"] = ops
        base["processing_history"] = history
        record.processing_report = base
        record.processing_status = "processed"
        self.storage.save(record)
        self.storage.append_event(
            {
                "event": "magnetic_operation",
                "geo_id": geo_id,
                "at": _utc_now(),
                "operation": op,
            }
        )
        return record, report

    def extract_candidate_lineaments(
        self,
        geo_id: str,
        *,
        percentile: float = 92.0,
        min_length_cells: int = 4,
        min_component_cells: int = 6,
        density_window_m: float = 500.0,
        use_residual_blend: bool = True,
        ensure_derivatives: bool = True,
        nodata: float = -9999.0,
    ):
        """Extract candidate magnetic lineaments from edge-enhanced TMI products.

        Does not invent faults. Does not inject Stage 2.5 channels.
        """
        import json
        from pathlib import Path

        import numpy as np
        import rasterio

        from ssri_model.geological.magnetic_lineament_extraction import (
            ExtractionParams,
            SOFTWARE_ID,
            SOFTWARE_VERSION,
            run_candidate_lineament_extraction,
            sha256_file,
            write_extraction_outputs,
        )
        from ssri_model.geological.magnetic_processing import append_processing_history

        record = self.storage.get(geo_id)
        self._require_validated_tmi(record)
        derived = self.storage.dataset_dir(geo_id) / "working" / "derived"
        npz_path = derived / "tmi_grid_arrays.npz"
        if not npz_path.exists():
            self.process_tmi(geo_id, resolution=100.0, nodata=nodata)
            record = self.storage.get(geo_id)

        if ensure_derivatives:
            for op in (
                "first_horizontal_derivative",
                "analytic_signal",
                "gaussian",
            ):
                tif = derived / f"{op}.tif"
                if not tif.exists():
                    self.run_magnetic_operation(geo_id, operation=op, nodata=nodata)

        data = np.load(npz_path)
        grid = data["grid"]
        mask = data["mask"].astype(bool)
        dx = float(data["dx"][0])
        dy = float(data["dy"][0])
        xmin = float(data["xmin"][0])
        ymax = float(data["ymax"][0])
        nd = float(data["nodata"][0]) if "nodata" in data.files else float(nodata)

        def _read_optional(name: str) -> np.ndarray | None:
            path = derived / f"{name}.tif"
            if not path.is_file():
                return None
            with rasterio.open(path) as src:
                arr = src.read(1).astype(np.float64)
                if src.nodata is not None:
                    arr = np.where(arr == src.nodata, np.nan, arr)
                return arr

        thg = _read_optional("first_horizontal_derivative")
        analytic = _read_optional("analytic_signal")
        gaussian = _read_optional("gaussian")
        if thg is None and analytic is None:
            raise ManualTrainingError(
                "Run first_horizontal_derivative or analytic_signal before extraction.",
                code="LINEAMENT_INPUT",
            )

        params = ExtractionParams(
            percentile=float(percentile),
            min_length_cells=int(min_length_cells),
            min_component_cells=int(min_component_cells),
            density_window_m=float(density_window_m),
            use_residual_blend=bool(use_residual_blend),
        )
        processing_crs = record.working_crs or "EPSG:32631"
        try:
            result = run_candidate_lineament_extraction(
                thg=thg,
                analytic=analytic,
                tmi=grid,
                gaussian=gaussian,
                mask=mask,
                xmin=xmin,
                ymax=ymax,
                dx=dx,
                dy=dy,
                processing_crs=processing_crs,
                params=params,
                nodata=nd,
            )
        except Exception as exc:
            raise ManualTrainingError(
                f"Candidate lineament extraction failed: {exc}",
                code="LINEAMENT_EXTRACT_FAILED",
            ) from exc

        out_dir = derived / "lineaments"
        qc = write_extraction_outputs(result, out_dir, nodata=nd)

        # Also copy GeoJSON to working/lineaments.geojson so catalogue overlay
        # sampling can use it IF the dataset is later activated as reporting_only
        # AND an operator explicitly promotes candidate vectors — we keep a
        # clearly labelled copy under derived/ and a sidecar marker.
        working_copy = self.storage.dataset_dir(geo_id) / "working" / "candidate_lineaments.geojson"
        working_copy.write_text(
            json.dumps(result["geojson"], indent=2), encoding="utf-8"
        )

        entry = {
            "operation": "candidate_lineament_extraction",
            "at": _utc_now(),
            "algorithm": SOFTWARE_ID,
            "software_version": SOFTWARE_VERSION,
            "scientific_validation_status": "NOT_VALIDATED",
            "not_confirmed_faults_or_fractures": True,
            "used_in_inference": False,
            "params": params.to_dict(),
            "statistics": result["statistics"],
            "threshold": result["threshold"],
            "enhancement": result["enhancement_meta"],
            "output_artifacts": {
                "qc": "working/derived/lineaments/lineament_extraction_qc.json",
                "geojson": "working/derived/lineaments/candidate_lineaments.geojson",
                "working_geojson": "working/candidate_lineaments.geojson",
                "density": "working/derived/lineaments/lineament_density.tif",
                "distance": "working/derived/lineaments/lineament_distance.tif",
            },
            "checksums_sha256": qc.get("checksums_sha256"),
            "input_tmi_npz_sha256": sha256_file(Path(npz_path)),
            "quality_limitations": qc.get("quality_limitations"),
        }
        history = append_processing_history(derived / "processing_history.json", entry)
        base = dict(record.processing_report or {})
        base["candidate_lineament_extraction"] = entry
        base["processing_history"] = history
        record.processing_report = base
        prov = dict(record.provenance or {})
        prov["candidate_lineaments"] = {
            "path": "working/derived/lineaments/candidate_lineaments.geojson",
            "scientific_class": "candidate_magnetic_lineament",
            "scientific_validation_status": "NOT_VALIDATED",
            "not_confirmed_faults_or_fractures": True,
            "used_in_inference": False,
            "n_lineaments": result["statistics"].get("n_lineaments"),
            "extracted_at": entry["at"],
        }
        record.provenance = prov
        self.storage.save(record)
        self.storage.append_event(
            {
                "event": "candidate_lineament_extraction",
                "geo_id": geo_id,
                "at": _utc_now(),
                "n_lineaments": result["statistics"].get("n_lineaments"),
            }
        )
        report = {
            "extraction": entry,
            "qc": qc,
            "statistics": result["statistics"],
            "products": self.list_magnetic_products(geo_id),
        }
        return record, report

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
