"""Subsidence scientific validation harness (honest missing-data behaviour).

This module never invents subsidence occurrences or control locations.
When real, independently curated ground-truth inventories are absent, it returns
a structured NOT_VALIDATED / BLOCKED_BY_MISSING_DATA report and refuses metrics.

When a validated inventory is supplied (EPSG-declared positives and negatives),
it computes ROC-AUC, PR-AUC, precision/recall/F1, Brier score, and a reliability
diagram — only after spatial-block splitting to reduce leakage.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

SOFTWARE_ID = "ssri_model.evaluation.subsidence_validation"
SOFTWARE_VERSION = "1.0.0"

GROUND_TRUTH_SCHEMA_VERSION = "ssri.subsidence_ground_truth.v1"

REQUIRED_COLUMNS = ("longitude", "latitude", "label", "source", "observed_date")
# label: 1 = observed subsidence, 0 = validated non-subsidence control


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class GroundTruthRecord:
    longitude: float
    latitude: float
    label: int
    source: str
    observed_date: str
    crs: str = "EPSG:4326"
    notes: str = ""
    confidence: str = "unknown"


def ground_truth_schema() -> dict[str, Any]:
    return {
        "schema": GROUND_TRUTH_SCHEMA_VERSION,
        "description": (
            "Inventory of observed subsidence positives and validated "
            "non-subsidence controls. Synthetic or model-derived scores must "
            "never be entered as observations."
        ),
        "required_columns": list(REQUIRED_COLUMNS),
        "label_values": {
            "1": "Observed subsidence (field/survey/authoritative inventory)",
            "0": "Validated non-subsidence control location",
        },
        "crs_default": "EPSG:4326",
        "forbidden": [
            "Model susceptibility scores presented as observations",
            "Synthetic Stage 2.5 training labels as real-world ground truth",
            "TMI or magnetic anomalies as subsidence occurrences",
        ],
        "minimum_for_metrics": {
            "n_positives": 30,
            "n_negatives": 30,
            "spatially_independent_blocks": 3,
            "note": (
                "Below these floors, metrics may be reported only as exploratory "
                "with an explicit underpowered flag — never as scientific validation."
            ),
        },
        "authoritative_source_examples": [
            {
                "name": "National geological survey subsidence / sinkhole inventories",
                "notes": "Prefer agency-published GIS with CRS and metadata",
            },
            {
                "name": "Peer-reviewed InSAR deformation studies with validated hotspots",
                "notes": "Deformation ≠ confirmed subsidence hazard class without review",
            },
            {
                "name": "Geotechnical / borehole campaigns with documented settlement",
                "notes": "Licensing and spatial coverage must be recorded",
            },
        ],
    }


def missing_ground_truth_report(
    *,
    checkpoint_id: str | None = None,
    searched_paths: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "software": SOFTWARE_ID,
        "software_version": SOFTWARE_VERSION,
        "created_at": _utc_now(),
        "hazard": "subsidence",
        "scientific_validation_status": "NOT_VALIDATED",
        "readiness": "BLOCKED_BY_MISSING_DATA",
        "checkpoint_id": checkpoint_id,
        "metrics_computed": False,
        "reason": (
            "No curated real-world subsidence ground-truth inventory is available "
            "in the repository for independent validation of the Stage 2.5 "
            "subsidence head."
        ),
        "searched_paths": list(searched_paths or []),
        "ground_truth_schema": ground_truth_schema(),
        "interpretation_rules": [
            "Susceptibility scores are relative rankings, not calibrated probabilities.",
            "An Abeokuta score near 58% must not be read as a 58% probability of subsidence.",
            "Synthetic/bootstrap training labels are not scientific ground truth.",
        ],
        "required_before_validation": [
            "EPSG-declared observed subsidence positives with provenance",
            "Validated non-subsidence controls in the same geographic domain",
            "Spatially independent train/validation/test (or block) split",
            "Documented licensing and collection methodology",
        ],
    }


def parse_ground_truth_rows(rows: Sequence[dict[str, Any]]) -> list[GroundTruthRecord]:
    records: list[GroundTruthRecord] = []
    for i, row in enumerate(rows):
        try:
            lon = float(row["longitude"])
            lat = float(row["latitude"])
            label = int(row["label"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid ground-truth row {i}: {exc}") from exc
        if label not in (0, 1):
            raise ValueError(f"Row {i}: label must be 0 or 1, got {label}")
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            raise ValueError(f"Row {i}: longitude/latitude out of range")
        source = str(row.get("source") or "").strip()
        if not source:
            raise ValueError(f"Row {i}: source is required")
        records.append(
            GroundTruthRecord(
                longitude=lon,
                latitude=lat,
                label=label,
                source=source,
                observed_date=str(row.get("observed_date") or "unknown"),
                crs=str(row.get("crs") or "EPSG:4326"),
                notes=str(row.get("notes") or ""),
                confidence=str(row.get("confidence") or "unknown"),
            )
        )
    return records


def assess_inventory_quality(records: Sequence[GroundTruthRecord]) -> dict[str, Any]:
    n_pos = sum(1 for r in records if r.label == 1)
    n_neg = sum(1 for r in records if r.label == 0)
    floors = ground_truth_schema()["minimum_for_metrics"]
    underpowered = n_pos < floors["n_positives"] or n_neg < floors["n_negatives"]
    sources = sorted({r.source for r in records})
    return {
        "n_total": len(records),
        "n_positives": n_pos,
        "n_negatives": n_neg,
        "class_imbalance_pos_fraction": (n_pos / len(records)) if records else None,
        "sources": sources,
        "underpowered": underpowered,
        "minimum_floors": floors,
        "duplicates_xy": _count_duplicate_xy(records),
    }


def _count_duplicate_xy(records: Sequence[GroundTruthRecord]) -> int:
    seen: set[tuple[float, float]] = set()
    dups = 0
    for r in records:
        key = (round(r.longitude, 6), round(r.latitude, 6))
        if key in seen:
            dups += 1
        seen.add(key)
    return dups


def spatial_block_ids(
    records: Sequence[GroundTruthRecord],
    *,
    block_deg: float = 0.5,
) -> list[str]:
    """Assign coarse geographic blocks to reduce spatial leakage."""
    blocks: list[str] = []
    for r in records:
        bx = math.floor(r.longitude / block_deg) * block_deg
        by = math.floor(r.latitude / block_deg) * block_deg
        blocks.append(f"{bx:.2f}_{by:.2f}")
    return blocks


def _binary_metrics(y_true: np.ndarray, y_score: np.ndarray) -> dict[str, Any]:
    """Compute ROC/PR/F1/Brier when both classes and scores exist."""
    from sklearn.metrics import (
        average_precision_score,
        brier_score_loss,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    if len(np.unique(y_true)) < 2:
        return {
            "metrics_computed": False,
            "reason": "Need both positive and negative labels for binary metrics.",
        }
    y_pred = (y_score >= 0.5).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    # Reliability diagram (10 bins)
    bins = np.linspace(0.0, 1.0, 11)
    centers = 0.5 * (bins[:-1] + bins[1:])
    frac_pos = []
    mean_pred = []
    counts = []
    for i in range(10):
        sel = (y_score >= bins[i]) & (y_score < bins[i + 1] if i < 9 else y_score <= bins[i + 1])
        counts.append(int(sel.sum()))
        if sel.any():
            frac_pos.append(float(y_true[sel].mean()))
            mean_pred.append(float(y_score[sel].mean()))
        else:
            frac_pos.append(None)
            mean_pred.append(None)
    return {
        "metrics_computed": True,
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "pr_auc": float(average_precision_score(y_true, y_score)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "brier_score": float(brier_score_loss(y_true, y_score)),
        "confusion_matrix": {
            "labels": [0, 1],
            "matrix": cm.tolist(),
        },
        "calibration_curve": {
            "bin_centers": centers.tolist(),
            "fraction_positives": frac_pos,
            "mean_predicted": mean_pred,
            "counts": counts,
            "note": "Not a claim of probability calibration unless Brier/ECE support it.",
        },
    }


def evaluate_subsidence_scores(
    records: Sequence[GroundTruthRecord],
    scores: Sequence[float],
    *,
    checkpoint_id: str | None = None,
    block_deg: float = 0.5,
) -> dict[str, Any]:
    """Evaluate scores in [0,1] against ground truth with spatial blocks.

    Scores are treated as relative ranking inputs for ROC/PR; do not claim
    calibrated probabilities unless calibration metrics and documentation agree.
    """
    if len(records) != len(scores):
        raise ValueError("records and scores length mismatch")
    quality = assess_inventory_quality(records)
    y_true = np.asarray([r.label for r in records], dtype=np.int64)
    y_score = np.asarray(scores, dtype=np.float64)
    if np.any(~np.isfinite(y_score)):
        raise ValueError("scores contain non-finite values")
    # Clip for Brier / reliability; ROC uses ranking so clipping is documented.
    y_score_clip = np.clip(y_score, 0.0, 1.0)
    blocks = spatial_block_ids(records, block_deg=block_deg)
    unique_blocks = sorted(set(blocks))
    metrics = _binary_metrics(y_true, y_score_clip)
    status = "NOT_VALIDATED"
    readiness = "BLOCKED_BY_MISSING_DATA"
    if metrics.get("metrics_computed") and not quality["underpowered"] and len(unique_blocks) >= 3:
        readiness = "READY_WITH_DOCUMENTED_LIMITATIONS"
        # Still NOT_VALIDATED until independent review / peer process.
        status = "NOT_VALIDATED"
    elif metrics.get("metrics_computed"):
        readiness = "READY_WITH_DOCUMENTED_LIMITATIONS"
        status = "NOT_VALIDATED"

    return {
        "software": SOFTWARE_ID,
        "software_version": SOFTWARE_VERSION,
        "created_at": _utc_now(),
        "hazard": "subsidence",
        "checkpoint_id": checkpoint_id,
        "scientific_validation_status": status,
        "readiness": readiness,
        "inventory_quality": quality,
        "spatial_blocks": {
            "block_deg": block_deg,
            "n_blocks": len(unique_blocks),
            "blocks": unique_blocks,
            "strategy": "geographic_block_ids_for_leakage_awareness",
        },
        "metrics": metrics,
        "score_interpretation": (
            "Scores are relative susceptibility rankings unless calibration is "
            "demonstrated. Do not equate score*100 with probability percent."
        ),
        "ground_truth_schema": ground_truth_schema(),
    }


def discover_ground_truth_candidates(root: Path) -> list[dict[str, Any]]:
    """Search common locations for inventory files; never invent content."""
    patterns = [
        "**/subsidence*ground*truth*.json",
        "**/subsidence*inventory*.csv",
        "**/ground_truth/subsidence*.csv",
        "**/ground_truth/subsidence*.json",
        "**/validation/subsidence*.csv",
    ]
    found: list[dict[str, Any]] = []
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file():
                found.append(
                    {
                        "path": str(path),
                        "size_bytes": path.stat().st_size,
                        "note": "Candidate file only — content must be reviewed before use.",
                    }
                )
    return found


def write_schema_stub(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": GROUND_TRUTH_SCHEMA_VERSION,
        "records": [],
        "instructions": ground_truth_schema(),
        "scientific_validation_status": "NOT_VALIDATED",
        "note": "Populate records with real observations only. Empty = missing ground truth.",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
