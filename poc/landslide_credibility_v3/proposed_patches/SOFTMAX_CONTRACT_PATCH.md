# Proposed patch — sigmoid vs softmax contract (NOT APPLIED)

## Intent
Stage 2.5 CE classes are mutually exclusive. Evaluation uses `F.softmax`. Assess / MC-dropout / GeoTIFF still use `torch.sigmoid` in places → class channels do not sum to 1.

## Reproduce mismatch (minimal)

```python
import torch, torch.nn.functional as F
logits = torch.randn(1, 3, 2, 2)
soft = F.softmax(logits, dim=1)
sig = torch.sigmoid(logits)
assert torch.allclose(soft.sum(dim=1), torch.ones(1, 2, 2), atol=1e-5)
assert not torch.allclose(sig.sum(dim=1), torch.ones(1, 2, 2), atol=1e-3)
```

Run: `python proposed_patches/test_proposed_softmax_contract.py`

## Files to change (after owner approval — branch only until merge)

1. `model/src/ssri_model/uncertainty/__init__.py` — replace `torch.sigmoid` in `run_mc_dropout` and related paths with `F.softmax(logits, dim=1)`.
2. `model/src/ssri_model/attribution/__init__.py` — same for gradient attribution class probs.
3. `model/src/ssri_model/api/routes/assess.py` — GeoTIFF export: softmax over class dim; write selected class channel.
4. Install `test_proposed_softmax_contract.py` into `model/tests/` after approval.

## Non-goals
- Do not change foundation multitask BCE heads (sigmoid correct there).
- Do not deploy in this task.
