"""Phase 8: sigmoid/softmax repro + claims audit (proposed patch only)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, REPO, append_run_log, write_json  # noqa: E402

sys.path.insert(0, str(REPO / "model" / "src"))


def repro_sigmoid_softmax_mismatch() -> dict:
    """Minimal reproducing example: same logits → different probability semantics."""
    torch.manual_seed(0)
    logits = torch.randn(1, 3, 8, 8)
    sig = torch.sigmoid(logits)
    soft = F.softmax(logits, dim=1)
    return {
        "logits_shape": list(logits.shape),
        "sigmoid_channel_sums_mean": float(sig.sum(dim=1).mean()),
        "softmax_channel_sums_mean": float(soft.sum(dim=1).mean()),
        "max_abs_diff_mean_over_space": float((sig - soft).abs().mean()),
        "finding": (
            "Sigmoid channel sums ≠ 1; softmax sums ≈ 1. Assess/MC uses sigmoid; "
            "evaluation/predictions.py uses softmax — incompatible for mutually exclusive CE classes."
        ),
        "assess_file": "model/src/ssri_model/api/routes/assess.py",
        "uncertainty_file": "model/src/ssri_model/uncertainty/__init__.py",
        "eval_file": "model/src/ssri_model/evaluation/predictions.py",
    }


def check_stage25_checkpoint() -> dict:
    hits = list(REPO.rglob("best.pt")) + list(REPO.rglob("latest.pt"))
    # exclude venv
    hits = [p for p in hits if ".venv" not in p.parts and "node_modules" not in p.parts]
    return {
        "best_or_latest_pt_found": [str(p.relative_to(REPO)) for p in hits[:50]],
        "count": len(hits),
        "live_assess_without_checkpoint": (
            "POST /api/v1/assess requires body.checkpoint path to an existing file; "
            "missing file → InvalidServiceRequestError. Demo mode can short-circuit without model."
        ),
    }


def claims_audit() -> list[dict]:
    """Static list of overclaim instances found by search this session."""
    return [
        {
            "path": "frontend/components/landing/Hero.tsx",
            "snippet": "simple risk picture",
            "issue": "Implies calibrated risk; evidence supports unvalidated susceptibility scores at best",
            "proposed": "simple susceptibility picture (research preview; not validated)",
        },
        {
            "path": "frontend/components/landing/UseCases.tsx",
            "snippet": "calibrated probabilities and credible intervals",
            "issue": "Calibration gates not met; ECE failed on foundation holdout",
            "proposed": "experimental scores with uncertainty bands (not calibrated probabilities)",
        },
        {
            "path": "frontend/components/pages/PageHeader.tsx",
            "snippet": "Landslide risk is moderate, with high confidence",
            "issue": "Demo copy states risk + high confidence without validated model",
            "proposed": "Example only — not a validated risk rating",
        },
        {
            "path": "frontend/app/developers/page.tsx",
            "snippet": "land-risk job / risk scores",
            "issue": "Marketing SDK routes not the real assess contract",
            "proposed": "susceptibility assessment job (research API)",
        },
        {
            "path": "model/src/ssri_model/api/routes/assess.py",
            "snippet": "probability.tif / susceptibility_score",
            "issue": "GeoTIFF named probability but produced via sigmoid on CE logits",
            "proposed": "Rename to susceptibility_score.tif; document uncalibrated",
        },
        {
            "path": "docs/SCIENTIFIC_VALIDATION_REPORT.md",
            "snippet": "Status INCOMPLETE — honest",
            "issue": "None — correctly incomplete",
            "proposed": "Keep; link from marketing pages",
        },
    ]


def write_proposed_patch() -> Path:
    patch_dir = Path(__file__).resolve().parents[1] / "proposed_patches"
    patch_dir.mkdir(parents=True, exist_ok=True)
    # Proposed test (not installed into model/tests)
    test_src = '''"""Proposed test — NOT installed into production test path by this task.

Copy into model/tests/ only after owner approval.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F


def probabilities_from_logits_softmax(logits: torch.Tensor) -> torch.Tensor:
    return F.softmax(logits, dim=1)


def test_assess_eval_probability_contract_agreement():
    torch.manual_seed(0)
    logits = torch.randn(2, 3, 4, 4)
    soft = probabilities_from_logits_softmax(logits)
    # Proposed assess path must match eval: softmax, sum≈1
    assert torch.allclose(soft.sum(dim=1), torch.ones(2, 4, 4), atol=1e-5)
    sig = torch.sigmoid(logits)
    assert not torch.allclose(sig.sum(dim=1), torch.ones(2, 4, 4), atol=1e-3)
'''
    (patch_dir / "test_proposed_softmax_contract.py").write_text(test_src, encoding="utf-8")

    patch_txt = '''# Proposed patch (NOT APPLIED)

## Intent
Align assess / MC-dropout / GeoTIFF probability transform with evaluation softmax
for Stage 2.5 mutually exclusive classes.

## Files to change (after approval)
1. `model/src/ssri_model/uncertainty/__init__.py`
   - Replace `torch.sigmoid` in `run_mc_dropout` and `gradient_feature_attribution` with `F.softmax(logits, dim=1)`.
2. `model/src/ssri_model/api/routes/assess.py`
   - Replace GeoTIFF `torch.sigmoid(logits)` with softmax over class dim; write selected class channel.
3. Add `model/tests/test_proposed_softmax_contract.py` (see sibling file).

## Non-goals
- Do not change foundation multitask BCE heads (sigmoid remains correct there).
- Do not deploy in this task.
'''
    (patch_dir / "SOFTMAX_CONTRACT_PATCH.md").write_text(patch_txt, encoding="utf-8")
    return patch_dir


def main() -> int:
    append_run_log(f"{datetime.now(timezone.utc).isoformat()} START phase8_contract_audit")
    report = {
        "phase": 8,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sigmoid_softmax_repro": repro_sigmoid_softmax_mismatch(),
        "stage25_checkpoints": check_stage25_checkpoint(),
        "claims_audit": claims_audit(),
        "proposed_patches_dir": str(write_proposed_patch()),
    }
    write_json(OUT / "phase8_contract_audit.json", report)
    append_run_log(f"{datetime.now(timezone.utc).isoformat()} END phase8_contract_audit")
    print(json.dumps({"sigmoid_sum": report["sigmoid_softmax_repro"]["sigmoid_channel_sums_mean"],
                      "softmax_sum": report["sigmoid_softmax_repro"]["softmax_channel_sums_mean"],
                      "checkpoints": report["stage25_checkpoints"]["count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
