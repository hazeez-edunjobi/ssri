# Reproduce

Branch: `poc/landslide-credibility`

```powershell
# Tests (expect 93 + 9)
poetry -C model run pytest tests/test_api_assess.py tests/test_api_assess_audit.py tests/test_demo_mode_assess.py tests/test_model_architecture.py tests/test_multitask_model.py tests/test_inference.py tests/test_evaluation_metrics.py tests/test_training_metrics.py -q --tb=no
poetry -C model run pytest ../poc/landslide4sense/integration/test_deepslide_engine.py -q --tb=no

# Corpus build (network: Planetary Computer STAC)
poetry -C model run python ../poc/landslide_credibility/scripts/build_corpus.py

# Disjointness
poetry -C model run python -m pytest ../poc/landslide_credibility/tests/test_split_disjoint.py -q

# Train + single test eval
poetry -C model run python ../poc/landslide_credibility/scripts/train_eval.py

# Verify hashes + headline AUC
poetry -C model run python ../poc/landslide_credibility/scripts/verify_repro.py
```

PROTOCOL_v2 SHA-256 must remain `5F63E3625717B25750868985621C6C161BDC9B31C295B7585E47BCD77796FEF5`.  
PROTOCOL v1 must remain `BD2A86BC5A883123B476F9CFD759026836740C60E09FD6A9ACE3BD088213DDFE`.
