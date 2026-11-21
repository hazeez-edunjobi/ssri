# SSRI — Final Project Closure & Production Release Qualification

**Date:** 2026-11-21  
**Mode:** Inspect, implement hardening, verify, document — **no commit / push / deploy**  
**Approved HEAD:** `d06878699f398a3b364a3ce48498c9cc0149786d` (Commit C)

---

## 1. Executive release verdict

| Gate | Result |
|------|--------|
| Engineering readiness (local dirty tree) | **CONDITIONAL PASS** after checkpoint authorization hardening + prior assess/Ruff/TS work |
| Security residual issues A/B/C | **Addressed in working tree** (not yet committed/deployed) |
| Scientific integrity constraints | **Preserved** |
| Production live assess verified | **NOT VERIFIED** — no deploy; production checkpoint presence unconfirmed |
| **Overall production release** | **NOT RELEASED / NOT QUALIFIED FOR GO-LIVE** until owner-approved commits, deploy, and authenticated production smoke succeed |

**Honest completion estimate:** ~**78%** toward a verified production release (engineering + local gates largely closed; production checkpoint, deploy evidence, and post-deploy smoke still open).

---

## 2. Verified Git baseline

| Item | Evidence |
|------|----------|
| Branch | `main` tracking `origin/main` |
| HEAD | `d06878699f398a3b364a3ce48498c9cc0149786d` |
| Subject | Harden Supabase assessment authentication and permissions |
| Working tree | Dirty — assess/visibility + Ruff + TS fix + checkpoint auth hardening + client leftovers |
| Stage / commit / push / deploy | **Not performed** |

Unrelated leftovers preserved (not cleaned): `poc/_tmp_*`, Abeokuta/client markdown, `inspect_client_csv.py` churn.

---

## 3. Exact implementation changes (this closure pass)

### Checkpoint authorization hardening (new)

| File | Change |
|------|--------|
| `model/src/ssri_model/api/routes/assess.py` | `can_override_assessment_checkpoint`; principal-aware `resolve_assessment_checkpoint`; ordinary users limited to active registry; operator path jail under `output_root`; non-active `model_id` requires `RUN_INFERENCE` |
| `model/src/ssri_model/api/routes/training.py` | Active-model endpoint redacts `checkpoint_path` / filesystem fields for non-operators |
| `model/tests/test_assess_checkpoint_authorization.py` | **New** RBAC matrix tests |
| `model/tests/auth_helpers.py` | Provision `Role.USER` API key |
| Assess fixture tests | Checkpoints placed under `service-outputs/` to match operator path jail |

### Already in working tree (prior tasks, still uncommitted)

- Live assessment active-registry resolution + 13-vs-16 channel guard  
- Hazard / geological visibility + ProductCapabilities  
- ProductCapabilities TypeScript fix  
- Repository-wide Ruff remediation  

**Auth package (`auth/`, `dependencies.py` RBAC maps):** unchanged from Commit C.

---

## 4. Checkpoint authorization and security findings

### A. Explicit checkpoint paths — **hardened**

- Ordinary `RUN_ASSESS` → `403 INSUFFICIENT_PERMISSIONS` if `checkpoint` is supplied.  
- Operators/admins (`RUN_INFERENCE`) may override; path must resolve **under `output_root`** (blocks `..`, absolute escape outside the jail, symlink escape out of root).  
- Error messages for denials do **not** echo filesystem paths.

### B. Model ID selection — **hardened**

- Naming the **active** `model_id` is allowed for ordinary users (equivalent to active resolution).  
- Selecting a **non-active** registered model requires `RUN_INFERENCE`.  
- Missing/unavailable registry files fail closed without inventing models.

### C. Active-model endpoint — **hardened**

- Ordinary `READ_STATUS`: `model_id`, `checkpoint_available`, scientific status, public metadata — **`checkpoint_path: null`**, no `experiment_dir`.  
- Operators/admins: full path retained for lab workflows.

### Residual note

`GET /training/models` list may still include paths in model dicts for callers with `READ_STATUS`. Only the **active** endpoint was required for this closure; further list redaction can be a follow-up.

Authentication and assess **rate limiting** remain on `require_run_assess_rate_limited`.

---

## 5. Backend and frontend test results

### Backend

| Command | CWD | Result |
|---------|-----|--------|
| `poetry run ruff check src tests` | `model/` | **All checks passed** (`RUFF_EXIT=0`) |
| Focused auth+resolution | `model/` | **27 passed** |
| Focused assess fixtures + auth after path-jail fixture fixes | `model/` | **46 passed** |
| `poetry run pytest -q --tb=line` | `model/` | **855 passed, 3 skipped** in 303.26s (`PYTEST_EXIT=0`) |

Collection arithmetic: prior 839 passed + new authorization tests (~16) ≈ 855 after fixture updates; skips remain 3.

### Frontend (verified this session / prior TS fix)

| Command | Result |
|---------|--------|
| `npm run typecheck` | **PASS** (`TSC_EXIT=0`) |
| `npm run lint` | **PASS** (`LINT_EXIT=0`) |
| `npm test` | **46 passed** (`TEST_EXIT=0`) |
| `npm run build` | **PASS** (`BUILD_EXIT=0`) |

---

## 6. Production infrastructure readiness

| Component | Evidence | Status |
|-----------|----------|--------|
| Frontend host | Documented `https://ssri-gamma.vercel.app` | Known |
| API host | Documented `https://ssri-api.onrender.com` | Reachable for some routes |
| Worker | `infra/WORKER_PRODUCTION_DEPLOY.md` — separate Render Background Worker | Config documented; **not verified live** |
| Postgres / Redis TLS / Celery | Env names in `infra/render-worker.env.example`, compose | **Not live-probed with credentials** |
| Supabase auth | Commit C on HEAD | Code present; prod behaviour depends on deploy |
| CORS | Historical docs require Vercel origin | Assume configured; not re-audited live |
| Persistent checkpoint storage | `SSRI_API_OUTPUT_ROOT=/data/outputs` | **Critical unknown** whether volume holds a promoted model |

### Live probe (this review, no secrets)

| Endpoint | Result |
|----------|--------|
| `GET …/api/v1/health` | **Timeout** |
| `GET …/api/v1/ready` | **Timeout** |
| `GET …/api/v1/training/models/active` | **401 Unauthorized** (API process answering auth gate) |

**Conclusion:** Cannot confirm a promoted Stage 2.5 checkpoint on production without authenticated operator access. Treat **missing/unverified production checkpoint** as a **deployment blocker**.

---

## 7. Actual promoted checkpoint verification

| Check | Local dirty tree | Production |
|-------|------------------|------------|
| Registry resolution code | Implemented + tested | **Not deployed** |
| Promoted file available to API | N/A locally | **Unknown / unverified** |
| 13-channel contract | Guard + Stage 2.5 loader | Must re-verify after deploy |
| Invented checkpoint | **Not done** | **Must not invent** |

---

## 8. Three-hazard and geological capability verification

| Requirement | Status |
|-------------|--------|
| Subsidence / Landslide / Sinkhole visible | Landing `ProductCapabilities` + dashboard chips + mergeHazardNames |
| Geological conditioning separate | Dashboard panel + capabilities column |
| Live-inference-pending labels | Preserved |
| No claim that lineaments/overburden drive live scores | Present in dashboard copy |
| Responsive layout | Flex-wrap / stacked sections; sinkhole not dropped by merge |

---

## 9. Scientific validation limitations

- `scientific_validation_status = NOT_VALIDATED` preserved.  
- Production live inference remains **13-channel Stage 2.5**.  
- Phase 6 schema-v2 live inference remains **BLOCKED**.  
- No invented accuracy metrics or geological measurements.  
- Demo mode remains server-side only when enabled.

---

## 10. Remaining blockers

1. **Owner-approved commits** (three separate manifests below) not yet staged.  
2. **Owner-approved deploy** of API + FE (+ worker if required).  
3. **Production promoted Stage 2.5 checkpoint** must exist on persistent storage and be active — **unverified**.  
4. Authenticated production smoke (assess + three hazards + geo separation + auth negatives) **not run**.  
5. Health/ready timeouts on public probe — investigate ops health independently of assess.  
6. Optional follow-up: redact paths on `GET /training/models` list for ordinary users.

---

## 11. Proposed separate commit manifests (do not stage until approved)

### Commit 1 — Ruff CI remediation

```
model/src/ssri_model/api/app.py
model/src/ssri_model/attribution/__init__.py
model/src/ssri_model/dann/train_step.py
model/src/ssri_model/data/feature_engineering.py
model/src/ssri_model/evaluation/evaluator.py
model/src/ssri_model/manual_training/validation.py
model/src/ssri_model/ml/statistics_loader.py
model/src/ssri_model/release_shell/evaluate.py
model/src/ssri_model/release_shell/labels_inventory.py
model/src/ssri_model/release_shell/routes.py
model/src/ssri_model/release_shell/validator.py
model/src/ssri_model/scripts/train_foundation_multitask.py
model/src/ssri_model/training/checkpoint.py
model/tests/test_calibration.py
model/tests/test_csv_import.py
model/tests/test_hazard_factors_v2.py
model/tests/test_release_shell_softmax_contract.py
model/tests/test_upload_row_cap.py
```

### Commit 2 — Assessment + product capability release

```
model/src/ssri_model/api/routes/assess.py          # resolution + channel guard (pre-hardening core)
model/src/ssri_model/api/routes/training.py        # checkpoint_available/model_id fields (pre-hardening)
model/tests/test_assess_checkpoint_resolution.py
model/tests/test_demo_mode_assess.py               # wording / fixture path under output_root
model/tests/test_release_shell_assess.py
frontend/lib/api.ts
frontend/lib/assessRequest.ts
frontend/lib/assessRequest.test.ts
frontend/lib/productCapabilities.ts
frontend/lib/productCapabilities.test.ts
frontend/components/product/ProductCapabilities.tsx
frontend/app/dashboard/page.tsx
frontend/app/page.tsx
frontend/app/shell/page.tsx
frontend/app/training/operator/page.tsx
frontend/e2e/dashboard.spec.ts
```

> Note: `assess.py` / `training.py` currently also contain Commit-3 hardening. Prefer committing **3 before or together with 2** as a single “assessment release” if splitting the same file is undesirable; otherwise cherry-pick/split carefully.

### Commit 3 — Checkpoint authorization hardening

```
model/src/ssri_model/api/routes/assess.py          # principal-aware resolution + path jail
model/src/ssri_model/api/routes/training.py        # active endpoint redaction
model/tests/test_assess_checkpoint_authorization.py
model/tests/auth_helpers.py                        # USER API key
model/tests/test_api_assess_audit.py               # fixtures under service-outputs
model/tests/test_assess_geotiff_and_conditioning.py
model/tests/test_assess_location_provenance.py
model/tests/test_release_shell_assess_route.py
model/tests/test_assess_checkpoint_resolution.py   # principal arg + dual-model model_id case
```

### Exclude from all commits

- `poc/_tmp_*`, `poc/release_shell/scripts/inspect_client_csv.py`  
- Abeokuta / client audit markdown unless requested  
- `.env`, secrets, raw client datasets  
- Auth files already on Commit C  

---

## 12. Deployment evidence

**None.** Deployment explicitly deferred pending owner approval. No provider deploy IDs or new SHAs recorded.

Post-approval checklist (unchanged from integrated report §10): dual deploy → authenticated ordinary-user assess → active model → three hazards → geo separate → USER denied path/model override → geological mutate denied → ready/Postgres/Redis/worker.

---

## 13. Final project completion percentage

| Area | Approx. |
|------|---------|
| Platform software (assess/train/auth UI) | 90% |
| Checkpoint resolution + auth hardening (local) | 95% |
| Hazard/geological visibility | 95% |
| Local quality gates (Ruff/FE build) | 95% |
| Scientific validation | **0% validated** (correctly NOT_VALIDATED) |
| Phase 6 live v2 | **BLOCKED** |
| Production checkpoint + deploy smoke | **~20%** (hosts known; content unverified) |
| **Weighted overall** | **~78%** |

---

## 14. Outstanding work for genuine 100%

1. Owner approve and land Commits 1–3 (or equivalent ordered set).  
2. Confirm / place a real promoted Stage 2.5 **13-channel** checkpoint on production persistent storage.  
3. Deploy API + frontend (+ worker if async required) to the approved SHAs.  
4. Complete authenticated production smoke (§12).  
5. Separate scientific programme to move beyond `NOT_VALIDATED` (out of scope for engineering GO).  
6. Unblock Phase 6 only after compatible model + evaluation (not now).

---

## Closing

SSRI’s engineering path for authenticated 13-channel assessment with visible hazards, honest geological conditioning, Ruff-clean backend, and hardened checkpoint authorization is implemented in the working tree atop Commit C. **It is not a completed production release** until commits, deployment, and a verified promoted production checkpoint pass the smoke checklist without inventing models or overstating science.
