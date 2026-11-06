"""Per-hazard assess contract for the release shell."""

from __future__ import annotations

from typing import Any

from ssri_model.ml.labels import label_class_names
from ssri_model.release_shell.gates import (
    STATUS_EVALUATED,
    STATUS_INSUFFICIENT,
    STATUS_NO_SKILL,
    STATUS_NOT_AVAILABLE,
    STATUS_OUTSIDE_REGION,
    STATUS_UNCONFIRMED,
)
from ssri_model.release_shell.flags import preview_unevaluated_scores
from ssri_model.release_shell.meta import point_in_training_region
from ssri_model.release_shell.spatial_split import LOCAL_EVIDENCE_LIMITATION

STATUS_UNEVALUATED_PREVIEW = "unevaluated_preview, no demonstrated skill beyond baseline"

# Gate floor: these statuses must never emit a numeric score (unless preview is on)
_NO_SCORE_STATUSES = {
    STATUS_NOT_AVAILABLE,
    STATUS_OUTSIDE_REGION,
    STATUS_INSUFFICIENT,
    STATUS_NO_SKILL,
    STATUS_UNCONFIRMED,
    "disabled",
    "no_positive_labels",
}


def resolve_hazard_entry(
    hazard: str,
    *,
    shell_meta: dict[str, Any] | None,
    query_lat: float | None,
    query_lon: float | None,
    raw_score: float | None,
    preview_unevaluated: bool | None = None,
) -> dict[str, Any]:
    """Return assess fields for one hazard under the release-shell contract."""
    preview = (
        preview_unevaluated_scores()
        if preview_unevaluated is None
        else bool(preview_unevaluated)
    )
    if shell_meta is None:
        # No shell meta → treat as unavailable for shell contract
        return {
            "hazard_type": hazard,
            "status": STATUS_NOT_AVAILABLE,
            "score": None,
            "reason": "Checkpoint has no release-shell metadata; hazard scores withheld.",
            "gate_status": None,
            "preview_unevaluated_scores": preview,
        }

    hazards_meta = shell_meta.get("hazards") or {}
    h = hazards_meta.get(hazard) or {}
    local_limits: list[str] = []
    if shell_meta.get("local_evidence_only"):
        local_limits.append(LOCAL_EVIDENCE_LIMITATION)

    if h.get("disabled_at_validation") or h.get("status") == "DISABLED":
        return {
            "hazard_type": hazard,
            "status": STATUS_NOT_AVAILABLE,
            "score": None,
            "reason": h.get("reason")
            or "Hazard was DISABLED at validation (insufficient labelled data).",
            "gate_status": STATUS_INSUFFICIENT,
            "preview_unevaluated_scores": preview,
            "limitations": local_limits or None,
        }

    if not h.get("has_positive_labels", True):
        return {
            "hazard_type": hazard,
            "status": STATUS_NOT_AVAILABLE,
            "score": None,
            "reason": "No positive labels for this hazard in the training set.",
            "gate_status": "no_positive_labels",
            "preview_unevaluated_scores": preview,
            "limitations": local_limits or None,
        }

    if query_lat is not None and query_lon is not None:
        region = shell_meta.get("training_region")
        if region and not point_in_training_region(query_lat, query_lon, region):
            return {
                "hazard_type": hazard,
                "status": STATUS_OUTSIDE_REGION,
                "score": None,
                "reason": (
                    "Query is outside the training data geography "
                    "(blocks/extent stored on the checkpoint)."
                ),
                "gate_status": STATUS_OUTSIDE_REGION,
                "preview_unevaluated_scores": preview,
                "limitations": local_limits or None,
            }

    gate = h.get("gate_status") or STATUS_NO_SKILL
    if gate != STATUS_EVALUATED:
        if preview and raw_score is not None and gate in {
            STATUS_NO_SKILL,
            STATUS_UNCONFIRMED,
            STATUS_INSUFFICIENT,
        }:
            # Trained but ungated — optional preview only; never clears NOT_VALIDATED.
            return {
                "hazard_type": hazard,
                "status": STATUS_UNEVALUATED_PREVIEW,
                "score": float(raw_score),
                "reason": (
                    "Preview score only: this hazard trained but did not pass the "
                    "evaluation gate. No demonstrated skill beyond baseline."
                ),
                "gate_status": gate,
                "preview_unevaluated_scores": True,
                "scientific_validation_status": "NOT_VALIDATED",
                "limitations": (
                    local_limits
                    + [
                        "unevaluated preview; no demonstrated skill beyond baseline",
                        "scientific status remains NOT_VALIDATED",
                    ]
                ),
                "score_framing": "relative susceptibility ranking (unevaluated preview)",
            }
        reason = (
            f"Hazard gate status is '{gate}'; score withheld. "
            "Only 'evaluated' hazards return a ranking score."
        )
        return {
            "hazard_type": hazard,
            "status": STATUS_NOT_AVAILABLE,
            "score": None,
            "reason": reason,
            "gate_status": gate,
            "preview_unevaluated_scores": preview,
            "limitations": local_limits or None,
        }

    return {
        "hazard_type": hazard,
        "status": "available",
        "score": None if raw_score is None else float(raw_score),
        "reason": None,
        "gate_status": STATUS_EVALUATED,
        "score_framing": "relative susceptibility ranking",
        "preview_unevaluated_scores": preview,
        "limitations": local_limits or None,
        "scientific_validation_status": "NOT_VALIDATED",
    }


def build_shell_hazard_profiles(
    *,
    shell_meta: dict[str, Any] | None,
    raw_scores: dict[str, float],
    query_lat: float | None,
    query_lon: float | None,
    requested: list[str] | None = None,
    preview_unevaluated: bool | None = None,
) -> list[dict[str, Any]]:
    names = list(requested) if requested else list(label_class_names())
    out = []
    for name in names:
        out.append(
            resolve_hazard_entry(
                name,
                shell_meta=shell_meta,
                query_lat=query_lat,
                query_lon=query_lon,
                raw_score=raw_scores.get(name),
                preview_unevaluated=preview_unevaluated,
            )
        )
    return out
