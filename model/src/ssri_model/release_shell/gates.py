"""Status gates — set in config, not editable mid-run."""

from __future__ import annotations

from typing import Sequence

# Fixed wording — never "validated"
STATUS_EVALUATED = "evaluated"
STATUS_NO_SKILL = "trained, no demonstrated skill beyond slope"
STATUS_UNCONFIRMED = "trained, unconfirmed across seeds"
STATUS_NOT_AVAILABLE = "not_available"
STATUS_NO_TRAINED_MODEL = "no_trained_model"
STATUS_OUTSIDE_REGION = "outside_training_region"
STATUS_INSUFFICIENT = "insufficient labelled data"


def gate_hazard_status(
    *,
    delta_ci95: Sequence[float] | None,
    frac_blocks_auc_gt_0_5: float,
) -> str:
    """Return gate label for a hazard (single seed).

    Evaluated only if lower 95% CI of ΔAUC vs slope > 0 AND
    AUC > 0.5 in ≥75% of held-out blocks.
    """
    if delta_ci95 is None or len(delta_ci95) < 2:
        return STATUS_NO_SKILL
    lower = float(delta_ci95[0])
    if lower > 0 and frac_blocks_auc_gt_0_5 >= 0.75:
        return STATUS_EVALUATED
    return STATUS_NO_SKILL


def aggregate_seed_gates(seed_gates: Sequence[str], *, min_pass: int = 2) -> str:
    """A hazard is evaluated only if the gate passes on at least min_pass seeds."""
    n_pass = sum(1 for g in seed_gates if g == STATUS_EVALUATED)
    if n_pass >= min_pass:
        return STATUS_EVALUATED
    if n_pass == 0 and seed_gates:
        # Prefer the modal non-evaluated status
        return STATUS_NO_SKILL
    if seed_gates:
        return STATUS_UNCONFIRMED
    return STATUS_NO_SKILL
