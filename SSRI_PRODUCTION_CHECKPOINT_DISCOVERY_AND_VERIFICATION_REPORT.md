# SSRI — Production Checkpoint Discovery and Verification Audit

**Date:** 2026-11-21  
**Mode:** READ-ONLY investigation (no promote, deploy, env change, Git mutation, or registry write)  
**Production API:** `https://ssri-api.onrender.com`  
**Git tip at investigation (local/remote reference):** `5d2e0cb` (`ssri-completed`) — deploy of this tip to Render was **not** verified via console

---

## 1. Executive verdict

```text
VERDICT: BLOCKED
PRODUCTION_CHECKPOINT_VERIFICATION = NOT_VERIFIED
```

| Question | Answer |
|----------|--------|
| Why does assess return the error? | Resolver found **no usable promoted (active) registry checkpoint** for the request |
| Is a valid 13-channel Stage 2.5 model present on production disk? | **Unknown** — no authorised operator or Render disk access this session |
| Can this audit promote a model? | **No** (explicitly forbidden) |
| Recommended next action | Operator (or Render console) inspection of training registry + `active` pointer, then promote a verified Stage 2.5 **13-channel** model if a candidate exists |

The observed client error maps to HTTP **400** `INVALID_REQUEST` with the server message that begins *“No valid production checkpoint is configured…”*. That message is raised only when active-registry resolution fails closed—not when a promoted file is missing (different wording), and not for auth failures (**401** / **403**).

---

## 2. Production storage configuration findings

### Code / ops intent (not production proof)

| Item | Source | Finding |
|------|--------|---------|
| Intended artifact root | `infra/docker-compose.yml`, `infra/render-worker.env.example`, `docs/operations.md` | `SSRI_API_OUTPUT_ROOT=/data/outputs` |
| Registry layout | `TrainingStorage` | `{output_root}/training/models/` with `registry.json` + `active.json` |
| Checkpoint copy on register | `ModelRegistry.register_from_training` | Copies `best.pt` under `{models_dir}/{model_id}/` |
| API ↔ worker share | Ops docs / Compose | Must use the **same** output root / volume |

### Live production probes (this session)

| Probe | Result | Class |
|-------|--------|-------|
| `GET /api/v1/health` | **200** `status=ok` | **Production** |
| `GET /api/v1/ready` | **200** distributed; postgres/redis/queue **ok** | **Production** |
| Ready checks checkpoint / registry | **No** — filesystem readiness probe only creates/deletes `.ready_probe`; does **not** assert an active model | **Code + production behaviour** |
| `GET /api/v1/training/models` | **401** without credentials | **Production** |
| `GET /api/v1/training/models/active` | **401** without credentials | **Production** |
| `POST /api/v1/assess` (no auth) | **401** `AUTHENTICATION_REQUIRED` | **Production** |
| OpenAPI `AssessRequestBody` includes `model_id` | **Yes** | **Production** |
| Render CLI / `RENDER_API_KEY` | Unavailable | **Access gap** |
| Operator API key / Supabase operator session in agent env | Not configured for this audit (`SSRI_API_KEY` unset) | **Access gap** |

**Not verified against production:**

- Whether a persistent disk is mounted at the configured output root  
- Whether that volume survives redeploy/restart  
- Whether API and worker share the same volume  
- Actual `SSRI_API_OUTPUT_ROOT` value (secret/config; name known from docs only)  
- Contents of `registry.json` / `active.json` on the host  

Local `.env` / Compose settings are **not** used as production evidence.

---

## 3. Training registry findings

### Resolution sequence (authoritative code on `assess.py`)

For a non-demo assess request:

1. **Operator `checkpoint` path** (requires `RUN_INFERENCE`) → must exist under `output_root` after resolve (blocks traversal/symlink escape).  
2. Else **`model_id`**:  
   - If equal to active id → fall through to active resolution.  
   - Else requires `RUN_INFERENCE`; load registry record; path must exist under `models_dir`.  
3. Else **`get_active_checkpoint()`** → reads `active.json` → loads model record → returns registered checkpoint path; must be a file under `models_dir`.  
4. If none of the above → **`InvalidServiceRequestError(_NO_PRODUCTION_CHECKPOINT_MESSAGE)`** → API maps to **`INVALID_REQUEST`**.

### Conditions that produce the *exact* user-facing message

The message *“No valid production checkpoint is configured. Promote a trained Stage 2.5 (13-channel) model…”* is raised when:

- No (authorised) client checkpoint override succeeded, **and**  
- Active registry resolution yields nothing usable (`active.json` missing, empty `model_id`, or exceptions while reading active/model treated as no active), **and**  
- The release-shell soft envelope does not apply (or request is not in that special empty-path shell path).

**Distinct alternate messages (not the one reported):**

| Situation | Message theme |
|-----------|----------------|
| USER supplies `checkpoint` | Authorization — operator required |
| USER selects non-active `model_id` | Authorization — operator required |
| Active selected but file missing | Promoted model selected but checkpoint unavailable |
| Channel mismatch after load | Feature channels ≠ checkpoint `in_channels` |

So the reported error means: **no active/promoted model was discoverable for ordinary active-model resolution**, not “wrong channel count” and not “auth denied.”

### Production registry content

```text
REGISTERED_MODELS: NOT_OBSERVABLE (401 without operator/READ_STATUS credentials)
ACTIVE_MODEL: NOT_OBSERVABLE (401)
CHECKPOINT_FILES_ON_DISK: NOT_OBSERVABLE (no Render shell / volume access)
```

---

## 4. Candidate checkpoint verification matrix

No production candidate could be enumerated or deserialized without operator/console access.

| Criterion | Production result |
|-----------|-------------------|
| Registry model ID | **N/A — not listed** |
| Training stage / architecture | **N/A** |
| Expected input channels = 13 | **N/A** |
| Checkpoint exists + readable | **N/A** |
| Deserialization / `model_config` | **N/A** |
| Already promoted | **N/A** |
| Discoverable by assess resolver | **Inferred fail for current active pointer** (error observed by operators/users) |

### Explicit rejection rules (for when candidates become visible)

| Reject if | Reason |
|-----------|--------|
| `in_channels == 16` (schema-v2) | Not production Stage 2.5 live contract |
| Synthetic / demo-only fixture | Must not be promoted as production |
| File missing / unreadable | Fail closed |
| Unregistered loose `.pt` on disk | Assess will not invent paths for ordinary users |
| Metadata cannot establish Stage 2.5 `SSRIModel` compatibility | Unsafe to promote |

Valid production candidate **must** be a trained Stage 2.5 checkpoint with **exactly 13** input channels (`CHANNEL_COUNT` from `CHANNEL_NAMES`).

---

## 5. Active-model and promotion status

| Item | Status |
|------|--------|
| Production active model | **Unknown** (endpoint 401); assess behaviour implies **no usable active** |
| Promotion executed this audit | **No** |
| Immediate effect of promotion (code) | Writes `active.json` under models dir; **no API process restart required** for subsequent requests reading the registry from disk |
| Persistence | Survives only if `output_root` is on durable storage; **disk durability NOT_VERIFIED** on Render |

---

## 6. Exact root cause of the current production error

**Primary root cause (evidence-based):**

The assessment API’s active-model resolver did not find a promoted Stage 2.5 checkpoint. With no authorised client checkpoint override, it fail-closed with:

`INVALID_REQUEST` ← `InvalidServiceRequestError` ← `_NO_PRODUCTION_CHECKPOINT_MESSAGE`

**Most likely operational underlying causes** (ordered; not mutually exclusive; disk state unconfirmed):

1. **No `active.json` (never promoted)** on the production output root.  
2. **Empty or wiped training registry** after deploy because output root is ephemeral (no persistent disk / wrong mount).  
3. **Active pointer / registry on a different filesystem** than the running API process expects.  
4. **`active.json` present but model id missing from `registry.json`** (resolver treats as no active).  

**Ruled out as the message source:** anonymous access (would be **401**), USER checkpoint override (would be **403**), and “promoted but file gone” (different **400** text).

**Not claimed:** that zero trained artifacts exist somewhere on the host—only that the **active** path used by assess is empty/unusable.

---

## 7. Supported promotion procedure (do not execute)

### Permissions

- `POST /api/v1/training/models/activate` requires **`RUN_INFERENCE`** (operator / admin / equivalent API key).  
- Ordinary `USER` (`RUN_ASSESS` only) **cannot** promote.

### Prerequisites

1. At least one registered model in `{output_root}/training/models/registry.json`.  
2. That model’s copied `best.pt` exists under the models directory.  
3. Checkpoint is Stage 2.5 with `model_config.in_channels == 13` (verify before promote).  
4. Accept that registry status remains `scientific_validation_status=NOT_VALIDATED`.

### API

```http
POST /api/v1/training/models/activate
Authorization: Bearer <operator-or-admin-credential>
Content-Type: application/json

{ "model_id": "<registered-id>" }
```

UI equivalent: operator training surface (“Promote for assessments”) → same endpoint (`docs/operations.md`, manual training briefing).

### Persistence / rollback

- **Activate:** writes/overwrites `active.json` with `model_id`, checkpoint path, `activated_at`.  
- **Deactivate:** `POST /api/v1/training/models/deactivate` deletes active pointer.  
- **Restart:** not required for the API to see the new active file on the next request.  
- **Does not** mark the model scientifically validated.

Platform completion may also call `registry.activate(...)` in account flows; that is a separate product path and still requires a real registered Stage 2.5 artifact.

---

## 8. Required operational actions

1. **Obtain operator credentials** (Supabase operator/admin session or operator API key) *or* Render shell / disk console access.  
2. Call `GET /api/v1/training/models` and `GET /api/v1/training/models/active` as operator.  
3. Record (internally, not in public docs): model ids, `checkpoint_available`, architecture/`in_channels` via safe operator inspection of checkpoint metadata—**do not paste absolute paths into public reports**.  
4. Confirm Render service has a **persistent** disk mounted at the configured `SSRI_API_OUTPUT_ROOT`, shared with the worker if used.  
5. If a valid **13-channel** Stage 2.5 candidate exists and is registered → **owner-approved** `POST .../models/activate`.  
6. If registry empty but a real trained artifact exists offline → register via the supported training/register pipeline on that persistent root (do **not** invent or copy a fake checkpoint).  
7. If no real Stage 2.5 model exists → train from a labelled Stage 2.5 dataset, then promote.  
8. Re-run authenticated assess **without** client filesystem paths.

---

## 9. Authenticated assessment smoke-test plan

After an owner-approved promotion (outside this audit):

| # | Step | Expected |
|---|------|----------|
| 1 | Operator `GET .../models/active` | Active model id present; `checkpoint_available=true`; USER view has **null** path |
| 2 | Confirm `in_channels == 13` on loaded checkpoint metadata | Pass |
| 3 | Authenticated USER `POST /api/v1/assess` with point/AOI, **no** `checkpoint` | **200** hazard profiles **or** clear acquisition error—not the “no valid production checkpoint” message |
| 4 | Anonymous assess | **401** |
| 5 | USER with explicit `checkpoint` | **403** |
| 6 | USER with non-active `model_id` | **403** |
| 7 | 16-channel feature stack against 13-ch model | **400** channel mismatch (no silent pad/truncate) |
| 8 | Hazards | Subsidence, landslide, sinkhole present; geo conditioning not a fourth hazard |

---

## 10. Evidence classes: production vs local

| Finding | Evidence class |
|---------|----------------|
| Health/ready 200; training endpoints 401; assess 401 without auth | **Verified against live production** |
| OpenAPI exposes `model_id`, activate/active routes | **Verified against live production** |
| Exact `INVALID_REQUEST` message source and resolution order | **Verified in source code** (matches deployed OpenAPI shape) |
| Ready does not check active checkpoint | **Verified in source code** |
| Promotion endpoint + `active.json` behaviour | **Verified in source code** + docs |
| Persistent disk mounted / registry contents / channel counts of prod candidates | **Not verified** (access missing) |
| Local fixtures / local `output_root` | **Local only — not production evidence** |
| Prior successful local/handover assess JSON in `poc/_tmp_*` | **Local/historical artifact — not current production proof** |

---

## Final rule compliance

- No promotion, deploy, env change, Git change, or registry mutation.  
- No fabricated checkpoint.  
- No 16-channel substitution.  
- No client filesystem path recommendation for ordinary users.  
- No secrets or absolute production filesystem paths printed.

### Exact recommended next action

**With operator or Render console access, inspect the production training registry and active pointer on the persistent output root; if a registered Stage 2.5 13-channel checkpoint exists, promote it via `POST /api/v1/training/models/activate` under separate owner approval; if none exists, train/register a real Stage 2.5 model on that durable volume before any go-live claim.**
