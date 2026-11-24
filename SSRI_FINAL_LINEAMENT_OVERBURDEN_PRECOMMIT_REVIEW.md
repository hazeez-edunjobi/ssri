# SSRI — Final Lineament & Overburden Diff Review (Pre-Commit)

**Date:** 2026-11-24  
**Review mode:** Read-only inspection of local uncommitted changes (implementation not modified).  
**Prior verification:** `SSRI_LINEAMENT_OVERBURDEN_ASSESSMENT_VERIFICATION_REPORT.md`  
**Decision:** **READY WITH NON-BLOCKING NOTES**

---

## 1. Executive decision

The local lineament/overburden assessment overlay work is **relevant, safe for the live 13-channel Stage 2.5 path, and sufficiently verified** for a local Git commit.

No blocking defects were found in the diff. Known scientific and operational limitations remain correctly labelled as **PARTIAL** / **BLOCKED** / **NOT_VALIDATED** and are not treated as software failures.

Non-blocking notes (do not block commit):

1. Credible intervals in the Abeokuta evidence payload are degenerate (identical lower/upper bounds) — pre-existing uncertainty-reporting limitation, not introduced as calibrated uncertainty by this change.
2. Overlay enumerates at most 200 catalogue records (`storage.list(limit=200)`).
3. Overlay imports private helpers from `release_shell.lineaments` (`_point_segment_distance`, `_segment_length_in_window`).
4. Dashboard summary calls `geologicalContextLines(...)` twice per render (cosmetic inefficiency).

**Do not commit / push / deploy until explicit approval.** This review did not perform any Git write operation.

---

## 2. Verified Git baseline and working-tree state

| Check | Result |
|---|---|
| Branch | `main` |
| HEAD | `d8ac1bc257a435cf22cc3b2bb14aa9b24e9832f1` |
| HEAD message | `chore: checkpoint working SSRI assessment platform before geological integration` |
| `origin/main` | Same as HEAD (`d8ac1bc…`) |
| Tracking | `main...origin/main` (no ahead/behind indicated) |
| Staged changes | None |
| Unstaged modifications | 5 tracked files |
| Untracked | 4 files (implementation + evidence + prior verification report) |
| Unexpected unrelated churn | **None observed** |

`git diff --stat` (tracked only):

```text
 frontend/app/dashboard/page.tsx           | 14 +++++++-
 frontend/components/AssessResultModal.tsx | 21 +++++++++++
 frontend/lib/conditioning.test.ts         | 39 ++++++++++++++++++++
 frontend/lib/conditioning.ts              | 60 +++++++++++++++++++++++++++++--
 model/src/ssri_model/api/routes/assess.py | 14 ++++++++
 5 files changed, 145 insertions(+), 3 deletions(-)
```

Baseline matches the expected checkpoint. Changes remain local and uncommitted.

---

## 3. Complete changed-file inventory

### Modified (tracked)

| Path | Role |
|---|---|
| `model/src/ssri_model/api/routes/assess.py` | Wire catalogue enrich after stack sampling |
| `frontend/lib/conditioning.ts` | Overlay-aware usage flags + geological context helper |
| `frontend/lib/conditioning.test.ts` | FE unit coverage for honesty / NE–SW context |
| `frontend/components/AssessResultModal.tsx` | Result modal geological context block |
| `frontend/app/dashboard/page.tsx` | Last-result geological context summary |

### Untracked (new)

| Path | Role |
|---|---|
| `model/src/ssri_model/api/geological_conditioning_overlay.py` | Core overlay implementation |
| `model/tests/test_geological_conditioning_overlay.py` | Backend unit tests |
| `poc/abeokuta_lineament_overburden_assess.json` | Local Abeokuta assess evidence payload |
| `SSRI_LINEAMENT_OVERBURDEN_ASSESSMENT_VERIFICATION_REPORT.md` | Prior verification report (scope documentation) |

### Review deliverable (this file)

| Path | Role |
|---|---|
| `SSRI_FINAL_LINEAMENT_OVERBURDEN_PRECOMMIT_REVIEW.md` | This pre-commit review |

No unexpected source-tree modifications (no checkpoint, `.env`, migration, Compose, or 13-channel architecture edits).

---

## 4. File-by-file review findings

### `model/src/ssri_model/api/geological_conditioning_overlay.py` (new) — PASS

**What changed:** New post-inference analytics module. Attaches:

- validated TMI catalogue geological context (publication themes, NE–SW structural theme, CRS/display bbox provenance);
- optional activated+validated `overburden_thickness` nearest-sample values;
- optional activated+validated lineament density/distance from GeoJSON;
- always sets catalogue overlay `used_in_inference=false`.

**Why necessary:** Live assess previously omitted catalogue honesty and magnetic context from `conditioning_features`.

**Scope:** In scope. Does not mutate feature tensors or checkpoints.

**Notes (non-blocking):**

- Reuses private lineament geometry helpers (encapsulation smell only).
- Catalogue scan capped at 200 datasets.
- Overburden/lineament values only fill stack layers when stack status is already `unavailable` — correct for v1 live stacks.

### `model/tests/test_geological_conditioning_overlay.py` (new) — PASS

Covers: TMI context without claiming thickness; activated thickness sampling with `used_in_inference=false`; activated lineament sampling without fault claims. Appropriate and focused.

### `model/src/ssri_model/api/routes/assess.py` — PASS

Diff inserts enrich **after** `sample_conditioning_features` and **after** MC inference / attribution already ran on the original feature tensor (lines ~442–523 resolve/run inference; enrich ~720+). Adds `geological_context_count` note when context exists.

No change to checkpoint resolution, channel-count enforcement, or hazard score computation path.

### `frontend/lib/conditioning.ts` — PASS

Adds `used_in_inference` / `source` typing; treats catalogue overlays as **not** used in assessment; adds `geologicalContextLines()` that labels NE–SW with `NOT_VALIDATED` and “not confirmed faults”.

### `frontend/lib/conditioning.test.ts` — PASS

Adds catalogue-overlay and geological-context assertions. No unrelated churn.

### `frontend/components/AssessResultModal.tsx` — PASS

Adds geological context panel with explicit disclaimers (not faults / not thickness / not hazard scores / NOT_VALIDATED). Conditioning groups remain unavailable/honest for Abeokuta.

### `frontend/app/dashboard/page.tsx` — PASS

Shows up to four geological context lines on last-result summary. Does not invent measurements. Double helper call is non-blocking.

### `poc/abeokuta_lineament_overburden_assess.json` — PASS (evidence)

Parsed locally:

| Field | Value |
|---|---|
| `assessment_id` | `assess-6c86be5b2db90641` |
| `schema_channel_count` | **13** |
| Scores | ~0.582 / 0.527 / 0.492 |
| Overlay `used_in_inference` | **false** |
| Layers | overburden/lineaments `unavailable`, `used=false`, values `null` |
| Context | `geo_be00a34ad6f4`, `z_meaning=total_magnetic_intensity`, NE–SW theme, `NOT_VALIDATED`, `not_overburden_thickness=true` |
| CI 80/95 | Degenerate (lower == upper == point estimate) |

### `SSRI_LINEAMENT_OVERBURDEN_ASSESSMENT_VERIFICATION_REPORT.md` — PASS (docs)

Consistent with the inspected code and evidence. Suitable companion artifact for the commit if included.

---

## 5. Geological correctness findings

| Requirement | Finding |
|---|---|
| Abeokuta CRS metadata respected | PASS — context records `crs=EPSG:32632`, `working_crs=EPSG:32631`, display bbox WGS84; AOI queried in lon/lat |
| TMI Z not treated as thickness/elevation/depth | PASS — `z_meaning=total_magnetic_intensity`; explicit “TMI Z is not overburden thickness…” reason; `not_overburden_thickness=true` |
| NE–SW as publication-guided, not confirmed faults | PASS — themes from `publication_comparison_notes()`; FE/API disclaimers; `not_confirmed_faults_or_fractures=true` |
| No synthetic lineament geometries as evidence | PASS — Abeokuta path reports unavailable; no fabricated vectors |
| Thickness only from validated thickness datasets | PASS — sampling gated on `measurement_type=overburden_thickness` + activated + validated |
| Missing data clearly communicated | PASS — API reasons + FE unavailable states |
| Catalogue vs inference distinction | PASS — `used_in_inference=false` / catalogue usage notes |
| No fabricated hazard labels | PASS — themes marked not hazard labels; scientific status NOT_VALIDATED |

---

## 6. Model compatibility findings

| Requirement | Finding |
|---|---|
| Live Stage 2.5 remains 13-channel | PASS — evidence `schema_channel_count=13`; assess still enforces checkpoint `in_channels` vs tensor shape |
| Active checkpoint unchanged | PASS — `active.json` → `ssri-model-e7af3afcd0`; `best.pt` SHA256 `D912027E17ED5326…` matches prior assess notes |
| No silent channel injection | PASS — enrich runs after inference; returns analytics only |
| No false claim that overlays influenced scores | PASS — API + FE mark unused |
| No claim that schema-v2 is live | PASS — copy states live AOI is v1 / 13-channel |
| Synthetic rehearsal provenance not misrepresented | PASS — checkpoint/registry identity unchanged; NOT_VALIDATED retained |

---

## 7. API / frontend integration findings

| Check | Finding |
|---|---|
| `/api/v1/assess` attaches conditioning enrichment | PASS |
| Missing catalogue data does not break assess | PASS — Abeokuta HTTP 200 with unavailable layers |
| FE safely consumes new optional fields | PASS — helpers tolerate missing/partial payloads |
| Modal distinguishes context vs inference features | PASS |
| Dashboard does not imply unavailable measurements exist | PASS — shows Unavailable + reasons / context themes |
| Existing score presentation compatible | PASS — hazard chips unchanged; scores comparable to historical |
| Unrelated API/FE behaviour | PASS — diff limited to conditioning presentation wiring |

---

## 8. Test evidence and exact commands

### Re-executed during this review (2026-11-24)

```text
poetry -C model run pytest tests/test_geological_conditioning_overlay.py tests/test_assess_conditioning.py -q --tb=line
→ 6 passed in 20.67s

node --test frontend/lib/conditioning.test.ts
→ 6 passed (0 fail)
```

### Supported by prior verification report (not re-run here)

| Evidence | Result |
|---|---|
| `test_abeokuta_crs_magnetic` + overlay/conditioning batch | 10 passed (prior report) |
| `test_assess_geotiff_and_conditioning` + `test_hazard_factors_v2` | 16 passed (prior report) |
| Targeted browser smoke (catalogue reopen, dashboard footprints, assess UI honesty) | PASS (prior report) |
| Full headed Playwright acceptance gate | Intentionally not repeated |

### Checkpoint integrity check (this review)

```text
Get-FileHash ...\ssri-model-e7af3afcd0\best.pt -Algorithm SHA256
→ D912027E17ED532687F9D2A2C74FD3C18CA8C812AE49107D939ADE19DDE5D004
```

---

## 9. Known limitations

| Topic | Status | Comment |
|---|---|---|
| Lineament live inference use | PARTIAL | Sampling/reporting only; 13-ch model does not consume lineaments |
| Overburden live inference use | PARTIAL | Sampling supported when activated thickness exists; Abeokuta has none |
| Abeokuta thickness metres | BLOCKED | External scientifically defensible dataset required |
| Abeokuta lineament vectors | BLOCKED | External/validated geometries required |
| Schema-v2 live injection | BLOCKED | Requires compatible stack + checkpoint / approved retrain |
| Scientific validation | NOT_VALIDATED | Unchanged |
| Credible intervals | Limitation | Evidence shows identical CI bounds; do **not** treat as meaningful calibrated uncertainty |

These limitations are correctly disclosed by the implementation and do **not** constitute commit blockers for the agreed overlay scope.

---

## 10. Blocking defects

**None found.**

No evidence of TMI→thickness substitution, fabricated lineaments, silent channel injection, checkpoint replacement, or unrelated destructive churn.

---

## 11. Explicit recommendation

### Decision: **READY WITH NON-BLOCKING NOTES**

Recommended local commit contents (when approved):

1. Implementation + tests:
   - `model/src/ssri_model/api/geological_conditioning_overlay.py`
   - `model/tests/test_geological_conditioning_overlay.py`
   - `model/src/ssri_model/api/routes/assess.py`
   - `frontend/lib/conditioning.ts`
   - `frontend/lib/conditioning.test.ts`
   - `frontend/components/AssessResultModal.tsx`
   - `frontend/app/dashboard/page.tsx`
2. Documentation / evidence (optional but recommended):
   - `SSRI_LINEAMENT_OVERBURDEN_ASSESSMENT_VERIFICATION_REPORT.md`
   - `poc/abeokuta_lineament_overburden_assess.json`
   - `SSRI_FINAL_LINEAMENT_OVERBURDEN_PRECOMMIT_REVIEW.md` (this file)

Suggested commit focus (message drafting only; **not** executed): document honest catalogue overlays for lineament/overburden/TMI context without altering Stage 2.5 inference.

### Stop

No commit, push, or deploy performed. Awaiting explicit approval before any Git operation.
