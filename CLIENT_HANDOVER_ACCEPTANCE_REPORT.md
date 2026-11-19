# SSRI — Client handover acceptance report

Date: 2026-11-19  
Baseline tip before work: `0f84a9c9e1c7c28477c60fe07fba6c265885a5e6` (`main` = `origin/main`)  
Implementation branch: `feature/client-handover-acceptance`  
Deployment: **none** (explicitly out of scope)

Audits: [coordinate lifecycle](6df30a22-2c3a-4c4e-94f3-6d9d0113a614), [CSV train path](05ad6632-5da0-4790-b048-6ca08e3a0ace)

---

## Coordinate accuracy — **PASS WITH WARNINGS**

### Verdict

Frontend-selected WGS84 coordinates are the coordinates validated and echoed by the assessment API. Live acquisition grids are derived from the same point via a ±0.01° bbox → computed UTM. Offline `.npy` assess uses the point for region gating / provenance and does not re-sample the tensor from the click.

### Evidence

| Check | Result |
|-------|--------|
| Lifecycle trace (map → assess → grid) | Documented in `docs/CLIENT_HANDOVER_ACCEPTANCE.md` |
| Deterministic grid mapping tests | `tests/test_location_provenance.py` (centre/W/E/N/S, invalid, SF≠32631) |
| Assess echo of submitted lat/lon + pixel | `tests/test_assess_location_provenance.py` + live `POST :8010/api/v1/assess` |
| Live call example | lat=6.5244, lon=3.3792 → provenance `EPSG:32631`, pixel row=37 col=37, bbox `(3.3692,6.5144,3.3892,6.5344)` |
| Frontend unit coord tests | 20/20 pass (`lib/coordinates.test.ts`, report tests) |

### Key files

- `frontend/app/dashboard/page.tsx` — MapLibre click → `{latitude,longitude}`
- `frontend/lib/coordinates.ts` — parse/format/coverage
- `model/src/ssri_model/api/routes/assess.py` — request validation + provenance
- `model/src/ssri_model/api/location_provenance.py` — WGS84 → UTM cell
- `model/src/ssri_model/data/feature_engineering.py` — `build_grid_spec_from_aoi`

### Warnings / remaining limits

1. Live raster sampling still needs `SSRI_LIVE_ACQUISITION_ENABLED` + DEM/GEE/geophysics; local proof used offline features + geometric grid provenance.
2. Point AOI is a ±0.01° window, not a single-cell click sample.
3. Dashboard requires auth in this environment; Playwright Chromium install was required for browser e2e (unit + API proof completed; browser e2e re-run after install).
4. Demo mode remains non-geospatial for scores.

---

## Client-owned training and inference — **PASS WITH WARNINGS**

### CSV contract

- **Trainable:** all 13 Stage 2.5 channels + labels + declared CRS (`manual_training/csv_import.py`).
- **Feature-only** (e.g. `X,Y,Z`): `FEATURE_LAYER_ONLY` — **labels never invented**.
- Manifest stamps `channel_schema_version=v1` + `channel_names`.

### Evidence

| Step | Result |
|------|--------|
| Labelled CSV validate | pass (`test_csv_import`, handover e2e) |
| Feature-only refuse | pass |
| Train → registry checkpoint | pass (`test_platform_v4`, `test_client_handover_e2e`) |
| Promote for assess | `POST /api/v1/platform/models/{id}/promote` → active registry path |
| Assess with promoted ckpt | genuine hazard profiles returned |
| Epochs honored | payload default 5 (no longer hardcoded 1) |
| Ownership | other user 404 on promote |
| Shell label join | `POST .../datasets/{id}/labels/apply` + UI button |

### Warnings / remaining limits

1. Interactive column-mapping UI still alias/exact-name based (no free-form picker).
2. Account train path is the CSV product path; release-shell train still expects Stage 2.5 ZIP (labels apply is additive).
3. Synthetic fixtures prove pipeline, not scientific skill.
4. Abeokuta CRS/units still client-owned unknowns.
5. Platform eval metrics are trainer validation metrics (shell has richer held-out suite).

---

## Test summary

| Suite | Result |
|-------|--------|
| Backend pytest | **772 passed** (+ new handover tests beyond that tip; re-run includes new files) |
| Infra integration (`SSRI_INTEGRATION_TESTS=1` + Postgres/Redis) | **2 passed** |
| Frontend typecheck | pass |
| Frontend lint | pass |
| Frontend unit tests | **20 passed** |
| Frontend production build | pass |
| Client handover e2e (CSV→train→promote→assess) | **2 passed** |
| Playwright dashboard coord e2e | Chromium installed; **4 tests skipped** (dashboard requires signed-in session; no client credentials in this run). Map click→6dp covered by existing unit tests + API provenance |

### Skipped

- Integration tests without `SSRI_INTEGRATION_TESTS=1` / DB URLs (by design).
- `-m integration` selects none (infra tests use `skipif`, not the mark alone).

---

## Deployment readiness

Checklist prepared: `docs/DEPLOYMENT_HANDOVER_CHECKLIST.md`.  
**Hosted functionality is not verified.** No Render/Vercel/Cloudflare/DNS/production migration work was done.

---

## Remaining handover blockers

1. Confirm Abeokuta CRS/units with the client before treating that CSV as science input.
2. Install Playwright browsers in CI/agent images if browser e2e is required in automation.
3. Decide whether live AOI will be enabled in the client environment (credentials + geophysics).
4. Scientific validation remains `NOT_VALIDATED`.

---

## Changes delivered in this acceptance pass

- Assess `location_provenance` (submitted CRS, transformed XY, pixel index)
- Platform promote endpoint + models UI promote control
- Platform training epochs from job payload; schema metadata on CSV/models
- Shell labels apply route + UI
- Acceptance docs + deterministic/e2e tests
