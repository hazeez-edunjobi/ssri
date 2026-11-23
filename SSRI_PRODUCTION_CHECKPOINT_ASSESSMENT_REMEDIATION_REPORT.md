# SSRI — Production Model Checkpoint, Assessment API & Hazard Presentation Remediation

**Date:** 2026-11-21  
**Baseline tag:** `ssri-completed` (`427f578`)  
**Local HEAD inspected:** `d4a4a12` (`ssri-completed-3-gd4a4a12`)  
**Git:** no commit / push / deploy performed  

---

## 1. Original root cause of the missing checkpoint

**Root cause:** there is **no promoted (active) Stage 2.5 checkpoint** in the training registry that production assess can resolve.

The assess path does **not** require clients to send a filesystem `checkpoint`. Ordinary requests omit it; the server calls `resolve_assessment_checkpoint()` which:

1. Optionally accepts an **operator** path (`RUN_INFERENCE`)  
2. Else optional `model_id`  
3. Else reads `{SSRI_API_OUTPUT_ROOT}/training/models/active.json`  
4. Fail-closed → `INVALID_REQUEST` with *“No valid production checkpoint is configured…”*

### About `INVALID_REQUEST: Assessment requires 'checkpoint'`

That exact string is **not present** in current `model/` or `frontend/` source. Production OpenAPI (`https://ssri-api.onrender.com/openapi.json`) lists `checkpoint` as an **optional** property (not in `required`).  

The historical message appears only in older docs/staging notes. Current client-facing failure for a missing promote is the **“No valid production checkpoint…”** message (or **401** when auth is required and no credentials are supplied).

---

## 2. Registry inspection results

### Production (`https://ssri-api.onrender.com`)

| Probe | Result |
|-------|--------|
| `GET /api/v1/health` | **200** ok |
| `GET /api/v1/ready` | **200** distributed; postgres/redis/queue ok; **no** prior `model_registry` field on deployed tip |
| `GET /api/v1/training/models/active` | **401** (auth required; contents not observable without credentials) |
| `POST /api/v1/assess` (no auth) | **401** |
| OpenAPI `AssessRequestBody.checkpoint` | **Optional** |

**Not verified on production disk:** `registry.json` / `active.json` contents, persistent volume state, or any promoted `best.pt`.

### Local workspace

| Location | Finding |
|----------|---------|
| Default service output registry under `outputs/service` | No usable `active.json` observed for the local demo API root |
| `model/outputs/rehearsal_300k_shell/.../training/models/` | `registry.json` with 3 models; **`active.json` absent** |
| Registered models (rehearsal) | `ssri-model-{9889974a4f,153f09d946,ab012b30ed}` — **`in_channels=13`**, `model_state_dict` present, dataset **`SYNTHETIC-300k`** |
| `model/_handover_tmp/best.pt` | Stage 2.5 format, **`in_channels=13`**, dataset **`handover`**, ~158 KB (epoch-1 style); **not** registered/promoted as production |
| `models/ssri-foundation-v*.pt` | Foundation multitask — **not** assess-loadable Stage 2.5 |
| `poc/.../frontend_rehearsal/.../active.json` | Local rehearsal only; prior audits flag **16-channel** schema-v2 — **reject for live assess** |

**Promotion decision:** **Not performed.** No scientifically credible, non-synthetic production Stage 2.5 artifact was identified. Promoting `SYNTHETIC-*` or `handover` weights as a production model would violate the mandate not to invent/promote unverified checkpoints.

---

## 3. Checkpoint artifact and architecture verification

| Candidate | Channels | Loader keys | Dataset provenance | Production promote? |
|-----------|----------|-------------|--------------------|---------------------|
| Rehearsal registry `best.pt` | **13** | `model_state_dict` + `model_config` | **SYNTHETIC-300k** | **No** |
| `_handover_tmp/best.pt` | **13** | Stage 2.5 | **handover** | **No** |
| Foundation `.pt` under `models/` | 13 (different arch) | Wrong contract | Foundation multitask | **No** |
| Schema-v2 rehearsal active | **16** | Stage 2.5-format | Synthetic v2 | **No** (wrong live contract) |

Live assess requires Stage 2.5 **13-channel** `SSRIModel` checkpoints. Channel mismatch is refused after load.

---

## 4. Promotion result

```text
PROMOTION: NOT PERFORMED
REASON: No valid non-synthetic production Stage 2.5 checkpoint available to promote
```

### Prerequisite to unblock genuine production inference

1. Train (or register) a Stage 2.5 model on a **non-synthetic** dataset with `(13, H, W)` stacks.  
2. Ensure `best.pt` contains `model_state_dict` + `model_config.in_channels=13`.  
3. Register under `{SSRI_API_OUTPUT_ROOT}/training/models/` (automatic on successful manual training job).  
4. Explicitly promote: `POST /api/v1/training/models/activate` with `{ "model_id": "..." }` (operator) **or** platform promote.  
5. Confirm `GET /api/v1/training/models/active` shows `checkpoint_available: true`.  
6. Keep `scientific_validation_status=NOT_VALIDATED` until scientific validation exists.

---

## 5. Assessment API contract changes (this session)

| Change | Detail |
|--------|--------|
| `AssessRequestBody` docstring | Clarifies ordinary clients **omit** `checkpoint`; server resolves promoted registry model |
| `checkpoint` Field description | Optional operator override only (`RUN_INFERENCE`) |
| `model_id` Field description | Registry id resolution without exposing paths |
| `GET /api/v1/ready` → `model_registry` | Safe summary: `active_model_id`, `checkpoint_available`, `scientific_validation_status`, `detail` — **no filesystem paths** |
| New helper | `ssri_model.api.registry_status.active_model_registry_status` |

**Not changed:** validation fail-closed behaviour; auth; scientific validation status; 13-channel contract; demo/live isolation.

---

## 6. Frontend request changes

| Area | Status |
|------|--------|
| `buildAssessRequestBody` | Already omits empty `checkpoint` / `model_id` |
| Dashboard `onAssess` | Already omits empty checkpoint; may send promoted `model_id` when known |
| Ready handling | Now stores `model_registry.detail` for the production-model panel |
| Copy | Clarifies ordinary clients do not send server paths |

No fake inference path was added. Assessment Preview (`SSRI_DEMO_MODE`) remains distinct from live inference.

---

## 7. Hazard and geological-layer presentation

Already correct in current code; verified / preserved:

| Concept | Presentation |
|---------|--------------|
| Subsidence / landslide / sinkhole | Ground-risk hazards (`PRODUCT_HAZARDS`, dashboard hazard selector, `/hazards`) |
| Lineament density / distance / overburden | Geological conditioning — **not** a fourth hazard (`PRODUCT_GEOLOGICAL`, dashboard conditioning panel) |
| Live score drivers | Copy states lineaments/overburden do **not** currently change live 13-channel scores |

`ProductCapabilities` remains on the dashboard panel. Frontend unit tests assert sinkhole visibility and that geological ids are rejected from the hazard list.

---

## 8. Tests executed and exact results

| Suite | Result |
|-------|--------|
| `poetry run pytest tests/test_registry_status.py tests/test_api_health.py tests/test_assess_checkpoint_resolution.py -q` | **19 passed** |
| `cd frontend && npm test` | **66 passed** |

Covered: active-registry resolution without client checkpoint; missing-active actionable error; ready `model_registry` without path leakage; hazard vs geological separation.

---

## 9. Live deployment verification

| Claim | Verdict |
|-------|---------|
| Production API process reachable | **Verified** (health/ready 200) |
| Production OpenAPI optional `checkpoint` | **Verified** |
| Production has a promoted Stage 2.5 checkpoint | **Not verified** (active endpoint 401; no operator credentials this session) |
| Genuine production neural inference executed | **Not claimed / not verified** |
| Local demo preview assessments | Distinct Assessment Preview path only — **not** production inference |

**Do not declare production assessment deployment successful.** Local tests prove the registry-resolution contract; they do not prove Render hosts a promoted model.

---

## 10. Remaining scientific / operational blockers

1. **No promoted production Stage 2.5 checkpoint** on an observable registry.  
2. Local 13-channel artifacts are **SYNTHETIC / handover** — unsuitable for production promote under current rules.  
3. Production registry contents require **authenticated operator** inspection.  
4. Persistent `/data/outputs` survival across Render restarts remains an ops concern if not already mounted.  
5. Scientific status remains **`NOT_VALIDATED`** even after a future promote.  
6. Local `.env` currently has `SSRI_DEMO_MODE=true` for presentation — turn **off** for live-inference testing.

---

## Files changed this remediation

| Path | Role |
|------|------|
| `model/src/ssri_model/api/routes/assess.py` | Contract documentation for optional checkpoint |
| `model/src/ssri_model/api/routes/health.py` | Emit `model_registry` on ready |
| `model/src/ssri_model/api/schemas.py` | `ReadinessResponse.model_registry` |
| `model/src/ssri_model/api/registry_status.py` | **New** safe registry summary |
| `model/tests/test_registry_status.py` | **New** |
| `model/tests/test_api_health.py` | Ready registry assertions |
| `frontend/lib/api.ts` | Ready type |
| `frontend/app/dashboard/page.tsx` | Registry detail + path-omission copy |

---

## Bottom line

```text
ASSESSMENT API CONTRACT: clients must not supply filesystem checkpoints — VERIFIED IN CODE + PRODUCTION OPENAPI
PRODUCTION CHECKPOINT PROMOTE: BLOCKED — no valid non-synthetic Stage 2.5 artifact identified
GENUINE PRODUCTION INFERENCE: NOT VERIFIED
HAZARD vs LINEAMENT PRESENTATION: CORRECT / PRESERVED
```
