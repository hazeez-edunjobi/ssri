# Landslide-only assess contract (PROPOSED, not applied)

## Behaviour after owner merge

| Class | Response |
|-------|----------|
| landslide | Relative susceptibility **index** from terrain (slope-only shipped product for v3 NO-GAIN) |
| subsidence | `availability: "not_available"` — **never** a numeric score |
| sinkhole | `availability: "not_available"` — **never** a numeric score |

## Endpoint return shape (proposed)

```json
{
  "landslide": {
    "availability": "available",
    "index_name": "ssri_landslide_slope_only_v3",
    "score": 0.0,
    "score_meaning": "relative ranking score on [0,1] from training-slope CDF; not a probability"
  },
  "subsidence": {"availability": "not_available", "score": null},
  "sinkhole": {"availability": "not_available", "score": null},
  "framing": "relative landslide susceptibility index derived from terrain/environment; evaluated only on CONUS held-out blocks; a ranking score, not a probability and not a risk estimate; not independently reviewed",
  "credibility_badge": "L1 — reproducible baselines on leakage-free blocks (NO-GAIN: slope-only product)"
}
```

## What it never claims
- Validated risk, absolute probability, detection of landslides, calibrated event odds, production geological truth, or independent scientific review (L4).

## Softmax
Build on `SOFTMAX_CONTRACT_PATCH.md` for any Stage 2.5 multi-class path that remains.

## Tests
See `test_proposed_landslide_only_contract.py` (copy to `model/tests/` after approval).
