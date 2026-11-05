# Independent geoscientist review checklist (L4 — human only)

Agent **cannot** claim L4. Reviewer should work from a clean checkout of `poc/landslide-credibility-v3` plus `FINAL_REPORT.md` and `outputs/`.

## Leakage

- [ ] Confirm held-out LOBO blocks never used for threshold/seed selection in their own fold (`lobo_eval.py` nested inner block only).
- [ ] Confirm 50 km buffer applied between train and hold samples.
- [ ] Confirm spent v2 test blocks labelled exploratory and excluded from Tier A/B.
- [ ] Confirm sealed fresh opened only after `phase3_freeze.json`.

## Inventory bias

- [ ] Mapping-effort concentration acknowledged (DATA_SHEET).
- [ ] Per-source caps / thinning (1 km) reviewed as adequate or not.
- [ ] Undated events: no date features used (static predictors only).

## Pseudo-replication

- [ ] Block-bootstrap CIs (not i.i.d. sample bootstrap) used for ΔAUC.
- [ ] Presence clustering residual risk stated.

## Absence design

- [ ] NEAR (5–20 km) understood as headline, not field truth.
- [ ] FAR (≥20 km) reported.
- [ ] SLOPE-MATCHED used for beyond-slope claim; method (resample to slope bins) accepted or challenged.

## Power

- [ ] `phase1_power.json`: LOBO MDD ≈ 0.06 ≤ 0.08 → NO-GAIN (not INCONCLUSIVE) is protocol-correct if Tier A fails.
- [ ] Sealed n=14 underpowered; Tier B unavailable.

## CI method

- [ ] Block-bootstrap ≥1000 resamples of held-out blocks.
- [ ] ECE/Brier informational only.

## Product honesty

- [ ] Slope-only index labelled as such; no risk/probability language.
- [ ] Sinkhole/subsidence “not available” contract reviewed.
- [ ] Production `/api/v1/assess` unchanged in this cycle; patches proposed only.
