# SSRI — Product Completion, Quality Assurance & Client Handover Readiness

**Date:** 2026-11-23  
**Scope:** Local implementation and verification only (no deploy, no client contact, no model retrain).  
**Overall decision:** **READY FOR HOSTING WITH DISCLOSED LIMITATIONS**

---

## 1. Original project baseline

SSRI is a geospatial ground-risk platform (Next.js frontend + FastAPI `ssri_model` + Celery + Postgres/Supabase + Redis) with:

- Stage 2.5 13-channel ML assess/train (`SSRIModel`) — research-ready, **NOT_VALIDATED**.
- Geological catalogue for client point-grid / lineament uploads, including Abeokuta Sheet 260 TMI magnetic processing (RTE, Gaussian, AS, FVD, THG, tilt, RAPS).
- Local output root under `data/outputs/`.
- Prior Abeokuta CRS / magnetic QA already completed; dashboard previously opened on a world-scale demotiles view without verified catalogue footprints.

Unrelated dirty/untracked work (prior reports, `data/outputs/`, infra/worker edits) was preserved and not reverted.

---

## 2. Files inspected (representative)

- `AGENTS.md`, `About.md`, prior `SSRI_*` completion/QA reports
- `model/src/ssri_model/api/` (app, assess, geological, jobs, production_gate, config)
- `model/src/ssri_model/geological/` (service, models, tmi, validate, magnetic_processing, abeokuta_*)
- `model/src/ssri_model/worker/tasks.py`, infrastructure retry/heartbeat/job store
- `frontend/app/dashboard/page.tsx`, `frontend/app/geological/**`, `frontend/lib/*`
- `docs/CLIENT_USER_GUIDE.md`, `ADMIN_TECHNICAL_GUIDE.md`, `DEPLOYMENT_READINESS_GUIDE.md`
- `infra/docker-compose.yml`, auth/production-gate tests

---

## 3. Files changed (this finalisation pass)

| Area | Paths |
|---|---|
| Map viewport | `frontend/lib/mapViewport.ts`, `mapViewport.test.ts`; `frontend/app/dashboard/page.tsx` (fit bounds, footprints, layer toggle) |
| Upload / CRS / validation UX | `frontend/app/geological/page.tsx`, `frontend/app/geological/[id]/page.tsx`; `frontend/lib/crsOptions.ts`, `validationOutcome.ts`(+test); `geologicalApi.ts`; `components/geological/TmiSurveyPreview.tsx` |
| Display footprint persistence | `model/src/ssri_model/geological/service.py`, `models.py` (prior + FAIL-safe coverage) |
| Docs | `docs/CLIENT_USER_GUIDE.md`, `ADMIN_TECHNICAL_GUIDE.md`, `DEPLOYMENT_READINESS_GUIDE.md` |
| This report | `SSRI_PRODUCT_COMPLETION_AND_CLIENT_HANDOVER_REPORT.md` |

Abeokuta magnetic modules and QA tests (from earlier stages) remain in tree and were re-verified.

---

## 4. Defects discovered

1. Dashboard initialised on a near-global empty basemap view (product coverage not communicated).
2. Projected `coverage_bbox` (UTM metres) could be mistaken for lon/lat if plotted without a verified WGS84 transform.
3. Geological upload success copy incorrectly stated Abeokuta as lon/lat + EPSG:4326.
4. Validation UI showed raw PASS/WARN/FAIL without client Ready / Ready with warnings / Blocked labels.
5. CRS entry lacked recognisable EPSG catalogue options; column picks were free-text only when headers existed.
6. Geographic `display_bbox_wgs84` was not always persisted when validation overall was FAIL (coverage still known from inspect).
7. No footprint layer visibility control on the assessment map.

---

## 5. Defects fixed

1. Default product bounds / center / zoom for SW Nigeria; `fitMapToWgs84Bounds` + union of gravity + verified footprints.
2. `displayBboxFromDataset` ignores projected `coverage_bbox`; requires `display_bbox_wgs84` or geographic CRS.
3. Abeokuta upload success message corrected (easting/northing; 32632→32631→4326).
4. Client validation outcome mapping + explanatory copy.
5. Common EPSG select + free-text override; header-driven X/Y/Z selects.
6. Persist WGS84 footprint from verified transform or geographic coverage even when other checks FAIL.
7. Dataset footprint visibility toggle beside gravity overlay.

---

## 6. New functionality implemented

- Shared `mapViewport` helpers and unit tests.
- Catalogue footprint overlays on `/dashboard` with honest “no verified footprint” state.
- Client-facing validation outcomes and CRS option catalogue.
- Handover documentation triad (client / admin / deployment).
- Geographic coverage preview path for multi-extent datasets (Abeokuta + Cape Town check dataset).

---

## 7. Features verified without changes (re-tested)

- Abeokuta Sheet 260 magnetic pipeline (gridding safeguards, RTE/Gaussian/derivatives/RAPS, NOT_VALIDATED).
- Geological TMI API paths and original-file immutability.
- Job cancel/retry/heartbeat infrastructure (unit tests).
- Production gate: auth required, demo forced off, no wildcard CORS in production.
- Stage 2.5 assess remains separate from TMI catalogue (no EMAG2 overwrite, no fabricated risk from TMI CSV).

---

## 8. Backend test results

| Suite | Result |
|---|---|
| `test_magnetic_analytical_qa` + `test_abeokuta_crs_magnetic` + `test_geological_tmi` | **27 passed** |
| `test_geological_tmi` + `test_geological_ingest` (rerun) | **27 passed** |
| Auth / jobs / retry / production gate / geological acceptance | **54 passed** |

Commanded under `model/` via Poetry. Full monolithic pytest of the entire `tests/` tree was not required for this gate; targeted suites covering the handover surfaces were executed.

---

## 9. Frontend test results

| Check | Result |
|---|---|
| `npm test` (includes mapViewport + validationOutcome) | **74 passed** |
| `npm run typecheck` | **PASS** (exit 0) |
| `npm run lint` | **PASS** (exit 0) |

---

## 10. Production build result

`frontend`: `npm run build` — **PASS** (compiled, TypeScript OK, 26 routes generated). Warning only: unset `metadataBase` for OG images (non-blocking).

---

## 11. End-to-end acceptance results

| Step | Result |
|---|---|
| Persist Abeokuta `display_bbox_wgs84` via validate | **PASS** ≈ `[2.99, 6.99, 3.51, 7.51]` |
| Upload/declare/validate second geographic dataset (Cape Town EPSG:4326 regular grid) | **PASS** (`geo_a21c81893719`, overall PASS, box ≈ `[18.4, -33.96, 18.54, -33.82]`) |
| Distinct extents (Abeokuta vs Cape Town) | **PASS** |
| Magnetic ops / provenance (prior QA + 27-test suite) | **PASS WITH LIMITATIONS** (NOT_VALIDATED; not publication-identical) |
| Browser click-through login → download | **NOT TESTED** in headed browser this pass (API/service + unit/build coverage used instead) |

Malformed / incompatible operations remain blocked by validation `can_process` / FAIL gates (covered by geological acceptance + TMI tests).

---

## 12. Map and CRS verification results

| Check | Status |
|---|---|
| Neutral product start (not world overview) | **PASS** |
| Abeokuta UTM source → WGS84 display footprint | **PASS** |
| Second CRS/extent (Cape Town 4326) | **PASS** |
| Reject plotting projected metres as lon/lat | **PASS** (unit + service rules) |
| Layer visibility (gravity + footprints) | **PASS** (implemented) |
| Analysis raster overlays on dashboard for every magnetic product | **PASS WITH LIMITATIONS** (detail page previews/exports; dashboard is assess-centric with footprints) |

---

## 13. Security findings

| Topic | Finding |
|---|---|
| Auth in production | Production gate requires `SSRI_AUTH_ENABLED`; development mode must be false |
| Demo mode | Forced off in production/staging |
| CORS | Wildcard rejected in production; fail-closed if unset |
| Geological mutations | Require operator/admin or `manage_geological` API key |
| Secrets | Service-role / JWT stay server-side; guides list names only |
| Client errors | Operator-facing messages; stack traces intended for logs |

**Development auth defaults remain unsafe if copied blindly into production** — hosting must flip production flags explicitly.

---

## 14. Remaining limitations

- Scientific status stays **NOT_VALIDATED** for ML assess and magnetic products.
- Magnetic maps are for comparison with published interpretations, not confirmed structure/hazard claims.
- Full headed Playwright e2e of login→download was not executed in this pass.
- Assessment dashboard does not replace the geological detail page for magnetic product galleries.
- Hosting (HTTPS, managed Redis/Postgres, shared volume) is documented but **not performed**.
- `metadataBase` OG warning remains.

---

## 15. Hosting requirements

See `docs/DEPLOYMENT_READINESS_GUIDE.md`: Frontend + FastAPI + Celery worker + Postgres + Redis + persistent `SSRI_OUTPUT_ROOT`, HTTPS, migrations, health/ready probes, backups, auth/CORS/demo production flags.

---

## 16. Client handover readiness assessment

| Area | Status |
|---|---|
| Dashboard map / footprints / CRS honesty | **PASS** |
| Client dataset upload + CRS + column UX | **PASS WITH LIMITATIONS** (formats already supported; large-file/path limits as implemented) |
| Validation gate (Ready / warnings / Blocked) | **PASS** |
| Geological / magnetic analysis workflows | **PASS WITH LIMITATIONS** (NOT_VALIDATED) |
| ML 13-channel assess (no TMI injection) | **PASS WITH LIMITATIONS** (research model) |
| Analysis jobs (cancel/retry/heartbeat) | **PASS** (automated tests) |
| Result presentation | **PASS WITH LIMITATIONS** |
| Client-facing app UX | **PASS WITH LIMITATIONS** (headed e2e not re-run) |
| Security / production integrity | **PASS WITH LIMITATIONS** (config discipline required at host time) |
| Documentation (client / admin / deploy) | **PASS** |
| Backend tests (targeted) | **PASS** |
| Frontend tests + build | **PASS** |
| End-to-end browser journey | **NOT TESTED** |

### Overall decision

**READY FOR HOSTING WITH DISCLOSED LIMITATIONS**

Evidence: map/CRS defects fixed and dual-extent verified; upload/validation UX completed; magnetic and auth/job suites green; frontend typecheck/lint/build green; client/admin/deploy guides present; scientific honesty preserved (NOT_VALIDATED, no fabricated risk, no EMAG2 overwrite). Remaining gaps are hosting execution, headed browser rehearsal, and scientific validation — not blocking documentation of a hosting handoff when limitations are disclosed to the client.
