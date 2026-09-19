# SSRI Completion Scorecard

**Updated:** 2026-09-09  
**Do not treat this as PRD-complete.**

## Engineering

| Item | Status |
|------|--------|
| Live FeatureStack pipeline | DONE |
| USGS catalog on disk | DONE — **251,344** |
| FeatureStack training set | DONE — **v3 n=240** (was v2 n=80) |
| Pseudo-absence + split audit | DONE — documented |
| Foundation checkpoint | DONE — `ssri-foundation-v2.pt` |
| EIGEN-6C4 provider (fail-closed) | DONE — raster **missing** |
| African target ingest tooling | DONE — UGLC download **blocked** (Zenodo 504) |
| DANN GRL engineering | DONE (synthetic tests) |
| DANN on real target | NOT STARTED |

## Scientific

| Item | Status |
|------|--------|
| Source AUC ≥ 0.88 | **FAILED** — test tile **0.750** (was 0.574) |
| Source ECE ≤ 0.08 | **FAILED** — test ECE **0.094** |
| African transfer AUC ≥ 0.74 | **NOT MEASURED** |
| DANN ΔAUC ≥ 0.12 | **NOT MEASURED** |
| Gravity = EIGEN-6C4 | **NOT YET** — still WGM2012 labelled honestly |

## Overall

```text
RESEARCH READY — LIVE PIPELINE VERIFIED
SOURCE FOUNDATION IMPROVED — AUC GATE NOT MET
SCIENTIFIC VALIDATION INCOMPLETE
```
