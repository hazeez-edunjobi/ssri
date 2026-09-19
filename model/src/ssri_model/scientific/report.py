"""Scientific validation report generation."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ssri_model import __version__
from ssri_model.scientific.exceptions import ReviewValidationError

SCIENTIFIC_VALIDATION_JSON = "scientific_validation.json"
SCIENTIFIC_VALIDATION_MD = "scientific_validation.md"

ValidationStatus = Literal[
    "NOT_VALIDATED",
    "DATASET_AUDITED",
    "STATISTICALLY_VALIDATED",
    "SPATIALLY_VALIDATED",
    "SCIENTIFICALLY_VALIDATED",
]

ReviewDecision = Literal["pending", "accepted", "rejected"]


@dataclass
class ScientificReviewRecord:
    """Human expert review metadata."""

    reviewer: str
    reviewed_at: str
    decision: ReviewDecision
    notes: str
    evidence: dict[str, Any] = field(default_factory=dict)
    dataset_version: str = ""
    report_fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.reviewer.strip():
            raise ReviewValidationError("reviewer is required")
        if not self.reviewed_at.strip():
            raise ReviewValidationError("reviewed_at is required")
        if not self.notes.strip():
            raise ReviewValidationError("notes are required")
        if self.decision == "accepted" and not self.reviewer.strip():
            raise ReviewValidationError("accepted review requires reviewer")


@dataclass
class ScientificValidationReport:
    """Complete scientific validation report."""

    status: ValidationStatus = "NOT_VALIDATED"
    dataset: dict[str, Any] = field(default_factory=dict)
    audits: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    fingerprints: dict[str, str] = field(default_factory=dict)
    independence: dict[str, Any] = field(default_factory=dict)
    distribution: dict[str, Any] = field(default_factory=dict)
    scientific_review_required: bool = True
    scientific_validation_status: str = "NOT_VALIDATED"
    package_version: str = __version__
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    review: ScientificReviewRecord | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "status": self.status,
            "scientific_validation_status": self.scientific_validation_status,
            "dataset": self.dataset,
            "audits": self.audits,
            "warnings": self.warnings,
            "failures": self.failures,
            "fingerprints": self.fingerprints,
            "independence": self.independence,
            "distribution": self.distribution,
            "scientific_review_required": self.scientific_review_required,
            "package_version": self.package_version,
            "created_at": self.created_at,
        }
        if self.review is not None:
            payload["review"] = asdict(self.review)
        return payload


def save_scientific_validation_json(path: Path | str, report: ScientificValidationReport) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(destination.name + ".tmp")
    tmp.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    os.replace(tmp, destination)
    return destination


def render_scientific_validation_markdown(report: ScientificValidationReport) -> str:
    lines = [
        "# SSRI Scientific Validation Report",
        "",
        "> Automated validation does not establish geological truth or operational hazard accuracy.",
        "",
        f"**Status:** `{report.scientific_validation_status}`",
        f"**Created:** {report.created_at}",
        "",
        "## Engineering Checks",
        "",
    ]
    for name, status in report.audits.items():
        lines.append(f"- **{name}:** {status}")
    lines.extend(["", "## Data Quality Checks", ""])
    if report.warnings:
        for warning in report.warnings:
            lines.append(f"- WARNING: {warning}")
    else:
        lines.append("- No data quality warnings recorded.")
    lines.extend(["", "## Spatial Checks", ""])
    lines.append(f"- Independence: `{report.independence.get('independent', 'unknown')}`")
    lines.append(
        f"- Spatial overlap count: {report.independence.get('spatial_overlap_count', 0)}"
    )
    lines.append(
        f"- Spatial buffer count: {report.independence.get('spatial_buffer_count', 0)}"
    )
    lines.extend(["", "## Statistical Checks", ""])
    distribution = report.distribution
    if distribution:
        lines.append(
            f"- Max/min class ratio: {distribution.get('max_min_class_ratio', 'n/a')}"
        )
        shift_warnings = distribution.get("feature_shift_warnings", [])
        if shift_warnings:
            for warning in shift_warnings:
                lines.append(f"- {warning}")
        else:
            lines.append("- No major feature distribution shift warnings recorded.")
    else:
        lines.append("- Distribution analysis not available.")
    lines.extend(["", "## Scientific Review Requirements", ""])
    lines.append(
        "- Human/domain review is required before any operational hazard claim."
        if report.scientific_review_required
        else "- Review record attached."
    )
    if report.review is not None:
        lines.extend(
            [
                "",
                "## Human Review",
                "",
                f"- Reviewer: {report.review.reviewer}",
                f"- Decision: {report.review.decision}",
                f"- Reviewed at: {report.review.reviewed_at}",
                f"- Notes: {report.review.notes}",
            ]
        )
    lines.extend(
        [
            "",
            "## Known Limitations",
            "",
            "- Passing automated checks does not prove geological validity.",
            "- Feature/label association diagnostics are not proof of leakage.",
            "- Spatial bbox checks do not replace expert geospatial review.",
            "",
        ]
    )
    return "\n".join(lines)


def save_scientific_validation_markdown(
    path: Path | str,
    report: ScientificValidationReport,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_scientific_validation_markdown(report), encoding="utf-8")
    return destination


def attach_review(
    report: ScientificValidationReport,
    review: ScientificReviewRecord,
    *,
    expected_fingerprint: str | None = None,
) -> ScientificValidationReport:
    if expected_fingerprint and review.report_fingerprint != expected_fingerprint:
        raise ReviewValidationError("Review report fingerprint mismatch")
    report.review = review
    if review.decision == "accepted":
        report.status = "SCIENTIFICALLY_VALIDATED"
        report.scientific_validation_status = "SCIENTIFICALLY_VALIDATED"
        report.scientific_review_required = False
    elif review.decision == "rejected":
        report.status = "NOT_VALIDATED"
        report.scientific_validation_status = "NOT_VALIDATED"
    return report
