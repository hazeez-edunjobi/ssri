# SSRI — Geological Phases 2–6 Acceptance Report

**Date:** 2026-11-20  
**Branch:** `main`  
**Mode:** Implementation + readiness assessment (no deploy, no push)  

---

## A. Phase status

| Phase | Status | Notes |
|-------|--------|--------|
| **Phase 1 (prerequisite)** | **COMPLETE** | Was **missing** from the tree at audit time; implemented as required prerequisite before Phases 2–5 (same catalogue — not a second system). |
| **Phase 2** | **COMPLETE** | Geological management UI at `/geological` + `/geological/[id]`; central `geologicalApi.ts`. |
| **Phase 3** | **COMPLETE** | `POST /api/v1/geological/coverage` + UI coverage probe; intersection/conflict policy documented in code. |
| **Phase 4** | **COMPLETE** | `asset_kind=vector_lineament`; GeoJSON (+ Shapefile zip / GPKG when fiona present); separate from XYZ. |
| **Phase 5** | **COMPLETE** | `POST /api/v1/geological/apply/offline` reuses `feature_apply`; depth≠thickness; report on disk. |
| **Phase 6** | **BLOCKED** | v2 readiness gate **failed** (see §F). No production inference changes. |

---

## B. Architecture

### Reuse map (audit)

| Need | Existing component reused |
|------|---------------------------|
| CSV parse / CRS / grid | `release_shell/point_grid_csv.py` |
| Validate contracts | `validate_point_grid_layer` |
| Overburden / lineament apply | `feature_apply.py`, `lineaments.py` |
| Upload limits / errors | `manual_training/upload_limits`, `ManualTrainingError` |
| Storage pattern | Mirrored from `TrainingStorage` → `{output_root}/geological/` |
| Auth deps | `require_run_inference` / `require_read_status` |
| Frontend auth + shell | `PlatformShell`, Supabase session headers |
| Schema v2 names | `channel_schema.CHANNEL_NAMES_V2` |

### Files created

- `model/src/ssri_model/geological/` — `models.py`, `storage.py`, `inspect.py`, `validate.py`, `coverage.py`, `lineament_ingest.py`, `apply.py`, `service.py`, `__init__.py`
- `model/src/ssri_model/api/routes/geological.py`
- `model/tests/test_geological_ingest.py`
- `model/tests/fixtures/geological/*.csv`, `lineaments.geojson`
- `frontend/lib/geologicalApi.ts`
- `frontend/app/geological/page.tsx`
- `frontend/app/geological/[id]/page.tsx`
- `SSRI_GEOLOGICAL_PHASES_2_6_ACCEPTANCE_REPORT.md` (this file)

### Files modified

- `model/src/ssri_model/api/app.py` — mount geological router
- `frontend/components/platform/PlatformShell.tsx` — nav + banner
- `poc/release_shell/scripts/inspect_client_csv.py` — delegates to `geological.inspect`

### API contracts (`/api/v1/geological`)

| Method | Path | Role |
|--------|------|------|
| POST | `/datasets` | Create catalogue entry (`point_grid_csv` \| `vector_lineament`) |
| GET | `/datasets` | List + filters + pagination |
| GET | `/datasets/{geo_id}` | Metadata + inspect + validation |
| POST | `/datasets/{geo_id}/upload` | Preserve original; inspect |
| POST | `/datasets/{geo_id}/declare` | CRS / measurement / units / columns |
| POST | `/datasets/{geo_id}/validate` | Fail-closed without CRS/measurement |
| POST | `/datasets/{geo_id}/activation` | `inactive` \| `reporting_only` \| `approved` (not live inference) |
| GET | `/datasets/{geo_id}/original` | Authz download of immutable original |
| POST | `/coverage` | AOI bbox matching (reporting only) |
| POST | `/apply/offline` | Schema-v2 offline apply via existing helpers |

### Storage

`{output_root}/geological/datasets/{geo_id}/original|working` + `dataset.json` + append-only `index.jsonl`.

---

## C. Data integrity

Evidence from `tests/test_geological_ingest.py` (executed; see §D):

- Two uploads → distinct `geo_id`; second upload to same id → `ORIGINAL_IMMUTABLE`
- Original bytes SHA256 preserved
- Validate without CRS → `CRS_REQUIRED`; without measurement → `MEASUREMENT_REQUIRED`
- `depth_to_bedrock` stored/reported as depth — not thickness; offline apply of depth → `APPLY_MEASUREMENT`
- Gaps/negatives reported at inspect; thickness negatives → `unit_sanity` WARN; no zero-fill in apply path (existing `FEATURE_NODATA` helpers)
- Lineament `asset_kind` separate; empty segments WARN, not “absence of lineaments”
- Coverage vs apply: coverage sets `used_in_inference: false`; apply report same; overlapping same measurement → conflict, no auto-merge
- API `to_dict()` hides filesystem relpaths from ordinary clients

---

## D. Testing

### Backend

| Command | Result |
|---------|--------|
| `cd model; poetry run pytest tests/test_geological_ingest.py -q --tb=line` | **15 passed** (initial + re-verify) |
| `poetry run pytest tests/test_feature_apply_and_upload_unlimited.py tests/test_hazard_factors_v2.py tests/test_manual_training.py tests/test_assess_conditioning.py -q --tb=line` | **30 passed** (initial) |
| `poetry run pytest tests/test_geological_ingest.py tests/test_feature_apply_and_upload_unlimited.py tests/test_assess_conditioning.py -q --tb=line` | **24 passed** (re-verify after this prompt) |

Warnings: none material in the captured summaries.

Not run: full `poetry run pytest` suite (scope/time); focused regression covers geological catalogue, feature apply, assess conditioning.

### Frontend

| Command | Result |
|---------|--------|
| `npm run typecheck` | **PASS** (re-verified) |
| `npm run lint` | **PASS** (re-verified) |
| `npm test` | **31 passed**, 0 failed (re-verified) |
| `npm run build` | **PASS** — includes `/geological` and `/geological/[id]` (prior run) |

---

## E. Production safety

| Check | Evidence |
|-------|----------|
| Three hazards unchanged | No edits to hazard heads / assess hazard contract in this work |
| 13-channel architecture default | `architecture/config.py` `in_channels=CHANNEL_COUNT` (13) untouched |
| Inference safety still 13 | `inference/safety.py` still requires `CHANNEL_COUNT` |
| Live assess routes untouched | No modifications to `api/routes/assess.py` |
| Geological not in live inference | Apply/coverage explicitly `used_in_inference: false`; activation copy states offline/reporting only |
| No deploy / credential / env change | None performed |
| No Git push | Confirmed |

---

## F. Phase 6 decision — **BLOCKED**

Readiness gate results:

| # | Requirement | Evidence | Pass? |
|---|-------------|----------|-------|
| 1 | Schema-v2 contract exists | `CHANNEL_NAMES_V2` (16 names) | Yes |
| 2 | Channel ordering documented | `FEATURE_SCHEMA_V2.md` / `channel_schema.py` | Yes |
| 3 | Offline apply produces 16-ch stacks | Phase 5 + existing `feature_apply` tests | Yes (offline only) |
| 4 | Defensible sources for all 3 conditioning channels | Client CRS/Z still unconfirmed; lineaments optional | **No** (catalogue ready; science undeclared) |
| 5 | NoData/missing tested | Existing + new geological tests | Partial/Yes offline |
| 6 | Architecture accepts exactly 16-ch | Default `in_channels=13`; safety hard-requires 13 | **No** for production path |
| 7 | Compatible checkpoint trained | No `*v2*best*.pt` / evaluated 16-ch checkpoint in repo | **No** |
| 8 | Checkpoint tied to schema version | N/A without checkpoint | **No** |
| 9 | Evaluation vs baselines/held-out | Not present for v2 | **No** |
| 10 | Metrics/limitations/`NOT_VALIDATED` docs | Remains research / NOT_VALIDATED | **No** (gate not met) |
| 11 | Inference/regression for v1/v2 isolation | Live path still v1-only by design | **No** for v2 live |

**Missing prerequisites for unblocking Phase 6**

1. Train `SSRIModel` with `in_channels=16` on schema-v2 stacks with documented provenance.  
2. Persist `channel_schema_version=v2` + channel names on the checkpoint.  
3. Run evaluation; document metrics and limitations; keep `scientific_validation_status` honest.  
4. Generalize inference safety to accept checkpoint-declared 13 **or** 16 without silent pad/trim.  
5. Separate versioned assess path; never silently replace v1.  
6. Confirmed client CRS/units/measurement for any thickness channel used in training.

**No fabricated checkpoint. Production v1 inference unchanged.**

---

## G. Git state

| Item | Value |
|------|-------|
| Branch | `main` (tracking `origin/main`) |
| Initial | Untracked planning docs / poc temps only; **no** `geological/` package |
| Final | Modified: `app.py`, `PlatformShell.tsx`, `inspect_client_csv.py`; untracked geological package, routes, tests, fixtures, FE pages, API client, this report |
| Preserved user work | Prior untracked planning docs and `poc/_tmp_*` left in place |
| Destructive ops | **None** (no reset/rebase/squash/amend/push/deploy) |

---

## Implementation note

Phase 1 was specified as already establishing the catalogue, but the repository contained only the architecture document. Phases 2–5 cannot function without that catalogue, so Phase 1 was implemented **once** as the single system described in `SSRI_GEOLOGICAL_CSV_INGESTION_ARCHITECTURE.md`, then extended — not duplicated.

Awaiting approval before any commit, push, deploy, model switch, or Phase 6 implementation.
