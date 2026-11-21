# SSRI — Live Assessment & Geological Visibility Remediation Report

**Date:** 2026-11-21  
**Mode:** Inspect, implement, test, report (no commit / push / deploy)  
**HEAD preserved:** `d06878699f398a3b364a3ce48498c9cc0149786d` (Commit C — authentication)  
**Phase 6:** remains **BLOCKED**  
**Scientific validation:** `NOT_VALIDATED`

---

## 1. Root cause of the missing checkpoint error

Production returned:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Assessment requires 'checkpoint'."
  }
}
```

That message was raised only when:

1. `SSRI_DEMO_MODE` was off,
2. release-shell soft envelope was off,
3. the request body had `checkpoint: null` / omitted.

### Lifecycle failure

| Step | Behaviour before fix |
|------|----------------------|
| Dashboard Run Assessment | Sent `checkpoint: checkpoint \|\| undefined` |
| Active model prefetch | Soft-failed on auth/network; left local `checkpoint` empty |
| Client contract | Expected the browser to supply a **server filesystem path** |
| Backend `/api/v1/assess` | Required `checkpoint` and did **not** resolve the promoted registry model |
| Result | `INVALID_REQUEST: Assessment requires 'checkpoint'.` |

The UI already claimed ordinary assessments use the promoted model automatically, but the API never did. After Commit C, authenticated clients that never send an operator path hit this gap.

**Not the cause:** inventing a missing file name; 16-channel schema-v2; auth rejection (that would be `AUTHENTICATION_REQUIRED`).

---

## 2. Exact frontend and backend files changed

### Backend

| File | Change |
|------|--------|
| `model/src/ssri_model/api/routes/assess.py` | Server-side checkpoint resolution (`active_registry` / `model_id` / optional operator `checkpoint`); clear missing/unavailable errors; explicit 13-vs-16 channel mismatch guard; `checkpoint_source=…` note |
| `model/src/ssri_model/api/routes/training.py` | Active-model response adds `checkpoint_available` + `model_id` |
| `model/tests/test_assess_checkpoint_resolution.py` | New regression coverage |
| `model/tests/test_demo_mode_assess.py` | Expect updated missing-checkpoint wording |
| `model/tests/test_release_shell_assess.py` | Assert checkpoint language when flag off |

### Frontend

| File | Change |
|------|--------|
| `frontend/lib/assessRequest.ts` | `buildAssessRequestBody` — omit empty checkpoint/model_id; never invent paths |
| `frontend/lib/api.ts` | Optional `model_id`; use builder; clearer checkpoint errors |
| `frontend/app/dashboard/page.tsx` | Status for promoted model; do not auto-send filesystem paths; always show 3 hazards + geological conditioning panel + capabilities |
| `frontend/lib/productCapabilities.ts` | Canonical hazard / geological / safeguard catalogue + `mergeHazardNames` |
| `frontend/components/product/ProductCapabilities.tsx` | Client-facing capability section |
| `frontend/app/page.tsx` | Landing includes `ProductCapabilities` |
| `frontend/app/shell/page.tsx` | Null-safe active path |
| `frontend/app/training/operator/page.tsx` | Null-safe active path |
| `frontend/e2e/dashboard.spec.ts` | Expect new missing-checkpoint copy |
| `frontend/lib/assessRequest.test.ts` | Request-contract tests |
| `frontend/lib/productCapabilities.test.ts` | Hazard/geological visibility tests |

Ruff remediation working-tree edits from the prior task remain present and **uncommitted**; they were not reworked for this task.

**Authentication code paths were not modified** (dependencies, RBAC, Supabase session forwarding, rate limiting remain as in Commit C).

---

## 3. Corrected request and checkpoint-resolution flow

```text
Client (dashboard)
  └─ POST /api/v1/assess
       body: { point|polygon|features, hazards, model_id? }
       # checkpoint omitted for ordinary clients

API assess_endpoint
  ├─ auth + rate limit (unchanged)
  ├─ resolve_assessment_checkpoint()
  │     1. body.checkpoint  → source=client_path (operators only)
  │     2. body.model_id    → registry lookup, source=model_id
  │     3. active registry  → source=active_registry
  │     else → INVALID_REQUEST: No valid production checkpoint is configured…
  ├─ load checkpoint + enforce channel count vs model_config.in_channels
  └─ Stage 2.5 inference (13-channel live contract)
```

Clients are not required to know or send server paths. If no promoted model exists, the API returns an actionable configuration error instead of inventing a checkpoint.

---

## 4. Production 13-channel contract

- Live assessment continues to load Stage 2.5 checkpoints via `load_inference_checkpoint`.
- After load, feature channel count must equal `model_config.in_channels` (default 13).
- A 16-channel schema-v2 stack against a 13-channel checkpoint is rejected with a plain-language 400.
- No padding, truncation, or zero-fill compatibility bridge.
- Phase 6 live schema-v2 inference remains **BLOCKED**.
- Hazard set remains `subsidence`, `landslide`, `sinkhole`.
- Scientific status remains **NOT_VALIDATED**.

---

## 5. All three hazards visible

- Dashboard hazard selector uses `mergeHazardNames` so **sinkhole** cannot be dropped by a truncated registry payload.
- Explicit `data-testid="hazard-option-{name}"` for each hazard.
- Landing + dashboard `ProductCapabilities` lists Subsidence, Landslide, Sinkhole.
- Existing `/hazards` page already covered all three; left intact.

---

## 6. Lineament and overburden presentation

Presented as **Geological conditioning / Geological intelligence**, not a fourth hazard:

- Overburden thickness — offline conditioning supported; live inference integration pending  
- Lineament density — available for geological data management; live inference integration pending  
- Distance to lineaments — available for geological data management; live inference integration pending  
- Geological dataset ingestion and validation — catalogue workflow  

Dashboard panel + landing capabilities section state clearly that these do **not** currently change live 13-channel map scores. Result analytics still use `buildConditioningGroups` for per-assessment availability without inventing measurements.

---

## 7. Tests executed and results

### Backend (focused)

```text
poetry run pytest tests/test_assess_checkpoint_resolution.py -q
→ 11 passed
```

Broader assess/auth/training batch (same session):

```text
tests/test_assess_checkpoint_resolution.py
tests/test_release_shell_assess.py
tests/test_demo_mode_assess.py
tests/test_api_assess.py
tests/test_assess_supabase_auth.py
tests/test_api_assess_audit.py
tests/test_assess_geotiff_and_conditioning.py
tests/test_assess_location_provenance.py
tests/test_manual_training.py
→ 57 passed (exit 0)
```

### Frontend

```text
npm test
→ 42 passed, 0 failed
```

### Full backend suite

```text
poetry run pytest -q --tb=line
→ 839 passed, 3 skipped in 238.82s
```

---

## 8. Remaining limitations

1. **Production still needs a promoted Stage 2.5 checkpoint** in the training registry on the API host. Code can resolve it; it cannot invent one.
2. **Live AOI acquisition** still requires `SSRI_LIVE_ACQUISITION_ENABLED` (+ GEE/OpenTopography) unless offline `.npy` features are supplied.
3. **Lineament / overburden do not drive live scores** until a scientifically evaluated compatible model exists (Phase 6 blocked).
4. **Deploy required** before production clients see this fix; this task did not deploy.
5. Operator advanced path override remains available for labs/tests; ordinary clients should leave it empty.
6. Active-model endpoint still returns `checkpoint_path` for operators/tests; ordinary UI no longer sends it.

---

## 9. Exact production verification procedure

Do **not** mark production fixed until these steps succeed against the deployed hosts after an approved deploy.

### A. Frontend assessment workflow

1. Sign in on the live frontend with a user that can run assess.
2. Open `/dashboard`.
3. Confirm **Production model** shows either the promoted model label or the clear “No promoted…configured” message (not a blank path field as the primary control).
4. Confirm hazard chips include **subsidence**, **landslide**, **sinkhole**.
5. Confirm **Geological conditioning** lists overburden + lineament density + distance with live-pending wording.
6. Confirm landing `/` shows **What SSRI can show you today** with the three capability columns.
7. Select a map point and click **Run assessment** (with a promoted model present).

### B. Request payload

In browser DevTools → Network → `POST …/api/v1/assess`:

- Must include auth (`Authorization: Bearer …`).
- Ordinary client body should **omit** `checkpoint` (or leave it unset).
- May include `model_id` of the promoted model.
- Must include `point` or `polygon_geojson` (or offline `features`).
- Must include all three hazards when selected.

### C. API response

- Success: `200` with three `hazard_profiles` and notes containing `checkpoint_source=active_registry` or `checkpoint_source=model_id`.
- Missing promotion: `400` with `No valid production checkpoint is configured…` (not the old `Assessment requires 'checkpoint'.` for empty client path when resolution is intended).
- Auth failure still `401 AUTHENTICATION_REQUIRED`.

### D. Checkpoint resolution

1. `GET /api/v1/training/models/active` → `checkpoint_available: true`, `model_id` set, `scientific_validation_status: NOT_VALIDATED`.
2. Assess without `checkpoint` succeeds only when that active file exists on the API host.
3. Deactivate / remove active → assess without path fails with actionable configuration error.

### E. Hazard + geological visibility

- Dashboard hazard selector: all three visible without horizontal clipping on mobile width.
- Geological panel visible without treating lineaments as a hazard.
- Capabilities section distinguishes offline vs live.

### F. Auth / RBAC

- Signed-out assess → authentication required.
- Signed-in Role.USER → can run assess.
- Geological mutations still require elevated permission (`MANAGE_GEOLOGICAL` / admin as previously hardened).

---

## 10. Git status and preservation confirmation

```text
HEAD: d06878699f398a3b364a3ce48498c9cc0149786d
Commit: Harden Supabase assessment authentication and permissions
```

- **No commit** created for this remediation.
- **No push**.
- **No deploy**.
- **No history rewrite**.
- Commit C authentication implementation preserved.
- Prior uncommitted Ruff fixes and client-specific leftovers remain in the working tree and were not deleted.

---

## Verdict

| Requirement | Status |
|-------------|--------|
| Root-cause identified | Done — client omitted path; API did not resolve active registry |
| Valid registered checkpoint resolution | Implemented server-side |
| Clear error when none configured | Implemented |
| No invented checkpoint / no path forced on clients | Confirmed |
| 13-channel live contract preserved | Confirmed + channel mismatch guard |
| Three hazards visible | Confirmed |
| Lineaments as conditioning, not hazard | Confirmed |
| Auth / rate limit preserved | Confirmed (untouched) |
| Phase 6 blocked / NOT_VALIDATED | Confirmed |
| Production verified live | **Pending owner deploy + §9 procedure** |
