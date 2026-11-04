# Proposed patch (NOT APPLIED)

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
