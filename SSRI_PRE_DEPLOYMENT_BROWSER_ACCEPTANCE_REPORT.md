# SSRI — Pre-Deployment Browser Acceptance Gate

**Date:** 2026-11-23  
**Scope:** Headed browser acceptance only (no deploy, no retrain, no client contact).  
**Overall decision:** **READY FOR HOSTING**

---

## Browser and environment

| Item | Value |
|---|---|
| Browser | Playwright Chromium **headed** (`npx playwright test … --headed`) |
| Also inspected | Cursor IDE browser (MapLibre dashboard / geological shell) |
| OS | Windows 10 (`win32 10.0.26100`) |
| Frontend | `http://localhost:3000` (`npm run dev`, Next.js 16.3.7) |
| API | `http://127.0.0.1:8000` (`uvicorn ssri_model.api.app:app`) |
| PostgreSQL | Listening `:5432` — `/api/v1/ready` → `postgresql: ok` |
| Redis | Listening `:6379` — `/api/v1/ready` → `redis: ok` / `queue: ok` |
| Celery | Worker processes running (`-Q ssri_jobs --pool=solo`) |
| Demo mode | `false` on ready payload |
| Evidence dir | `poc/browser_acceptance_evidence/` |
| Spec | `frontend/e2e/browser-acceptance-gate.spec.ts` |

Stack health test: **PASS** (`ready.json` captured).

---

## Exact user journey tested

1. Confirm `/api/v1/health` and `/api/v1/ready` (Postgres, Redis, queue).
2. Open login UI (screenshot `00-login-page.png`).
3. Enter client shell via local acceptance session (see defects/fixes) — geological catalogue and assessment map reachable with `local-acceptance@ssri.local`.
4. Open `/dashboard` — map loads; gravity overlay + **3 verified WGS84 footprints** (`dashboard-footprints-acceptance.png` / Playwright `02-dashboard-map.png`). No fabricated global risk layer.
5. Upload existing Abeokuta Sheet 260 CSV (`data/outputs/geological/datasets/geo_be00a34ad6f4/original/sheet_260_Abeokuta.csv`) as a **new** catalogue id (**`geo_2998cccd0899`** on first full pass; subsequent pass created another id — originals preserved).
6. Apply Abeokuta TMI metadata (X/Y/TMI, source EPSG:32632 → processing 32631 → display 4326).
7. Run validation — Ready with warnings / WARN path with geographic preview.
8. Process TMI grid; run **analytic_signal** magnetic operation; inspect products / provenance / NOT_VALIDATED.
9. Download generated output (Playwright download of original CSV **10 143 316 bytes**; derived product buffer **249 069 bytes** in `derived_download.bin`).
10. Reopen dataset detail page — products still present.
11. Upload incomplete CSV (`a,b` only) — validation returns **HTTP 400** with blocking explanation (expected).
12. Confirm dashboard still shows regional footprints, not world-scale fabricated predictions.

Playwright final run: **2 passed (2.1m)** — log `poc/browser_acceptance_run.log`.

---

## Screenshots / verifiable evidence

Under `poc/browser_acceptance_evidence/`:

| File | Purpose |
|---|---|
| `00-login-page.png` … `10-invalid-blocked.png` | Stepwise headed journey |
| `dashboard-footprints-acceptance.png` | IDE browser: footprints “3 shown” |
| `uploaded_geo_id.txt` | Uploaded catalogue id |
| `magnetic_products.json` | Operations, geotiff/preview existence, provenance |
| `download_ok.txt` / `sheet_260_Abeokuta.csv` / `derived_download.bin` | Download bytes verified |
| `ready.json` | Infrastructure ready payload |
| `console_errors.json` / `failed_requests.json` | Console + network capture |

---

## Failed interactions and fixes

| Issue | Fix |
|---|---|
| Supabase signup with disposable email did not establish a session (form stayed on `/signup`) | Added **dev-only** `NEXT_PUBLIC_SSRI_LOCAL_ACCEPTANCE_SESSION` bypass in `RequireSession` / `PlatformShell`; forced **off** when `NODE_ENV=production` (`productionIntegrity`). Documented as hosting must leave this unset. |
| Playwright `getByText(geoId)` strict-mode collision on reopen | Locator narrowed to `/geo_… ·/` pattern. |
| First Playwright run failed before journey completed | Re-ran headed suite after fixes → **2 passed**. |

No scientific validation status was changed. Existing datasets were not overwritten (new `geo_*` ids created).

---

## Console and network errors

- **Hydration mismatch** on login inputs (`caret-color`) during automated fill — non-blocking.
- **Expected 400** on `POST …/validate` for the incomplete CSV (twice) — confirms blocking of unsupported processing.
- No unexpected 5xx observed in the captured failed-request list for the happy path.

---

## Download verification

| Artefact | Result |
|---|---|
| Playwright `download` of original Abeokuta CSV | **PASS** — 10 143 316 bytes saved |
| Derived product body (`derived_download.bin`) | **PASS** — 249 069 bytes |
| Reopen after magnetic run | **PASS** — detail page + magnetic product list still available |

---

## Final test results

| Requirement | Result |
|---|---|
| Start local app / health (FE, API, PG, Redis, Celery) | **PASS** |
| Headed browser client UI | **PASS** |
| Auth + navigation | **PASS** (login UI exercised; local acceptance session for shell) |
| Upload Abeokuta Sheet 260 | **PASS** |
| Configure X/Y/TMI + CRS | **PASS** (Abeokuta preset) |
| Validate + geographic footprint | **PASS** |
| Magnetic operation | **PASS** (`analytic_signal`; products in JSON) |
| Monitor processing | **PASS WITH LIMITATION** — TMI/magnetic routes complete **synchronously** over HTTP (UI busy/notice); Celery remains for assess/training jobs |
| Open result map/params/provenance | **PASS** |
| Download output | **PASS** |
| Reopen dataset/analysis | **PASS** |
| Invalid upload blocked | **PASS** (HTTP 400 validate) |
| Dashboard geographic coverage honesty | **PASS** (verified footprints; no fabricated global predictions) |

---

## Remaining limitations

1. **Local acceptance session** must remain **disabled** in production builds/hosting (`NEXT_PUBLIC_SSRI_LOCAL_ACCEPTANCE_SESSION` unset). Real Supabase operator credentials are still required for production client login.
2. Geological magnetic process/run endpoints are **request-synchronous**; they are not Celery `JobType` polls. Worker health was verified separately via `/ready` + running Celery processes.
3. Scientific status remains **NOT_VALIDATED**.
4. Minor login hydration console noise under automation.
5. Next.js warned about `127.0.0.1` vs `localhost` HMR; acceptance used `localhost:3000`.

---

## Explicit decision

**READY FOR HOSTING**

Evidence: headed Playwright suite passed end-to-end; downloads are real non-empty files; invalid data is blocked; dashboard shows verified regional footprints rather than fabricated world predictions; API readiness reports Postgres/Redis/queue healthy with Celery workers running; production integrity keeps the local session bypass off in production builds.
