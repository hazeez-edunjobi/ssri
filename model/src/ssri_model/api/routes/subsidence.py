"""Subsidence scientific-validation HTTP surface.

Exposes the existing ``ssri_model.evaluation.subsidence_validation`` library.
Does not invent ground truth, sample checkpoints at inventory points, or upgrade
``scientific_validation_status`` beyond ``NOT_VALIDATED``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ssri_model.api.dependencies import (
    AuthenticatedPrincipal,
    get_service_config,
    require_read_status,
    require_run_inference,
)
from ssri_model.evaluation.subsidence_validation import (
    SOFTWARE_ID,
    SOFTWARE_VERSION,
    assess_inventory_quality,
    discover_ground_truth_candidates,
    evaluate_subsidence_scores,
    missing_ground_truth_report,
    parse_ground_truth_rows,
)
from ssri_model.manual_training.registry import ModelRegistry
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.service.config import ServiceConfig
from ssri_model.service.validation import reject_path_traversal, resolve_under_output_root

router = APIRouter(prefix="/subsidence", tags=["subsidence"])

Outcome = Literal["unavailable", "insufficient", "success", "failed"]


class GroundTruthRowBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    longitude: float
    latitude: float
    label: int
    source: str
    observed_date: str = "unknown"
    crs: str = "EPSG:4326"
    notes: str = ""
    confidence: str = "unknown"


class EvaluateBody(BaseModel):
    """POST body: independently curated GT rows + externally supplied scores."""

    model_config = ConfigDict(extra="forbid")

    checkpoint_id: str | None = None
    records: list[GroundTruthRowBody] = Field(default_factory=list)
    scores: list[float] = Field(default_factory=list)
    block_deg: float = Field(default=0.5, gt=0.0, le=5.0)


def _repo_root() -> Path:
    # .../model/src/ssri_model/api/routes/subsidence.py → repo root parents[5]
    return Path(__file__).resolve().parents[5]


def _active_checkpoint_id(service_config: ServiceConfig) -> str | None:
    try:
        registry = ModelRegistry(TrainingStorage(str(service_config.output_root)))
        return registry.get_active_model_id()
    except Exception:
        return None


def _derive_outcome(report: dict[str, Any], *, has_scores: bool) -> Outcome:
    metrics = report.get("metrics")
    metrics_computed = bool(
        report.get("metrics_computed")
        or (isinstance(metrics, dict) and metrics.get("metrics_computed"))
    )
    quality = report.get("inventory_quality") or {}
    readiness = report.get("readiness")
    if readiness == "BLOCKED_BY_MISSING_DATA" and not report.get("inventory_quality"):
        return "unavailable"
    if not has_scores:
        if quality.get("n_total", 0) == 0:
            return "unavailable"
        return "insufficient"
    if metrics_computed:
        if quality.get("underpowered"):
            return "insufficient"
        blocks = (report.get("spatial_blocks") or {}).get("n_blocks") or 0
        if blocks < 3:
            return "insufficient"
        return "success"
    return "insufficient"


def _envelope(
    report: dict[str, Any],
    *,
    outcome: Outcome,
    ground_truth_available: bool,
    ground_truth_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "hazard": "subsidence",
        "scientific_validation_status": report.get(
            "scientific_validation_status", "NOT_VALIDATED"
        ),
        "ground_truth_available": ground_truth_available,
        "ground_truth_provenance": ground_truth_provenance,
        "software": report.get("software", SOFTWARE_ID),
        "software_version": report.get("software_version", SOFTWARE_VERSION),
        "report": report,
        "ui_guidance": {
            "title": "Subsidence scientific validation",
            "never_implies": [
                "A successful API response is not scientific validation.",
                "Model inference scores are relative rankings, not probabilities.",
                "Missing metrics must never be shown as zero.",
            ],
            "outcome_meanings": {
                "unavailable": "No independent ground-truth inventory is available.",
                "insufficient": (
                    "Ground truth and/or scores are present but underpowered, "
                    "single-class, missing scores, or otherwise not ready for "
                    "defensible metrics."
                ),
                "success": (
                    "Software metrics computed against supplied ground truth; "
                    "status remains NOT_VALIDATED until independent review."
                ),
                "failed": "Request was invalid or evaluation could not run.",
            },
        },
    }


def _load_inventory_file(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            records = payload.get("records")
            if records is None:
                raise ValueError("JSON inventory must contain a 'records' array")
            if not isinstance(records, list):
                raise ValueError("'records' must be a list")
            return records
        if isinstance(payload, list):
            return payload
        raise ValueError("Unsupported JSON inventory shape")
    if path.suffix.lower() == ".csv":
        import csv

        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return [dict(row) for row in reader]
    raise ValueError(f"Unsupported inventory format: {path.suffix}")


@router.get("/validation")
def get_subsidence_validation(
    checkpoint_id: str | None = Query(
        default=None,
        description="Optional model/checkpoint id for reporting only (no inference).",
    ),
    ground_truth_path: str | None = Query(
        default=None,
        description=(
            "Optional inventory path relative to SSRI_API_OUTPUT_ROOT. "
            "Must be a curated JSON/CSV — never model scores as observations."
        ),
    ),
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_read_status),
) -> Any:
    """Report validation readiness without inventing ground truth or metrics."""
    resolved_checkpoint = checkpoint_id or _active_checkpoint_id(service_config)
    search_roots = [
        Path(service_config.output_root),
        _repo_root() / "data",
        _repo_root() / "poc",
    ]
    searched: list[str] = []
    candidates: list[dict[str, Any]] = []
    for root in search_roots:
        if root.is_dir():
            searched.append(str(root))
            candidates.extend(discover_ground_truth_candidates(root))

    provenance: dict[str, Any] | None = None
    records_raw: list[dict[str, Any]] | None = None

    if ground_truth_path:
        try:
            reject_path_traversal(ground_truth_path, field_name="ground_truth_path")
            gt_parts = Path(ground_truth_path).parts
            if not gt_parts or gt_parts[0] in ("/", "\\"):
                raise ValueError("ground_truth_path must be relative to output root")
            gt_path = resolve_under_output_root(
                service_config.output_root, *gt_parts
            )
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content=_envelope(
                    {
                        "software": SOFTWARE_ID,
                        "software_version": SOFTWARE_VERSION,
                        "scientific_validation_status": "NOT_VALIDATED",
                        "readiness": "BLOCKED_BY_MISSING_DATA",
                        "metrics_computed": False,
                        "reason": str(exc),
                        "error_code": "INVALID_GROUND_TRUTH_PATH",
                    },
                    outcome="failed",
                    ground_truth_available=False,
                ),
            )
        if not gt_path.is_file():
            report = missing_ground_truth_report(
                checkpoint_id=resolved_checkpoint,
                searched_paths=[*searched, str(gt_path)],
            )
            report["candidate_files"] = candidates
            report["reason"] = (
                f"Ground-truth path under output root was not found: {ground_truth_path}"
            )
            return _envelope(
                report,
                outcome="unavailable",
                ground_truth_available=False,
                ground_truth_provenance={"requested_path": ground_truth_path},
            )
        try:
            records_raw = _load_inventory_file(gt_path)
            provenance = {
                "path": str(gt_path),
                "source": "operator_supplied_under_output_root",
                "size_bytes": gt_path.stat().st_size,
            }
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content=_envelope(
                    {
                        "software": SOFTWARE_ID,
                        "software_version": SOFTWARE_VERSION,
                        "scientific_validation_status": "NOT_VALIDATED",
                        "metrics_computed": False,
                        "reason": str(exc),
                        "error_code": "GROUND_TRUTH_PARSE_FAILED",
                    },
                    outcome="failed",
                    ground_truth_available=False,
                    ground_truth_provenance={"path": str(gt_path)},
                ),
            )

    if records_raw is None:
        report = missing_ground_truth_report(
            checkpoint_id=resolved_checkpoint,
            searched_paths=searched,
        )
        report["candidate_files"] = candidates
        report["note"] = (
            "GET does not compute ROC/PR metrics: aligned model scores must be "
            "supplied via POST /api/v1/subsidence/validation. Discovery lists "
            "candidate files only — content is not trusted until reviewed."
        )
        return _envelope(
            report,
            outcome="unavailable",
            ground_truth_available=False,
            ground_truth_provenance={"candidate_files": candidates},
        )

    if len(records_raw) == 0:
        report = missing_ground_truth_report(
            checkpoint_id=resolved_checkpoint,
            searched_paths=searched,
        )
        report["candidate_files"] = candidates
        report["reason"] = (
            "Ground-truth inventory file exists but contains zero records."
        )
        return _envelope(
            report,
            outcome="unavailable",
            ground_truth_available=False,
            ground_truth_provenance=provenance,
        )

    try:
        records = parse_ground_truth_rows(records_raw)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=_envelope(
                {
                    "software": SOFTWARE_ID,
                    "software_version": SOFTWARE_VERSION,
                    "scientific_validation_status": "NOT_VALIDATED",
                    "metrics_computed": False,
                    "reason": str(exc),
                    "error_code": "GROUND_TRUTH_INVALID",
                },
                outcome="failed",
                ground_truth_available=False,
                ground_truth_provenance=provenance,
            ),
        )

    from ssri_model.evaluation.subsidence_validation import ground_truth_schema

    quality = assess_inventory_quality(records)
    report = {
        "software": SOFTWARE_ID,
        "software_version": SOFTWARE_VERSION,
        "hazard": "subsidence",
        "checkpoint_id": resolved_checkpoint,
        "scientific_validation_status": "NOT_VALIDATED",
        "readiness": "BLOCKED_BY_MISSING_DATA",
        "metrics_computed": False,
        "inventory_quality": quality,
        "reason": (
            "Ground-truth inventory parsed for quality review only. "
            "Aligned susceptibility scores were not supplied on GET; "
            "use POST with records+scores to compute exploratory metrics. "
            "Status remains NOT_VALIDATED."
        ),
        "ground_truth_schema": ground_truth_schema(),
        "candidate_files": candidates,
    }
    outcome = _derive_outcome(report, has_scores=False)
    return _envelope(
        report,
        outcome=outcome,
        ground_truth_available=True,
        ground_truth_provenance=provenance,
    )


@router.post("/validation")
def post_subsidence_validation(
    body: EvaluateBody,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> Any:
    """Evaluate supplied scores against independently curated ground truth.

    Does not sample the live checkpoint. Callers must supply aligned scores.
    Metrics never upgrade scientific_validation_status past NOT_VALIDATED.
    """
    resolved_checkpoint = body.checkpoint_id or _active_checkpoint_id(service_config)
    if not body.records:
        report = missing_ground_truth_report(checkpoint_id=resolved_checkpoint)
        report["reason"] = "POST body contained no ground-truth records."
        return _envelope(
            report,
            outcome="unavailable",
            ground_truth_available=False,
        )

    try:
        records = parse_ground_truth_rows([row.model_dump() for row in body.records])
        if not body.scores:
            quality = assess_inventory_quality(records)
            report = {
                "software": SOFTWARE_ID,
                "software_version": SOFTWARE_VERSION,
                "hazard": "subsidence",
                "checkpoint_id": resolved_checkpoint,
                "scientific_validation_status": "NOT_VALIDATED",
                "readiness": "BLOCKED_BY_MISSING_DATA",
                "metrics_computed": False,
                "inventory_quality": quality,
                "reason": (
                    "Ground-truth records were accepted but scores were not supplied. "
                    "Metrics are not computed. Missing metrics are not reported as zero."
                ),
            }
            from ssri_model.evaluation.subsidence_validation import ground_truth_schema

            report["ground_truth_schema"] = ground_truth_schema()
            return _envelope(
                report,
                outcome="insufficient",
                ground_truth_available=True,
                ground_truth_provenance={
                    "source": "request_body",
                    "n_records": len(records),
                },
            )
        report = evaluate_subsidence_scores(
            records,
            body.scores,
            checkpoint_id=resolved_checkpoint,
            block_deg=body.block_deg,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=_envelope(
                {
                    "software": SOFTWARE_ID,
                    "software_version": SOFTWARE_VERSION,
                    "scientific_validation_status": "NOT_VALIDATED",
                    "metrics_computed": False,
                    "reason": str(exc),
                    "error_code": "SUBSIDENCE_VALIDATION_FAILED",
                },
                outcome="failed",
                ground_truth_available=bool(body.records),
            ),
        )

    outcome = _derive_outcome(report, has_scores=True)
    return _envelope(
        report,
        outcome=outcome,
        ground_truth_available=True,
        ground_truth_provenance={
            "source": "request_body",
            "n_records": len(body.records),
            "n_scores": len(body.scores),
        },
    )
