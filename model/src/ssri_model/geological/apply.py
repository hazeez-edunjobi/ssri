"""Offline schema-v2 feature application from the geological catalogue.

Reuses ``feature_apply.apply_overburden_to_dataset`` and
``feature_apply.apply_lineaments_to_dataset``. Does **not** touch live assess.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ssri_model.geological.models import (
    MEASUREMENT_LINEAMENT,
    MEASUREMENT_OVERBURDEN_THICKNESS,
    GeologicalDatasetRecord,
)
from ssri_model.geological.storage import GeologicalStorage
from ssri_model.geological.target import resolve_offline_apply_target
from ssri_model.geological.validate import assert_column_mapping_consistent
from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.release_shell.feature_apply import (
    apply_lineaments_to_dataset,
    apply_overburden_to_dataset,
)
from ssri_model.release_shell.lineaments import load_lineament_segments
from ssri_model.release_shell.point_grid_csv import ingest_point_grid_csv


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(payload, indent=2)
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def apply_geological_to_offline_dataset(
    storage: GeologicalStorage,
    *,
    geo_ids: list[str],
    target_dataset_id: str | None = None,
    target_dataset_root: Path | str | None = None,
    window_m: float = 500.0,
    record_provenance: bool = True,
    allow_direct_target_root: bool = False,
) -> dict[str, Any]:
    """Apply eligible catalogue layers onto an offline Stage 2.5 dataset root.

    Path policy (F1):
    - Default: require ``target_dataset_id`` and resolve via ``TrainingStorage``
      under the same output root as the geological catalogue.
    - ``allow_direct_target_root=True``: trusted in-process / test escape hatch
      that accepts an explicit local ``target_dataset_root``. Not for HTTP.

    Provenance (F5):
    - Assigns ``application_id`` before stack mutation.
    - Writes durable ``geological_apply_report.json`` after successful stack
      updates, then appends the JSONL ledger.
    - Ledger append is idempotent; ``recover_feature_applications_from_report``
      can rebuild missing ledger rows from a PASS report without duplicating.
    """
    dataset_id: str | None
    if allow_direct_target_root:
        if not target_dataset_root:
            raise ManualTrainingError(
                "allow_direct_target_root requires target_dataset_root.",
                code="APPLY_TARGET_MISSING",
            )
        target = Path(target_dataset_root)
        dataset_id = target_dataset_id
    else:
        training = TrainingStorage(storage.root.parent)
        dataset_id, target = resolve_offline_apply_target(
            training,
            target_dataset_id=target_dataset_id,
            target_dataset_root=(
                str(target_dataset_root) if target_dataset_root is not None else None
            ),
        )

    if not target.exists():
        raise ManualTrainingError(
            f"Target dataset root does not exist: {target}",
            code="APPLY_TARGET_MISSING",
        )

    application_id = f"app_{uuid.uuid4().hex[:16]}"
    records = [storage.get(gid) for gid in geo_ids]
    by_mt: dict[str, list[GeologicalDatasetRecord]] = {}
    for rec in records:
        if rec.validation_status != "validated":
            raise ManualTrainingError(
                f"{rec.geo_id} is not validated.",
                code="APPLY_NOT_VALIDATED",
            )
        if rec.activation_status not in {"reporting_only", "approved"}:
            raise ManualTrainingError(
                f"{rec.geo_id} is not activated for reporting/offline use.",
                code="APPLY_NOT_ACTIVATED",
            )
        mt = rec.measurement_type or "undeclared"
        by_mt.setdefault(mt, []).append(rec)

    for mt, group in by_mt.items():
        if len(group) > 1:
            raise ManualTrainingError(
                f"Conflicting datasets for measurement_type={mt}: "
                f"{[g.geo_id for g in group]}. Choose one explicitly.",
                code="APPLY_CONFLICT",
            )

    steps: list[dict[str, Any]] = []
    provenance_entries: list[dict[str, Any]] = []
    for rec in records:
        original = storage.original_path(rec)
        if original is None or not original.exists():
            raise ManualTrainingError(
                f"Original upload missing for {rec.geo_id}.",
                code="APPLY_ORIGINAL_MISSING",
            )

        if rec.asset_kind == "point_grid_csv":
            if rec.measurement_type != MEASUREMENT_OVERBURDEN_THICKNESS:
                raise ManualTrainingError(
                    f"{rec.geo_id} measurement_type={rec.measurement_type!r} cannot "
                    "be written to overburden_thickness. depth_to_bedrock is not "
                    "auto-converted.",
                    code="APPLY_MEASUREMENT",
                )
            if not rec.crs:
                raise ManualTrainingError(
                    f"{rec.geo_id} has no declared CRS.",
                    code="CRS_REQUIRED",
                )
            if not rec.units:
                raise ManualTrainingError(
                    f"{rec.geo_id} has no declared units.",
                    code="UNITS_REQUIRED",
                )
            assert_column_mapping_consistent(
                x_column=rec.x_column,
                y_column=rec.y_column,
                value_column=rec.z_column,
            )
            content = original.read_bytes()
            layer = ingest_point_grid_csv(
                content,
                filename=rec.original_filename or "layer.csv",
                layer_name=MEASUREMENT_OVERBURDEN_THICKNESS,
                crs=rec.crs,
                working_crs=rec.working_crs or rec.crs,
                x_column=rec.x_column,
                y_column=rec.y_column,
                value_column=rec.z_column,
            )
            scale = rec.z_to_metres
            conversion = {"z_to_metres": scale, "applied": False}
            if scale is not None and scale != 1.0:
                for key, val in list(layer.values.items()):
                    if val == val and val not in {-9999.0}:  # noqa: PLR0124
                        layer.values[key] = float(val) * float(scale)
                conversion["applied"] = True
            result = apply_overburden_to_dataset(
                target,
                layer,
                measurement_type="thickness",
                units=rec.units if not conversion["applied"] else "m",
            )
            step = {
                "geo_id": rec.geo_id,
                "channel": "overburden_thickness",
                "channels": ["overburden_thickness"],
                "measurement_type": rec.measurement_type,
                "result": result,
                "crs": rec.crs,
                "working_crs": rec.working_crs or rec.crs,
                "units_conversion": conversion,
                "content_sha256": rec.content_sha256,
                "column_mapping": {
                    "x_column": rec.x_column,
                    "y_column": rec.y_column,
                    "z_column": rec.z_column,
                },
            }
            steps.append(step)
            provenance_entries.append(
                {
                    "application_id": application_id,
                    "geo_id": rec.geo_id,
                    "content_sha256": rec.content_sha256,
                    "target_dataset_id": dataset_id or "",
                    "measurement_type": rec.measurement_type,
                    "channels": ["overburden_thickness"],
                    "processing_parameters": {
                        "crs": rec.crs,
                        "working_crs": rec.working_crs or rec.crs,
                        "units": rec.units,
                        "z_to_metres": scale,
                        "column_mapping": step["column_mapping"],
                    },
                    "overall": "PASS",
                }
            )

        elif rec.asset_kind == "vector_lineament":
            if rec.measurement_type not in {MEASUREMENT_LINEAMENT, "lineament_vectors", None}:
                if rec.measurement_type and "lineament" not in rec.measurement_type:
                    raise ManualTrainingError(
                        f"{rec.geo_id} is not a lineament dataset.",
                        code="APPLY_MEASUREMENT",
                    )
            if not rec.crs:
                raise ManualTrainingError(
                    f"{rec.geo_id} has no declared CRS.",
                    code="CRS_REQUIRED",
                )
            geojson_path = storage.resolve_under(rec.geo_id, "working/lineaments.geojson")
            if geojson_path.exists():
                raw = geojson_path.read_bytes()
            else:
                raw = original.read_bytes()
                if rec.original_filename.lower().endswith((".geojson", ".json")):
                    pass
                else:
                    raise ManualTrainingError(
                        f"{rec.geo_id}: working GeoJSON missing for non-GeoJSON original.",
                        code="APPLY_WORKING_MISSING",
                    )
            segments = load_lineament_segments(raw)
            result = apply_lineaments_to_dataset(
                target,
                segments,
                window_m=window_m,
                lineament_crs=rec.crs,
            )
            step = {
                "geo_id": rec.geo_id,
                "channels": ["lineament_density", "lineament_distance"],
                "measurement_type": rec.measurement_type,
                "result": result,
                "crs": rec.crs,
                "window_m": window_m,
                "segment_count": len(segments),
                "content_sha256": rec.content_sha256,
            }
            steps.append(step)
            provenance_entries.append(
                {
                    "application_id": application_id,
                    "geo_id": rec.geo_id,
                    "content_sha256": rec.content_sha256,
                    "target_dataset_id": dataset_id or "",
                    "measurement_type": rec.measurement_type,
                    "channels": ["lineament_density", "lineament_distance"],
                    "window_m": window_m,
                    "processing_parameters": {
                        "crs": rec.crs,
                        "window_m": window_m,
                        "segment_count": len(segments),
                    },
                    "overall": "PASS",
                }
            )
        else:
            raise ManualTrainingError(
                f"Unsupported asset_kind={rec.asset_kind}",
                code="APPLY_ASSET_KIND",
            )

    applied_at = _utc_now()
    report = {
        "overall": "PASS",
        "application_id": application_id,
        "at": applied_at,
        "target_dataset_id": dataset_id,
        "target_dataset_root": str(target),
        "source_geo_ids": list(geo_ids),
        "steps": steps,
        "used_in_inference": False,
        "used_in_feature_application": True,
        "scientific_validation_status": "NOT_VALIDATED",
        "note": (
            "Offline schema-v2 feature application only. "
            "Live 13-channel assessment inference is unchanged."
        ),
    }
    # Durable success receipt BEFORE ledger — enables crash recovery without
    # inventing success from partial stack writes alone.
    out = target / "geological_apply_report.json"
    _atomic_write_json(out, report)
    report["report_path"] = str(out)

    if record_provenance:
        for entry in provenance_entries:
            entry["at"] = applied_at
            storage.record_feature_application(entry)
        # Idempotent reconcile in case a prior crash left the report without ledger.
        storage.recover_feature_applications_from_report(report)

    return report
