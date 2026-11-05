# Reproduce landslide credibility v3

## Prerequisites

- Repo checkout on branch `poc/landslide-credibility-v3`
- `cd model && poetry install`
- Existing v2 corpus at `poc/landslide_credibility/corpus/` (do not rebuild unless intentional)
- USGS catalog at `data/catalogs/usgs_landslide_v3/catalog.jsonl`

## Commands

```bash
# Phase 0 was recorded in outputs/phase0_freeze.json (tests 93+9)
# PROTOCOL_v3.md must remain hash 70FE823F… — do not edit after freeze

# Corpus extension (slope-matched resample + sealed attempt)
poetry -C model run python poc/landslide_credibility_v3/scripts/extend_corpus.py

# LOBO + freeze + sealed once
poetry -C model run python poc/landslide_credibility_v3/scripts/lobo_eval.py

# Failure analysis
poetry -C model run python poc/landslide_credibility_v3/scripts/failure_analysis.py

# Verify hashes + headline
poetry -C model run python poc/landslide_credibility_v3/scripts/verify.py

# Proposed patch tests (not in production suite)
poetry -C model run python poc/landslide_credibility_v3/proposed_patches/test_proposed_softmax_contract.py
poetry -C model run python poc/landslide_credibility_v3/proposed_patches/test_proposed_landslide_only_contract.py
```

## Headline tolerance

`verify.py` checks PROTOCOL v1/v2/v3 hashes and that NEAR B1 slope AUC re-reads as `0.891239825182349` (±0). Full LOBO with 50 km buffer is stored in `outputs/phase4_eval.json`; regenerating LOBO from scratch should match within **0.01 AUC** if corpus hashes match.

## Clean-checkout proof

From a fresh clone of this branch with corpus + outputs present (or after re-running extend+lobo), run `verify.py` and confirm `pass: true`. Record result in `outputs/phase8_verify.json` and FINAL_REPORT integrity section.
