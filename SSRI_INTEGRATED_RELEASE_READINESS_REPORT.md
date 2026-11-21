# SSRI — Integrated Assessment, Ruff & Release Readiness Report

**Review date:** 2026-11-21  
**Mode:** Review only — no stage / commit / push / deploy / reset / rebase / amend / clean  
**HEAD:** `d06878699f398a3b364a3ce48498c9cc0149786d`  
**HEAD subject:** `Harden Supabase assessment authentication and permissions` (Commit C)  
**Verdict:** **NOT RELEASE-READY** — backend Ruff/pytest green locally; frontend `tsc` / production build fail; production assess not verified against a deployed promoted checkpoint.

---

## 1. Exact Git status and diff summary

### HEAD preservation

| Check | Result |
|-------|--------|
| `git rev-parse HEAD` | `d06878699f398a3b364a3ce48498c9cc0149786d` |
| Commit C preserved | **Yes** |
| Auth package diff vs HEAD | **Empty** (`model/src/ssri_model/auth/`, `api/dependencies.py` unchanged) |
| Staging / commit / push / deploy | **Not performed** |

### Working tree (abridged)

**Modified (29 tracked paths):** assessment/visibility + Ruff + unrelated client CSV script.  
**Untracked:** remediation/audit markdown reports; new assess/visibility frontend modules and tests; `model/tests/test_assess_checkpoint_resolution.py`; numerous `poc/_tmp_*` artefacts; Abeokuta / client docs.

**Aggregate tracked diff vs HEAD:** ~355 insertions / ~339 deletions across 29 files (includes large `inspect_client_csv.py` churn).

### Change isolation

#### A. Assessment + geological visibility (proposed commit set)

| Path | Role |
|------|------|
| `model/src/ssri_model/api/routes/assess.py` | `resolve_assessment_checkpoint`, channel guard, clearer errors |
| `model/src/ssri_model/api/routes/training.py` | `checkpoint_available` / `model_id` on active model |
| `model/tests/test_assess_checkpoint_resolution.py` | **New** — 11 regression tests |
| `model/tests/test_demo_mode_assess.py` | Expect updated missing-checkpoint wording |
| `model/tests/test_release_shell_assess.py` | Assert checkpoint language when shell off |
| `frontend/lib/api.ts` | `model_id`, request builder, clearer errors |
| `frontend/lib/assessRequest.ts` | **New** — omit empty checkpoint/model_id |
| `frontend/lib/assessRequest.test.ts` | **New** |
| `frontend/lib/productCapabilities.ts` | **New** — hazard/geo catalogues + merge |
| `frontend/lib/productCapabilities.test.ts` | **New** |
| `frontend/components/product/ProductCapabilities.tsx` | **New** |
| `frontend/app/dashboard/page.tsx` | Promoted-model status, hazards, geo panel |
| `frontend/app/page.tsx` | Landing capabilities section |
| `frontend/app/shell/page.tsx` | Null-safe active path |
| `frontend/app/training/operator/page.tsx` | Null-safe active path |
| `frontend/e2e/dashboard.spec.ts` | Updated missing-checkpoint expectation |

#### B. Ruff-only (proposed separate commit set)

| Path |
|------|
| `model/src/ssri_model/api/app.py` |
| `model/src/ssri_model/attribution/__init__.py` |
| `model/src/ssri_model/dann/train_step.py` |
| `model/src/ssri_model/data/feature_engineering.py` |
| `model/src/ssri_model/evaluation/evaluator.py` |
| `model/src/ssri_model/manual_training/validation.py` |
| `model/src/ssri_model/ml/statistics_loader.py` |
| `model/src/ssri_model/release_shell/evaluate.py` |
| `model/src/ssri_model/release_shell/labels_inventory.py` |
| `model/src/ssri_model/release_shell/routes.py` |
| `model/src/ssri_model/release_shell/validator.py` |
| `model/src/ssri_model/scripts/train_foundation_multitask.py` |
| `model/src/ssri_model/training/checkpoint.py` |
| `model/tests/test_calibration.py` |
| `model/tests/test_csv_import.py` |
| `model/tests/test_hazard_factors_v2.py` |
| `model/tests/test_release_shell_softmax_contract.py` |
| `model/tests/test_upload_row_cap.py` |

Diffstat for this set: **18 files, +15 / −32** (lint-only).

#### C. Unrelated / client-specific (exclude from both commits)

| Path / pattern | Notes |
|----------------|-------|
| `poc/release_shell/scripts/inspect_client_csv.py` | Large client-oriented rewrite; not assess/Ruff |
| `poc/_tmp_*`, `poc/release_shell/configs/` | Temporary probes / leftovers |
| `SSRI_ABEOKUTA_*.md`, `SSRI_CLIENT_*.md`, other audit/release markdown | Documentation leftovers |
| Prior report files (`SSRI_RUFF_*`, `SSRI_LIVE_*`, auth manifests, etc.) | Keep out of product commits unless owner wants them |

---

## 2. Assessment implementation review

### `resolve_assessment_checkpoint()`

**Call site:** sole production caller is `assess_endpoint` in `assess.py` (after auth dependency, before load/inference).

**Resolution order:**

1. Explicit `body.checkpoint` → `source=client_path` (operator override; path-traversal check applied).
2. Explicit `body.model_id` → registry lookup under `TrainingStorage.models_dir`; missing/unavailable/out-of-tree fail closed.
3. Active promoted model → `source=active_registry`; missing file fail closed.
4. Else → `No valid production checkpoint is configured…` (no invented path).

**Ordinary clients:** dashboard omits filesystem paths and prefers server resolution / optional `model_id` of the promoted model.

**13-channel contract:** after load, feature channel count must equal `model_config.in_channels` (default 13). 16-channel stacks against a 13-channel checkpoint return 400. No padding/truncation/zero-fill bridge. Phase 6 live schema-v2 remains BLOCKED by product policy.

**Failure modes covered by tests:** missing active, invalid `model_id`, unavailable active file, invalid client path, 16-vs-13 rejection, successful active resolution without client path.

### Residual assessment risks (not fixed in this review)

1. **Any `RUN_ASSESS` principal may still send `checkpoint`** (advanced path). Traversal is rejected, but a guessed absolute server path is not limited to “operator role only”.
2. **`model_id` can select any registered model**, not only the promoted active one, if the id is known.
3. **`GET /training/models/active` still returns `checkpoint_path`** for operators/tests. Ordinary UI no longer sends it, but the API still exposes the filesystem location to anyone with `READ_STATUS`.

These do **not** bypass authentication: resolution runs only after `require_run_assess_rate_limited`.

---

## 3. Authentication and authorization review

| Control | Status |
|---------|--------|
| Commit C auth code unchanged | **Confirmed** (no working-tree diff under `auth/` / `dependencies.py`) |
| Assess gated by `require_run_assess_rate_limited` | **Confirmed** |
| Rate limiting bucket | Inference limiter still applied for assess |
| `Role.USER` → `RUN_ASSESS` only | **Unchanged** |
| Geological mutations → `require_manage_geological` | **Confirmed** on geological routes |
| Checkpoint resolution bypasses auth? | **No** — dependency runs first |

Ordinary authenticated users can assess; catalogue mutations remain elevated.

---

## 4. Hazard and geological visibility review

| Surface | Finding |
|---------|---------|
| Landing `/` | `ProductCapabilities` lists Subsidence, Landslide, Sinkhole |
| Dashboard hazard chips | All three via `mergeHazardNames`; sinkhole cannot be dropped by truncated registry |
| Layout | Flex-wrap chips + stacked capability columns; sinkhole not truncated by fixed-width list logic |
| Geological conditioning | Separate dashboard panel + capabilities column; labelled “not hazards” |
| Overburden / lineaments | “Offline conditioning supported” / “Available for geological data management” / “Live inference integration pending” |
| Live-score claim | Dashboard states they **do not currently change** live 13-channel scores |

No review evidence of fabricated accuracy percentages or “production-ready” badges for lineaments.

**Frontend type/build blocker:** `productCapabilities.ts` / `.test.ts` fail strict TypeScript (`includes` typing). See §5.

---

## 5. Ruff and integrated test results

### Environment (this review run)

| Item | Value |
|------|-------|
| CWD (backend) | `…/ssri/model` |
| HEAD | `d06878699f398a3b364a3ce48498c9cc0149786d` |
| Working tree | Dirty (assessment + Ruff + unrelated leftovers present) |
| Collection | `842 tests collected` |

### Ruff

```text
Command: poetry run ruff check src tests
Result: All checks passed!
Exit: 0
```

### Backend pytest

```text
Command: poetry run pytest -q --tb=line
Result: 839 passed, 3 skipped in 303.00s
Exit: 0
```

(`839 + 3 skipped = 842` collected.)

### Frontend

| Command | Result |
|---------|--------|
| `npm run typecheck` (`tsc --noEmit`) | **FAIL** (exit 2) — 3 TS2345 errors in `productCapabilities.ts` / `.test.ts` |
| `npm run lint` | **PASS** (exit 0) |
| `npm test` | **42 passed**, 0 failed (exit 0) |
| `npm run build` | **FAIL** (exit 1) — same TypeScript errors during Next typecheck |

TypeScript errors (exact):

- `lib/productCapabilities.test.ts(24,52)` — hazard id passed into geological `includes`
- `lib/productCapabilities.ts(61,27)` and `(61,47)` — `string` vs literal union in `mergeHazardNames`

---

## 6. Explanation of 839 versus 828

| Report / moment | Command | HEAD | Working-tree context | Result |
|-----------------|---------|------|----------------------|--------|
| `SSRI_RUFF_CI_REMEDIATION_REPORT.md` | `poetry run pytest -q --tb=line` | `d068786` | Ruff fixes present; **no** `test_assess_checkpoint_resolution.py` | **828 passed, 3 skipped** |
| Live-assessment remediation + this review | `poetry run pytest -q --tb=line` | `d068786` | Ruff fixes + assess remediation + **new 11 tests** | **839 passed, 3 skipped** |
| This review collect-only | `poetry run pytest --collect-only -q` | `d068786` | Same dirty tree | **842 tests collected** |

**Arithmetic:** `828 + 11 = 839` passed. The 11 new tests are in untracked `model/tests/test_assess_checkpoint_resolution.py`. Skips remain 3 in both eras. **No evidence of flaky hiding or count manipulation**; the delta is the new assessment regression file.

Code was **not** modified during this review to reconcile counts.

---

## 7. Release qualification

| Constraint | Status |
|------------|--------|
| Three hazards available | **Yes** (backend `SUPPORTED_LABELS` + UI) |
| Production inference 13-channel | **Yes** locally (contract + channel mismatch guard) |
| `scientific_validation_status = NOT_VALIDATED` | **Preserved** |
| Phase 6 live schema-v2 | **BLOCKED** |
| Lineament/overburden as live score drivers | **Not claimed**; pending labels present |
| Commit C auth | **Preserved** |
| Production live assess verified on deployed hosts | **Not verified** (no deploy this review) |
| Frontend production build | **Blocked** by TypeScript errors |

**Release qualification: FAIL** until at least:

1. Frontend typecheck/build fixed and re-verified.
2. Owner-approved deploy of API + FE.
3. Production verification against a **real promoted** Stage 2.5 checkpoint (see checklist).

---

## 8. Remaining blockers

1. **Frontend `tsc` / `next build` failure** on `productCapabilities` typing (hard blocker for FE release).
2. **No approved deployment** of assessment resolution + visibility work.
3. **Production must have a promoted registry checkpoint** on the API host; code cannot invent one.
4. **Live AOI acquisition** still depends on deployment flags/credentials when offline `.npy` is not used.
5. **Residual API exposure:** active endpoint still returns `checkpoint_path`; assess still accepts client `checkpoint` / any registered `model_id` for `RUN_ASSESS` principals.
6. **Working tree mixing:** Ruff, assess/visibility, and client leftovers are intertwined — commit only after separation.
7. **CI on `origin/main`** still reflects Commit C until Ruff + assess commits land.

---

## 9. Proposed file lists (for future owner-approved commits)

### Commit proposal 1 — Ruff CI remediation only

Use list **§1.B** (18 files). Exclude auth, assess behavioural changes, and client CSV.

### Commit proposal 2 — Live assessment + visibility

Use list **§1.A** (including untracked new modules/tests). Do **not** include Ruff-only or `poc/` / Abeokuta leftovers.

### Do not include

- `poc/release_shell/scripts/inspect_client_csv.py`
- `poc/_tmp_*`
- Client/Abeokuta markdown unless explicitly requested
- Auth files (already on Commit C)

---

## 10. Production verification checklist

After an **approved** dual deploy (API + frontend):

1. Confirm API build includes assess resolution; FE build passes typecheck.
2. Sign in as ordinary user (`Role.USER` / Supabase session).
3. `GET /api/v1/training/models/active` → `checkpoint_available: true`, `model_id` set, status `NOT_VALIDATED`.
4. `/dashboard`: promoted-model status visible; hazard chips include **subsidence, landslide, sinkhole**; geological panel separate with live-pending wording.
5. Landing `/`: ProductCapabilities shows three hazards + geological intelligence (not a fourth hazard).
6. Run assessment; Network tab: `POST /api/v1/assess` **omits** `checkpoint` for ordinary flow; includes auth header.
7. Response `200` with three hazard profiles; notes include `checkpoint_source=active_registry` or `model_id`.
8. With active model removed: actionable `No valid production checkpoint…` (not silent success).
9. Geological mutation as USER → denied; as elevated principal → allowed.
10. Confirm rate-limit headers/behaviour still apply under burst assess traffic.
11. Confirm no UI copy claims lineaments/overburden drive live scores.

Until steps 1–8 succeed on production hosts, **do not claim the live assessment error is fixed in production**.

---

## Closing

Commit C remains HEAD. Local backend quality gates (Ruff + full pytest) pass on the dirty tree. Assessment resolution and hazard/geological visibility are implemented coherently, with auth preserved. Release is blocked by frontend TypeScript/build failure, undeployed state, and the need for a real promoted production checkpoint plus post-deploy verification.
