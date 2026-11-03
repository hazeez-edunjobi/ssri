# Reproduce landslide due-diligence

Branch: `poc/landslide-due-diligence`  
From repo root. Poetry env under `model/` (scikit-learn 1.9.1 installed via pip into that env for poc scripts only; `model/pyproject.toml` unchanged).

```powershell
# Phase 0 tests (baseline counts: 93 + 9)
poetry -C model run pytest tests/test_api_assess.py tests/test_api_assess_audit.py tests/test_demo_mode_assess.py tests/test_model_architecture.py tests/test_multitask_model.py tests/test_inference.py tests/test_evaluation_metrics.py tests/test_training_metrics.py -q --tb=no
poetry -C model run pytest ../poc/landslide4sense/integration/test_deepslide_engine.py -q --tb=no

# Phase 2
poetry -C model run python ../poc/landslide_due_diligence/scripts/phase2_data_audit.py

# Phase 3
poetry -C model run python ../poc/landslide_due_diligence/scripts/phase3_baselines.py

# Phase 8
poetry -C model run python ../poc/landslide_due_diligence/scripts/phase8_contract_audit.py
```

Verify PROTOCOL hash unchanged:

```powershell
Get-FileHash poc\landslide_due_diligence\PROTOCOL.md -Algorithm SHA256
# expect BD2A86BC5A883123B476F9CFD759026836740C60E09FD6A9ACE3BD088213DDFE
```
