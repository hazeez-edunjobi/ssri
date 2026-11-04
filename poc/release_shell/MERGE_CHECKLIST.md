# Merge checklist (owner only — agent does not merge)

## Orphan inventory (do not lose these branches)

| Asset | Branch / location | Notes |
|-------|-------------------|--------|
| DeepSlide 9 tests | **`poc/landslide-credibility-v3`** → `poc/landslide4sense/integration/test_deepslide_engine.py` (also on `poc/landslide-credibility`) | **Not on `main` / `poc/release-shell`**. Restore before claiming 93+9 on merge. |
| DeepSlide engine (unwired) | same branches under `poc/landslide4sense/` | Keep unwired |
| Softmax proposed patches (pre-shell) | `poc/landslide-credibility` + `poc/landslide-due-diligence` → `proposed_patches/` | Superseded in spirit by flag-gated shell softmax on this branch |
| PROTOCOL_v3 + slope index cycle | **`poc/landslide-credibility-v3`** → `poc/landslide_credibility_v3/` (`PROTOCOL_v3.md`, reports) | Some deliverables (`SHIPPED_INDEX.md`, `FINAL_REPORT.md`, `proposed_patches/`) may still be **uncommitted** on that branch — commit there before discarding |
| Release shell | **`poc/release-shell`** (this branch) | Feature-flagged; default off |

## Before merge

1. `poetry -C model run python poc/release_shell/scripts/verify.py` → pass  
2. Assess suite **93** + DeepSlide **9** (after restoring deepslide path from credibility-v3)  
3. New `tests/test_release_shell_*.py` pass  
4. `SSRI_RELEASE_SHELL` default **off**  
5. No weights committed; SYNTHETIC only for demos  
6. Copy audit complete (`COPY_AUDIT.md`)  
7. Decide whether to port operator UI to release-shell routes or keep API guide

## Rollback

Revert this branch / unset `SSRI_RELEASE_SHELL` and `SSRI_ASSESS_SOFTMAX`. Classic `/training` and sigmoid assess remain.

## Do not

Deploy without approval; promote SYNTHETIC or FeatureStacks-v3-with-sentinel checkpoints; wire DeepSlide; claim validated.
