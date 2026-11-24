# SSRI — Lineament & Overburden Assessment Verification Report

**Date:** 2026-11-24  
**Scope:** Local completion of outstanding lineament and overburden assessment integration.  
**Constraint:** No Git push, no production deployment, no client contact, no retraining.  
**Scientific status:** **NOT_VALIDATED** (unchanged).

---

## 1. Initial Git checkpoint and working-tree status

| Item | Value |
|---|---|
| Branch | `main` (tracks `origin/main`) |
| HEAD / `origin/main` | `d8ac1bc` — *chore: checkpoint working SSRI assessment platform before geological integration* |
| Prior acceptance | 2026-11-23 Pre-Deployment Browser Acceptance Gate — **READY FOR HOSTING** |
| Working tree at start | Clean at `d8ac1bc` (pushed checkpoint present) |
| Working tree at end | Local uncommitted changes only (this work). **Not pushed.** |

Uncommitted at verification close:

- `model/src/ssri_model/api/geological_conditioning_overlay.py` (new)
- `model/tests/test_geological_conditioning_overlay.py` (new)
- `model/src/ssri_model/api/routes/assess.py` (wire enrich)
- `frontend/lib/conditioning.ts` (+ tests)
- `frontend/components/AssessResultModal.tsx`
- `frontend/app/dashboard/page.tsx`
- Evidence: `poc/abeokuta_lineament_overburden_assess.json`

---

## 2. Existing lineament implementation and identified gaps

### What already existed (verified in source)

| Capability | Location | Status before this work |
|---|---|---|
| Lineament vector ingest / activation | Geological catalogue (`vector_lineament`) | Present |
| Density / distance math | `release_shell/lineaments.py` | Present |
| Schema-v2 conditioning channels | `assess_conditioning.py`, channel schema v2 | Present |
| Live Stage 2.5 assess | 13-channel tensor only | Does **not** acquire or inject lineaments |
| Magnetic NE–SW themes | `magnetic_processing.publication_comparison_notes()` | Present as publication-guided notes |

### Gaps closed

1. Live `/api/v1/assess` did not attach catalogue lineament analytics or magnetic structural context to `conditioning_features`.
2. Frontend could not distinguish catalogue overlay values from inference inputs (`used_in_inference`).
3. NE–SW structural orientation was not surfaced in the assessment result UI as geological context.
4. Missing lineament data risked being conflated with “not supported” rather than “no activated vectors; themes are context only.”

### What was *not* done (by design)

- No fabricated LineString geometries from TMI.
- No claim that NE–SW themes are confirmed faults/fractures.
- No injection of lineament channels into the 13-channel Stage 2.5 checkpoint.

**Classification — Lineament assessment integration:** **PARTIAL**  
Implemented and verified for honest reporting + optional activated-vector sampling; blocked from live inference use until schema-v2 offline stack + matching checkpoint (or approved architecture change). No client lineament vectors cover Abeokuta.

---

## 3. Existing overburden implementation and identified gaps

### What already existed

| Capability | Location | Status before this work |
|---|---|---|
| `overburden_thickness` measurement type | Geological models / ingest | Present |
| Schema-v2 channel sampling | `assess_conditioning.py` | Present |
| Client Abeokuta Z column | `geo_be00a34ad6f4` | **TMI (nT), not thickness** |
| Catalogue Capetown thickness demo | `geo_a21c81893719` | Separate AOI; not Abeokuta |

### Gaps closed

1. Live assess could omit clear provenance that intersecting TMI must not be treated as thickness.
2. No catalogue nearest-neighbour thickness sampling path for activated `overburden_thickness` CSVs.
3. Frontend usage notes could imply an available catalogue value was used in inference.

### What was *not* done (by design)

- TMI Z was **not** substituted for overburden thickness.
- DEM / elevation was **not** substituted for thickness.
- No invented metre thickness for Abeokuta.

**Classification — Overburden assessment integration:** **PARTIAL**  
Honest missing-data path verified for Abeokuta; activated thickness sampling implemented and unit-tested; no scientifically defensible Abeokuta thickness dataset is available in-project.

---

## 4. Files changed and reasons

| File | Reason |
|---|---|
| `model/src/ssri_model/api/geological_conditioning_overlay.py` | Catalogue overlay: TMI geological context; optional activated overburden CSV sampling; optional activated lineament GeoJSON density/distance; never mutates inference tensor |
| `model/src/ssri_model/api/routes/assess.py` | Call enrich after `sample_conditioning_features`; note geological context count |
| `model/tests/test_geological_conditioning_overlay.py` | Unit coverage for TMI honesty, overburden sample, lineament sample |
| `frontend/lib/conditioning.ts` | `used_in_inference` / catalogue source handling; `geologicalContextLines()` |
| `frontend/lib/conditioning.test.ts` | FE unit coverage for overlay honesty + NE–SW context |
| `frontend/components/AssessResultModal.tsx` | Display geological context block in results |
| `frontend/app/dashboard/page.tsx` | Summary geological context on last result |

---

## 5. Technical description of completed corrections

### Pipeline (preserved)

```text
Dataset (Abeokuta TMI) → Geological catalogue (validated, inactive for Stage 2.5)
Live AOI → 13-channel acquisition → Stage 2.5 inference (unchanged)
         ↘ sample_conditioning_features (v1 → unavailable layers)
         ↘ enrich_conditioning_with_geological_catalogue
              · geological_context from intersecting validated TMI footprints
              · overburden/lineament layers only if activated+validated covering data
              · used_in_inference=false always for catalogue overlays
API response → Frontend result modal / dashboard summary
```

### Compatibility

- Active checkpoint unchanged: `ssri-model-e7af3afcd0` (`best.pt`), Stage 2.5 **13 channels**.
- No retraining; no extra channels passed into the checkpoint.
- Abeokuta dataset `geo_be00a34ad6f4` interpretation preserved: Z=TMI; CRS 32632→32631→4326; publication themes including NE–SW.

---

## 6. Tests executed and exact results

| Suite | Result |
|---|---|
| `tests/test_geological_conditioning_overlay.py` | **3 passed** |
| `tests/test_assess_conditioning.py` (with overlay suite) | included in **6 / 10 passed** batches |
| `tests/test_abeokuta_crs_magnetic.py` | included — **10 passed** total with overlay+conditioning |
| `tests/test_assess_geotiff_and_conditioning.py` + `test_hazard_factors_v2.py` | **16 passed** |
| `frontend/lib/conditioning.test.ts` (`node --test`) | **6 passed** |

Full headed Playwright acceptance gate was **not** re-run end-to-end (avoids unnecessary re-ingest/magnetic reprocessing per mission §7/§8). Targeted browser smoke was performed instead (below).

---

## 7. Previous versus new Abeokuta assessment results

**AOI:** lat `7.25`, lon `3.25` (inside `geo_be00a34ad6f4` display bbox)  
**Checkpoint:** `ssri-model-e7af3afcd0` / sha256 `d912027e17ed532687f9d2a2c74fd3c18ca8c812ae49107d939ade19dde5d004`  
**Evidence:** `poc/abeokuta_lineament_overburden_assess.json`  
**Browser confirmation assessment id:** `assess-15bd67103df8879a`

| Risk category | Previous (historical) | New (2026-11-24) | Δ |
|---|---:|---:|---:|
| Subsidence | 58.0% | **58.2%** | +0.2 pp |
| Landslide | 52.8% | **52.7%** | −0.1 pp |
| Sinkhole | 49.3% | **49.2%** | −0.1 pp |

Differences are within expected Monte Carlo / acquisition noise for the same 13-channel path. **No improvement is claimed.** Scores remain relative susceptibility rankings, **NOT_VALIDATED**.

Confidence: **Low** (software heuristic; domain similarity uncalibrated).

---

## 8. Feature availability and provenance

| Feature | Available at AOI? | Used in 13-ch inference? | Provenance / note |
|---|---|---|---|
| Stage 2.5 channels (elevation…magnetics EMAG2) | Yes (live acquire) | **Yes** | Unchanged live path |
| Overburden thickness (m) | **No** | **No** | Intersecting asset is TMI; Z≠thickness; no activated thickness CSV for AOI |
| Lineament density | **No** | **No** | No activated lineament vectors covering AOI; not fabricated from TMI |
| Lineament distance | **No** | **No** | Same |
| Geological context (NE–SW, sedimentary/transitional/basement themes) | **Yes** | **No** (context only) | From `geo_be00a34ad6f4` + publication comparison notes; NOT_VALIDATED |

Missing-data warnings (verbatim intent):

- Overburden: *TMI Z is not overburden thickness and was not substituted.*
- Lineaments: *Magnetic NE–SW structural themes … are geological context only and are not converted into fabricated lineament geometries.*

---

## 9. Frontend and browser acceptance results

### Targeted browser smoke (2026-11-24)

| Check | Result |
|---|---|
| Local acceptance session → `/geological` | PASS — catalogue lists Abeokuta + footprints |
| Reopen `geo_be00a34ad6f4` | PASS — TMI metadata, CRS roles, NOT_VALIDATED, products intact |
| `/dashboard` API ready + 3 WGS84 footprints | PASS |
| Run assess at 7.25, 3.25 | PASS — modal scores 58.2 / 52.7 / 49.2% |
| Geological context UI | PASS — NE–SW + magnetic themes; not faults |
| Overburden / lineament honesty | PASS — unavailable; catalogue-only usage note; TMI not thickness |

### November 23 gate capabilities (spot-checked intact)

Next.js, FastAPI ready (Postgres/Redis/queue), geological catalogue, Abeokuta reopen, dashboard footprints — **PASS** in this session. Full headed Playwright re-ingest was intentionally skipped.

Local acceptance bypass remains `NEXT_PUBLIC_SSRI_LOCAL_ACCEPTANCE_SESSION=1` in **local** `.env.local` only; not promoted to production config in this work.

---

## 10. Remaining limitations and scientific validation status

| Item | Class | Notes |
|---|---|---|
| Live 13-ch inference unchanged | PASS | Compatibility preserved |
| TMI geological context on assess | PASS | Surfaced; NOT_VALIDATED |
| Honest overburden missing-data | PASS | No TMI/DEM substitution |
| Honest lineament missing-data | PASS | No fabricated vectors |
| Activated overburden sampling path | PASS (unit) | Requires activated thickness CSV covering AOI |
| Activated lineament sampling path | PASS (unit) | Requires activated GeoJSON covering AOI |
| Abeokuta overburden thickness metres | **BLOCKED** | Need external scientifically defensible thickness dataset |
| Abeokuta lineament vectors for density/distance | **BLOCKED** | Need client/validated lineament geometries |
| Inject lineament/overburden into live scores | **BLOCKED** | Needs schema-v2 offline stack + compatible checkpoint / approved retrain |
| Independent scientific validation | FAIL (by policy) | Remains **NOT_VALIDATED** |

---

## 11. Final local readiness decision

| Outstanding area | Classification |
|---|---|
| Lineament assessment & integration | **PARTIAL** |
| Overburden assessment & integration | **PARTIAL** |
| Existing platform (assess / catalogue / CRS / magnetic products) | **PASS** (no regression observed) |

### Decision

**LOCAL VERIFICATION COMPLETE — READY FOR REVIEW / APPROVAL TO COMMIT**

Not claiming production scientific readiness. Not claiming lineament or overburden features are now live inference inputs. Honest assessment analytics and Abeokuta re-run are verified locally.

**Stopped here. No Git push. No deployment. Awaiting explicit approval.**
