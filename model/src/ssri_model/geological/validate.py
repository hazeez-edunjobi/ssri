"""Validate declared geological point-grid layers via existing shell validator."""

from __future__ import annotations

from typing import Any

from ssri_model.geological.models import (
    MEASUREMENT_DEPTH_TO_BEDROCK,
    MEASUREMENT_OVERBURDEN_THICKNESS,
    MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
    canonicalize_measurement_type,
    is_tmi_measurement,
)
from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.release_shell.validator import validate_point_grid_layer


def _column_key(value: str | int | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return f"idx:{value}"
    text = str(value).strip()
    return text.lower() if text else None


def assert_column_mapping_consistent(
    *,
    x_column: str | int | None,
    y_column: str | int | None,
    value_column: str | int | None,
) -> None:
    """Reject duplicate/ambiguous explicit column mappings before ingest."""
    keys = {
        "x_column": _column_key(x_column),
        "y_column": _column_key(y_column),
        "z_column": _column_key(value_column),
    }
    present = {name: key for name, key in keys.items() if key is not None}
    if len(present) < 2:
        return
    seen: dict[str, str] = {}
    for name, key in present.items():
        if key in seen:
            raise ManualTrainingError(
                f"Ambiguous column mapping: {seen[key]} and {name} both select '{key}'.",
                code="COLUMN_MAPPING_AMBIGUOUS",
            )
        seen[key] = name


def validate_declared_point_grid(
    content: bytes,
    *,
    filename: str,
    measurement_type: str,
    crs: str,
    working_crs: str | None = None,
    units: str | None = None,
    x_column: str | int | None = None,
    y_column: str | int | None = None,
    value_column: str | int | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run ``validate_point_grid_layer`` with catalogue measurement semantics.

    Depth is never written as thickness. ``can_activate_reporting`` is true only
    when overall ≠ FAIL and CRS/measurement/units are present.

    Declared coordinate/value column mappings are passed through to the shell
    ingest path (source of truth). Explicit mappings are not silently ignored.
    """
    mt = canonicalize_measurement_type(measurement_type)
    if not mt:
        return {
            "overall": "FAIL",
            "can_train": False,
            "can_activate_reporting": False,
            "checks": [
                {
                    "name": "measurement_type",
                    "status": "FAIL",
                    "message": "measurement_type is required before validation.",
                }
            ],
            "scientific_validation_status": "NOT_VALIDATED",
        }

    try:
        assert_column_mapping_consistent(
            x_column=x_column,
            y_column=y_column,
            value_column=value_column,
        )
    except ManualTrainingError as exc:
        return {
            "overall": "FAIL",
            "can_train": False,
            "can_activate_reporting": False,
            "checks": [
                {
                    "name": "column_mapping",
                    "status": "FAIL",
                    "message": exc.message,
                    "detail": {"code": exc.code},
                }
            ],
            "scientific_validation_status": "NOT_VALIDATED",
            "column_mapping": {
                "x_column": x_column,
                "y_column": y_column,
                "z_column": value_column,
            },
        }

    # TMI point surveys use a dedicated validator (irregular clouds allowed).
    if mt == MEASUREMENT_TOTAL_MAGNETIC_INTENSITY or is_tmi_measurement(mt):
        from ssri_model.geological.tmi import validate_tmi_point_survey

        return validate_tmi_point_survey(
            content,
            filename=filename,
            crs=crs,
            units=units,
            x_column=x_column,
            y_column=y_column,
            z_column=value_column,
            provenance=provenance,
            working_crs=working_crs,
        )

    # Map catalogue identity onto shell layer_name / measurement_type.
    if mt == MEASUREMENT_DEPTH_TO_BEDROCK:
        layer_name = MEASUREMENT_DEPTH_TO_BEDROCK
        shell_mt = "depth_to_interface"
    elif mt == MEASUREMENT_OVERBURDEN_THICKNESS:
        layer_name = MEASUREMENT_OVERBURDEN_THICKNESS
        shell_mt = "thickness"
    else:
        layer_name = mt
        shell_mt = None

    report = validate_point_grid_layer(
        content,
        filename=filename,
        layer_name=layer_name,
        crs=crs,
        working_crs=working_crs,
        measurement_type=shell_mt,
        units=units,
        x_column=x_column,
        y_column=y_column,
        value_column=value_column,
    )
    overall = report.get("overall")
    units_ok = bool((units or "").strip())
    crs_ok = bool((crs or "").strip()) and overall != "FAIL"
    report["measurement_type"] = mt
    report["can_activate_reporting"] = bool(
        overall in {"PASS", "WARN"} and crs_ok and units_ok and mt
    )
    report["scientific_validation_status"] = "NOT_VALIDATED"
    report["can_train"] = False
    report["column_mapping"] = {
        "x_column": x_column,
        "y_column": y_column,
        "z_column": value_column,
        "applied": True,
    }
    return report
