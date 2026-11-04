# Copy audit — changes made (blocker close)

Required framing: relative susceptibility **rankings**; **NOT_VALIDATED**; never risk / probability / detection / validated as product status.

## Changes in this close-out

| Location | Before | After |
|----------|--------|-------|
| `uncertainty/__init__.py` note | “calibration parameters, not scientifically validated thresholds” | “Ranking confidence bands are software heuristics… relative susceptibility rankings, not probabilities or risk estimates” |
| Assess GeoTIFF (flag on) | `*_probability.tif` | `*_ranking_score.tif` |
| Assess explanation (flag on) | template confidence text | Explicit ranking / NOT_VALIDATED / never insurance-engineering-safety |
| Operator UI alt text | “landslide risk is read from the terrain” | “relative landslide susceptibility ranking demos” |
| Operator UI banner | “not scientifically validated or production-ready” | Prefer gate wording; never “validated”; Known Limitations panel added |
| Shell evaluate / meta / API | — | `score_framing=relative susceptibility rankings` everywhere |
| README_OWNER / LIMITATIONS / DEMO / OWNER_API_GUIDE | — | Explicit never-use list |

## Remaining / UNKNOWN (owner scan)

| Location | Finding |
|----------|---------|
| Marketing pages under `frontend/app` (non-operator) | **UNKNOWN** — not exhaustively re-scanned this pass |
| `AssessResponseBody` field names like legacy confidence tiers | Still present when flag **off**; shell path replaces hazard profile payload when flag on |
| Demo assessment path | Unchanged when `SSRI_DEMO_MODE` |

## Rehearsal wording

FeatureStacks v3 validation report correctly FAILs all-sentinel channels and DISABLEs hazards below minimum — use that language in owner briefings (insufficient labelled data / channel quality FAIL), not “invalid model”.
