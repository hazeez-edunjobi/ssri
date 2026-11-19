# SSRI — Lineament & overburden frontend visibility

**Date (UTC):** 2026-11-19  
**Baseline before fix:** `51fd4d0` on `main` / `origin/main`  
**Fix commit:** `e2a9bd87978557abf8981347245adeec4d883c3f` (`e2a9bd8`)

---

## Verdict — root cause

**Missing / weak frontend presentation (discoverability), not a deployment or API mapping failure.**

| Candidate cause | Finding |
|-----------------|---------|
| Deployment / version mismatch | **Ruled out.** Vercel JS for `/dashboard` already contained `conditioning_features`, `lineament`, `overburden`, `Download GeoTIFF`, `onrender.com`. |
| API response mapping issue | **Ruled out.** `submitAssess` returns the JSON body as `AssessResponse` without stripping fields. Types already included `conditioning_features`. |
| Missing production data as “broken UI” | **Contributing UX factor.** Live AOI is schema **v1** (13 channels); backend correctly returns `status=unavailable` for overburden/lineaments. Users looking for labelled “Lineaments” / “Overburden” analytics saw only a compact technical list (“Conditioning layers at sample cell” + snake_case keys) or mistook unavailable for “not integrated.” |
| Missing frontend implementation | **Partial.** Backend + a minimal modal block existed in `51fd4d0`, but there were no dedicated **Lineaments** / **Overburden thickness** analytics panels, no always-on summary when the modal is closed, and the section was gated on `conditioning_features?.layers` (hidden if the field was absent). |

Information flow before the fix:

1. Backend `sample_conditioning_features` → `AssessResponseBody.conditioning_features.layers`  
2. Frontend types + modal list under “Conditioning layers…”  
3. **Stopped for users** at presentation: not titled as Lineaments / Overburden, easy to miss after hazard cards, not mirrored on the dashboard analytics summary.

---

## Phase 1 — Trace

### Backend

- `model/src/ssri_model/api/assess_conditioning.py`  
  Layers: `overburden_thickness`, `lineament_density`, `lineament_distance`  
  Statuses: `available` \| `nodata` \| `unavailable` (never fabricates zeros)  
  Units / reasons attached per layer.
- Wired in `routes/assess.py` and demo path (`demo_assessment.py` → all unavailable).
- Production OpenAPI `AssessResponseBody` includes `conditioning_features`.

### Frontend (pre-fix)

- Types: `frontend/lib/api.ts` → `conditioning_features`  
- Modal: `AssessResultModal` rendered a single technical list when `layers` existed  
- Report HTML: snake_case conditioning dump  
- Dashboard: “Last result” reopen button only — no lineament/overburden summary  
- Map: no lineament/overburden overlay (correct for live v1; no fabricated layer)

---

## Phase 2 — Deployment verification

| Check | Result |
|-------|--------|
| Intended commit on git | `51fd4d0` aligned local/`origin/main` before this fix |
| Vercel contains prior conditioning strings | **Yes** (dashboard bundle probe) |
| Frontend → production API | Bundles reference `onrender.com` / `ssri-api` |
| Production API schema fields | `conditioning_features` present on OpenAPI |
| Authenticated live assess body | **Not re-run** (auth / Redis readiness still constrained); schema + code path verified |

Successful prior deploy of `51fd4d0` did **not** mean the UX was discoverable as “Lineament” and “Overburden” analytics.

---

## Phase 3 — Frontend completion (this pass)

Implemented:

1. `frontend/lib/conditioning.ts` — presentation helper: always builds **Overburden thickness** and **Lineaments** groups; honest unavailable when API omits payload; never coerces null → 0.  
2. `AssessResultModal` — dedicated titled panels with status badges, values, units, reasons, sample caption.  
3. Dashboard — “Last result” card shows Lineament & overburden summary while the modal is closed.  
4. HTML report — same titled sections.  
5. Tests — `conditioning.test.ts` + report assertions.

**Not done (by design):** inventing map layers or live measurements for v1 AOI; scientific model changes; claiming unavailable data was used in inference.

---

## Phase 4 — Test evidence

| Check | Result |
|-------|--------|
| Unit: conditioning groups / NoData / unavailable / no zero coercion | **PASS** (4 tests) |
| Unit: report includes Overburden / Lineaments headings | **PASS** |
| Full `npm test` | **PASS** (25) |
| `npm run typecheck` | **PASS** |
| `npm run lint` | **PASS** |
| `npm run build` | **PASS** |
| Hazard UI path untouched beyond conditioning block + summary | Yes |
| UI screenshot (synthetic fixture mirroring new panels) | `poc/_tmp_conditioning_ui_fixture.html` — browser capture shows Overburden **unavailable**, Lineament density **nodata**, (fixture also documents available distance pattern) |

API field behaviour (code-level): v1 stacks → all three layers `unavailable`; v2 stacks report `available` / `nodata` per cell without zero-fill.

---

## Fix commit

```text
e2a9bd87978557abf8981347245adeec4d883c3f
```

Message: *Make lineament and overburden assess analytics explicitly visible.*

Files in the fix:

- `frontend/lib/conditioning.ts` (new)  
- `frontend/lib/conditioning.test.ts` (new)  
- `frontend/components/AssessResultModal.tsx`  
- `frontend/app/dashboard/page.tsx`  
- `frontend/lib/report.ts`  
- `frontend/lib/report.test.ts`  
- `SSRI_LINEAMENT_OVERBURDEN_FRONTEND_REPORT.md`

---

## Remaining limits

- Live AOI acquisition remains **v1 / 13 channels** — production assessments will usually show **Unavailable** for these analytics until a schema-v2 offline stack (shell-applied layers) is assessed. That is correct honesty, not a missing UI.  
- Map overlays for lineaments/overburden are still not provided (no live raster/vector product on the assess path).  
- Hosted Redis/readiness and authenticated production smoke remain separate blockers (see `SSRI_FINAL_PRODUCTION_RELEASE_REPORT.md`).
