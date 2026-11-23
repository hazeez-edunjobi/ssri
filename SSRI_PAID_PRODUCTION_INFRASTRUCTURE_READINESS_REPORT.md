# SSRI — Paid Production Infrastructure Readiness Report

**Date:** 2026-11-23  
**Scope:** Read-only verification. No code, config, billing, deploy, upload, promotion, or secret changes.  
**Repository tip inspected:** `main` @ `d6e877a` (tracks `origin/main`)  
**Live API:** `https://ssri-api.onrender.com`  
**Live frontend:** `https://ssri-gamma.vercel.app`

---

### 1. Executive verdict

**NOT READY — MULTIPLE BLOCKERS.**

Upgrading the existing Render `ssri-api` Web Service to a paid plan alone does **not** make SSRI an operational production ML platform. Paid compute removes free-tier sleep/spin-down and enables a persistent disk, but the live system still lacks:

1. A **promoted Stage 2.5 checkpoint** on durable storage (`checkpoint_available=false` on `/api/v1/ready`).
2. A **confirmed always-on Celery worker** (code and docs exist; production deployment is **NOT_VERIFIED**).
3. **Durable shared storage** compatible with both API and worker. Geological catalogue, training datasets, registry, and checkpoints are filesystem-bound under `SSRI_API_OUTPUT_ROOT`. Render persistent disks **cannot be shared across services** ([Render Disks docs](https://render.com/docs/disks)), which invalidates “API disk + separate worker sharing the same mount” without additional architecture work.
4. **Firebase Storage is not integrated at all** (zero repository matches). Billing/Blaze is irrelevant until an integration exists.
5. Live AOI acquisition remains an optional env gate (`SSRI_LIVE_ACQUISITION_ENABLED`); production value **NOT_VERIFIED** without dashboard access to env.

**What paid API upgrade does solve:** always-on HTTP process, ability to attach a disk, headroom above free-tier 512 MB / spin-down.  
**What it does not solve:** missing model, missing worker, ephemeral/shared-storage gap, Firebase preference, scientific validation (`NOT_VALIDATED` remains correct and unchanged).

---

### 2. Verified current architecture

| Layer | Actual production posture | Status |
|---|---|---|
| Frontend | Vercel `https://ssri-gamma.vercel.app` | VERIFIED (prior deploy audits; not re-probed this pass) |
| API | Render Web Service `ssri-api` → Docker `model/Dockerfile` `CMD ["api"]` → `uvicorn ssri_model.api.app:app` | VERIFIED live |
| Execution mode | `/api/v1/ready` reports `infrastructure.mode=distributed`, postgres/redis/queue `ok` | VERIFIED live |
| Redis broker | Owner-stated Upstash `rediss://` on `SSRI_REDIS_URL` / Celery broker / result backend; live ready shows redis+queue connected | PARTIALLY VERIFIED (connectivity yes; secret values not inspected) |
| Render Valkey | Present in dashboard per owner; API Redis vars point to Upstash, not Valkey | PARTIALLY VERIFIED (owner statement + code defaults; dashboard not re-logged) |
| Celery worker | Implemented (`ssri_model.worker`); **no public proof of a running production worker** | NOT_VERIFIED deploy |
| Postgres | Supabase (platform) + job store reachable (`postgresql` ready component `ok`) | VERIFIED connectivity |
| Model registry | Filesystem under `{SSRI_API_OUTPUT_ROOT}/training/models` via `TrainingStorage` / `ModelRegistry` | VERIFIED code; live `active_model_id=null` |
| Geological storage | Local FS catalogue; object backends explicitly refused (`geological/durable.py`) | VERIFIED code |
| Assess GeoTIFF object store | Optional `ObjectStorage` local/S3/R2 (`storage/__init__.py`); default local | VERIFIED code; prod backend NOT_VERIFIED |
| Platform dataset uploads | Optional Supabase Storage bucket `datasets` (`platform/supabase_store.py`) | VERIFIED code; prod bucket activity NOT_VERIFIED |
| Firebase | No SDK, env, rules, or references in repo | VERIFIED absent |
| Demo mode | Forced off in production/staging (`APIConfig.resolve_demo_mode`); live `demo_mode=false` | VERIFIED |
| Scientific status | Assess path stamps `NOT_VALIDATED`; live registry status `null` (no active model) | VERIFIED |

**Live probe (2026-11-23, source: terminal capture):**

- `GET /api/v1/health` → `{"status":"ok","service":"ssri-inference"}` — **PASS**
- `GET /api/v1/ready` → `status=ready`, `demo_mode=false`, `mode=distributed`, components configuration/postgresql/redis/queue `ok`, `active_model_id=null`, `checkpoint_available=false`, detail: *No promoted Stage 2.5 model is configured in the training registry.* — **PASS (infra) / FAIL (model serving)**
- `GET /openapi.json` → version `0.1.0`, 67 paths; assess, jobs, training active model, geological datasets, inference async present — **PASS**

---

### 3. Render paid API assessment

#### 3.1 Can the current API run on a paid Web Service without code changes?

**Yes for HTTP health/OpenAPI/distributed job enqueue plumbing** — the image and entrypoint are already production-shaped.

Evidence:

- `model/Dockerfile` lines 77–78: `ENTRYPOINT` + `CMD ["api"]`
- `model/docker-entrypoint.sh` lines 7–8: `uvicorn ssri_model.api.app:app --host 0.0.0.0 --port ${SSRI_API_PORT:-8000}`
- Live service already serves health/ready/OpenAPI

**No for durable ML operations** without storage + checkpoint + (for async) worker work.

#### 3.2 Is the deployment command correct?

**PASS** for the API role: Docker command / entrypoint role `api` is correct. Do not use the worker command on the web service.

#### 3.3 Filesystem persistence dependency

**FAIL (ephemeral risk) if no durable mount.**

| Workflow | Storage path | Provider today |
|---|---|---|
| Geological catalogue | `{output_root}/geological` | Local FS only (`build_geological_storage`) |
| Training datasets / runs / models | `{output_root}/training/...` | `TrainingStorage` FS |
| Active registry | `{output_root}/training/models` | FS + JSON registry |
| Assessment acquisition/outputs | `{output_root}/assessments/...` | FS (+ optional object store for GeoTIFF URLs) |
| Platform product dataset originals | Supabase Storage `datasets/` | Object (platform path only) |

`geological/durable.py` lines 1–22 and 50–69: object backends `r2`/`s3`/… are **refused**; production path is durable `SSRI_API_OUTPUT_ROOT`.

#### 3.4 Does upgrading the API alone provide durable storage?

**No.** Paid compute ≠ disk. Disk must be attached explicitly ([Render Disks](https://render.com/docs/disks)). Without it, redeploy/restart wipes `/data/outputs`.

#### 3.5 Does the API need a persistent disk?

**Yes, under current code**, *or* an engineered shared object-storage migration (not complete for geological/training/registry).

**Critical Render constraint:** a persistent disk is usable by **one service instance only** and cannot be mounted by a separate Background Worker. Therefore “API disk + worker sharing `/data/outputs`” is **architecturally incompatible with Render disks** as documented by Render. The wording in `infra/WORKER_PRODUCTION_DEPLOY.md` step 5 (“Attach the same persistent disk”) is **operationally incorrect on Render** and must not be funded as-is.

#### 3.6 Shared external storage backend support

| Capability | Status |
|---|---|
| Assess GeoTIFF via S3/R2 `ObjectStorage` | Implemented (`storage/__init__.py`) |
| Geological catalogue on object storage | **Refused** (`durable.py`) |
| TrainingStorage / registry on object storage | **Not implemented** (pure Path FS) |
| Firebase | **Not implemented** |
| Supabase Storage for Stage 2.5 training/geological | **Not** the Stage 2.5 path; platform uploads only |

#### 3.7 Checkpoint load after restart/redeploy

Requires (a) promoted registry metadata + `best.pt` on durable media and (b) that media still present after restart. Live: no active model → **FAIL** regardless of plan tier.

#### 3.8 Free-tier vs application gaps

| Symptom | Free-tier cause? | Application/config cause? |
|---|---|---|
| Cold starts / sleep | Yes (free web) | — |
| Lost uploads after redeploy | Yes if no disk | Also: FS architecture |
| `checkpoint_available=false` | No | No promoted checkpoint / empty registry |
| Async jobs never complete | Possible if worker never deployed (not free-tier specific) | Missing worker service |
| Firebase “not working” | No | Missing integration |

#### 3.9 Minimum viable Render compute (evidence-based)

Stage 2.5 defaults (`SSRIModelConfig`): `base_channels=32`, `num_encoder_stages=3`, 13 in / 3 out (`architecture/config.py`). Parameter counter exists (`count_parameters` in `architecture/model.py`) but a live parameter dump was **not** executed this audit (**NOT_VERIFIED** exact count). Architecture docs describe a compact U-Net-scale network (encoder 32→64→128, bottleneck 256).

**RAM is dominated by the process footprint, not parameter tensors alone:** CPU PyTorch (`Dockerfile` pins `torch==2.5.1` CPU), rasterio/whitebox, FastAPI, and concurrent request buffers. Free/Starter **512 MB** is inadequate for reliable PyTorch + geospatial serving.

| Role | Minimum plan | Evidence |
|---|---|---|
| API (sync assess, no training) | **1 CPU / 2 GB** (`1c-2g`, legacy Standard) **$25/mo** | Below 2 GB: high OOM risk with torch+stack; 0.5c/512MB insufficient |
| Worker (inference/batch jobs) | **1 CPU / 2 GB** minimum | Same torch image; concurrency `SSRI_CELERY_CONCURRENCY=1` |
| Worker (training jobs) | **2 CPU / 4 GB** (`2c-4g`) **$85/mo** strongly preferred | Training materializes batches + checkpoints; 2 GB is borderline |

Disk (if Option A-style API-local durability for sync-only): start **10–25 GB** @ **$0.25/GB-mo** ([Render pricing](https://render.com/pricing)) for catalogues + one checkpoint; increase for multi-dataset ZIPs/GeoTIFFs.

---

### 4. Firebase Storage assessment

**Status: NOT INTEGRATED AT ALL.**

Repository-wide search for `firebase`, `Firebase`, `FIREBASE`, `firebase_admin`, `google.cloud.storage` (app code/deps): **zero matches**. `model/pyproject.toml` has `boto3` and Celery/torch — **no** Firebase Admin/client SDK.

| Workflow | Current destination | Firebase today | Could Firebase replace without code? |
|---|---|---|---|
| Geological uploads / catalogue | Local FS under `output_root/geological` | No | **No** — needs catalogue rewrite (`durable.py` refuses object backends) |
| Original geological files | FS | No | No |
| Processed geological datasets | FS | No | No |
| Training datasets (Stage 2.5) | `TrainingStorage` FS | No | No |
| Training artefacts / runs | FS `training/runs` | No | No |
| Checkpoints / `best.pt` | FS `training/models` | No | No |
| Active model registry | FS JSON + paths | No | No |
| Assessment rasters | FS + optional S3/R2 ObjectStorage | No | Partial only if wired as S3-compatible (GCS) — still code |
| Platform dataset originals | Supabase `datasets` bucket | No | Separate product path |

**Billing vs integration:** Firebase Cloud Storage requires the **Blaze** plan to provision/use buckets ([Firebase Storage FAQ](https://firebase.google.com/docs/storage/faqs-storage-changes-announced-sept-2024)). That is a real Firebase product constraint **if** you choose Firebase later. It is **not** the current production blocker: SSRI never calls Firebase. Enabling Blaze alone changes nothing in this codebase.

**Suitability if implemented later:** GCS/Firebase can store large ZIPs, GeoTIFFs, `.npy`, and `.pt` blobs, but SSRI’s server-side ML paths expect **POSIX paths**, atomic replace writes, JSONL ledgers, and `FileResponse`-style readers. Firebase is a poor drop-in; prefer **S3-compatible object storage** already partially abstracted (`ObjectStorage`) or a **shared durable filesystem** on a single host. Firebase adds Auth rules/client SDK complexity without matching the existing `boto3` path.

**Integration work if insisted upon (not recommended as first choice):** Admin SDK + service account; download-to-local-cache for training/inference; rewrite `GeologicalStorage`/`TrainingStorage`/registry; Blaze + bucket + IAM; dual API/worker credentials. This is a **multi-sprint application project**, not a config flip.

---

### 5. Storage recommendation

**Choose: S3-compatible object storage (Cloudflare R2 / AWS S3 / GCS via S3 API) for shareable artifacts, plus either (a) a single-host durable volume for the geological catalogue until object-catalogue work lands, or (b) complete the geological object-backend work before splitting API/worker on Render.**

Ranking against actual code:

1. **S3-compatible (R2/S3)** — Best fit: `ObjectStorage` + `boto3` already exist for assess outputs; worker/API can share; no Firebase SDK gap. Geological/training still need implementation before full cutover.
2. **Render persistent disk on one service only** — Valid for **API-only sync** durability; **invalid** as shared API↔worker mount on Render.
3. **Supabase Storage** — Keep for **platform** `datasets` uploads (`upload_dataset_object` → `storage/v1/object/datasets/...`). Do **not** assume it covers Stage 2.5 geological/training/registry.
4. **Firebase Storage** — Owner preference only; **not** present; higher integration cost than extending existing S3 path.
5. **Render Valkey** — **Redundant** while Upstash backs Redis/Celery (live queue ready). Paying for both duplicates broker cost. Safe to leave unused or delete only after confirming no other service points at it (**NOT_VERIFIED** other consumers).

**Do not** treat “set `SSRI_GEOLOGICAL_STORAGE_BACKEND=s3`” as migration — it **raises** `InvalidServiceConfigError` today.

---

### 6. Celery worker assessment

| Item | Finding | Status |
|---|---|---|
| Entry point | `celery -A ssri_model.worker.celery_app worker -Q ssri_jobs` via `docker-entrypoint.sh` role `worker` | VERIFIED code |
| Task | `ssri.execute_job` registered from `worker/tasks.py` | VERIFIED code |
| Queue | `ssri_jobs` (`celery_app.py` `task_default_queue`) | VERIFIED |
| Broker/backend | `SSRI_CELERY_BROKER_URL` or `SSRI_REDIS_URL`; result backend defaults to broker | VERIFIED |
| Job store | Postgres `DatabaseJobStore` required in worker context | VERIFIED |
| Retry / heartbeat | Retry requeue + `HeartbeatController` / lease recovery design | VERIFIED code |
| Production deploy | No worker URL; prior release report: continuously running worker **NOT_VERIFIED** | NOT_VERIFIED |
| Redis env alone proves worker? | **No** — API can connect to Redis without a consumer | FAIL inference |

**Minimum viable worker**

| Setting | Value |
|---|---|
| Hosting | Render **Background Worker** (same Docker image, command `worker`) **or** any always-on VM running the same image |
| Build | `model/` Dockerfile context |
| Start | `worker` |
| Env | Same as API: `SSRI_EXECUTION_MODE=distributed`, `SSRI_DATABASE_URL`, Upstash Redis trio, `SSRI_API_OUTPUT_ROOT`, object-storage vars, acquisition secrets as needed |
| Storage | **Must see the same artifacts the API writes** — impossible via Render disk sharing; use object storage, single-host disk, or sync strategy |
| Concurrency | `SSRI_CELERY_CONCURRENCY=1` |
| Compute | ≥ 1c/2g; training → 2c/4g |

**Cost preference:** One paid API + one paid worker on Render is the path of least operational novelty. A single small VPS running **both** `api` and `worker` with one disk can be cheaper and correctly shares FS — but is a hosting-model change. Do **not** fund Render Valkey if Upstash remains broker.

---

### 7. Model-serving assessment

| Check | Production value / finding | Status |
|---|---|---|
| `demo_mode` | `false` | VERIFIED live |
| `active_model_id` | `null` | VERIFIED live |
| `checkpoint_available` | `false` | VERIFIED live |
| Scientific validation | `null` (no model); assess code keeps `NOT_VALIDATED` | VERIFIED |
| Stage 2.5 architecture | `SSRIModel`, 13-ch `CHANNEL_COUNT`, 3 classes | VERIFIED code |
| Checkpoint resolve | `resolve_assessment_checkpoint` → active registry FS file | VERIFIED code |
| Genuine inference | **Blocked** — no promoted checkpoint | FAIL |
| Point/polygon assess routes | Present in OpenAPI | VERIFIED surface |
| Live AOI acquisition | Requires `SSRI_LIVE_ACQUISITION_ENABLED=true` + GEE/OpenTopo | NOT_VERIFIED prod env |
| Fabricated scores | Disabled when demo off | VERIFIED code |

Distinction:

1. **API health** — PASS  
2. **Infrastructure readiness** (Postgres/Redis/queue from API’s view) — PASS  
3. **Worker readiness** — NOT_VERIFIED / treat as FAIL for async  
4. **Checkpoint availability** — FAIL  
5. **Checkpoint compatibility** — NOT_VERIFIED (nothing loaded)  
6. **Scientific validation** — correctly `NOT_VALIDATED`; not a hosting issue  
7. **Genuine inference availability** — **FAIL**

---

### 8. Paid infrastructure requirements

| Service | Required? | Paid plan required? | Purpose | Evidence |
|---|---|---|---|---|
| Vercel frontend | Yes (already) | Hobby may suffice; Pro if team needs | UI | Existing `ssri-gamma.vercel.app` |
| Render API Web Service | Yes | **Yes** for always-on + disk eligibility | FastAPI | Live `ssri-api`; free spins down |
| Render persistent disk | **Conditional** | Yes ($0.25/GB-mo) | Durable `SSRI_API_OUTPUT_ROOT` on **one** instance | FS-bound geological/training; Render disk single-service limit |
| Render Background Worker | Yes for async training/jobs | **Yes** (always-on) | Celery `ssri_jobs` | Code + `WORKER_PRODUCTION_DEPLOY.md`; deploy NOT_VERIFIED |
| Upstash Redis | Yes (already) | Upgrade if free limits bind | Broker + result backend | Live redis/queue ok; [Upstash pricing](https://upstash.com/pricing/redis) |
| Render Valkey | **No** (duplicate) | Do not pay if unused | — | API uses Upstash per owner + ready |
| Supabase Postgres | Yes | Per Supabase plan | Jobs + platform metadata | Ready component ok |
| Supabase Storage `datasets` | Platform path only | Per Supabase | Platform dataset originals | `supabase_store.upload_dataset_object` |
| S3/R2 object storage | **Strongly recommended** for API↔worker share | Usage-based | Assess artifacts now; training/geo after code | `ObjectStorage`; geological refuses today |
| Firebase Storage | **Not required** | Blaze if chosen later | — | Zero integration |
| GEE / OpenTopo keys | Required for live AOI | Provider billing as applicable | Live acquisition | `SSRI_LIVE_ACQUISITION_ENABLED` gate |

**Illustrative minimum monthly compute (official list prices, not a quote):**

- API `1c-2g`: **$25**  
- Worker `1c-2g` (inference) or `2c-4g` (training): **$25** or **$85**  
- Disk 20 GB: **$5**  
- Upstash: free → Pay-as-you-go / Fixed from **$10** if limits require  
- Firebase: **$0** until integrated; Blaze required then  

Exact totals depend on chosen architecture (below).

---

### 9. Remaining engineering work (priority order)

1. **Promote a real Stage 2.5 `best.pt` into the training registry on durable storage** and confirm `/api/v1/ready` → `checkpoint_available=true` (ops + durable media; do not change `NOT_VALIDATED`).
2. **Decide storage architecture that API and worker can both read** — knowing Render disks are single-service. Prefer R2/S3 share **or** single-host FS; do not fund “shared Render disk.”
3. **Deploy Celery Background Worker** (`command: worker`, same image, same Redis/Postgres, shared artifact strategy) and prove `ssri.execute_job` end-to-end.
4. **Attach durable storage to the artifact root** (`SSRI_API_OUTPUT_ROOT=/data/outputs`) before any production uploads/training.
5. **If split services on object storage:** implement geological catalogue object backend (list/get/conditional write/locks) — today refused in `durable.py`; migrate `TrainingStorage`/registry off pure Path assumptions.
6. **Configure live acquisition** (`SSRI_LIVE_ACQUISITION_ENABLED`, GEE/OpenTopo) if map AOI assess is in scope — else document offline `.npy`/prestacked-only.
7. **Point `SSRI_OBJECT_STORAGE_*` at S3/R2** for assess GeoTIFF durability (already supported).
8. **Leave Firebase out** unless a funded integration project is approved; do not bill client for Blaze “to unblock SSRI” — it does not.
9. **Decommission or ignore Render Valkey** once confirmed unused.
10. **Fix global git identity risk** (see §14) before further commits from machines using `olaniyanp11` global config.

---

### 10. Client funding recommendation

**Is it reasonable to ask the client to fund production infrastructure now?**  
**Yes — selectively.** Fund the services that remove proven free-tier and missing-process gaps. Do **not** fund duplicates or Firebase “because preferred.”

**Exact services to fund now:**

1. Render paid API (**≥ 1c-2g / $25**).  
2. Render paid Background Worker (**≥ 1c-2g**; **2c-4g** if client training is in scope).  
3. Durable storage: either Render disk on the **artifact-owning** host **or** S3/R2 bucket (preferred for two-service layout).  
4. Keep Supabase + Upstash; upgrade those only if quotas bind.  
5. GEE/OpenTopo if live AOI is a sold capability.

**Engineering still required before “operational ML platform”:**

- Checkpoint promotion onto durable storage.  
- Worker deploy + job proof.  
- Storage sharing strategy that matches Render’s disk limits (may include code for object-backed geological/training).  
- Live acquisition env if required.

**Do not charge / do not fund as blockers:**

- Rebuilding the FastAPI/ML app (already substantial).  
- Firebase Blaze or Firebase integration (not in product path).  
- Second Redis (Render Valkey) while Upstash works.  
- Scientific validation campaigns disguised as hosting (status remains `NOT_VALIDATED` until independent science completes).  
- Demo mode enablement (correctly forced off).

---

### 11. Final go/no-go decision

**NO-GO on “upgrade API only and call it production.”**

**GO on a sequenced paid package** only if the owner simultaneously commits to:

1. Paid API (≥ 2 GB RAM),  
2. Paid always-on worker,  
3. A **feasible** durable shared-storage plan (not “one Render disk for two services”),  
4. Promotion of a Stage 2.5 checkpoint onto that storage,  

…and accepts that **genuine assessments remain blocked** until step 4 is verified on `/api/v1/ready`.

Upgrading the API in isolation is a partial infrastructure improvement, not production ML readiness.

---

## Architecture options (Audit G)

### Option A — Render API + persistent disk; worker separate

| | |
|---|---|
| Paid services | API + disk + worker + Upstash + Supabase |
| Code changes | Minimal if worker only does queue/DB work **without** reading API-local files — **insufficient** for real training/assess artifacts |
| Env | Same Redis/Postgres; disk mount `/data/outputs` on **API only** |
| Storage sharing | **FAIL on Render** — disk not mountable by worker ([docs](https://render.com/docs/disks)) |
| Risks | Worker cannot see checkpoints/datasets; false sense of durability; docs that say “same disk” are wrong on Render |
| Pros | Fast durability for **API-local sync** assess if checkpoint lives on API disk and assess stays in-process |
| Cons | Breaks distributed training/async inference file access; no zero-downtime deploys with disk |
| Min recurring (list) | ~$25 API + ~$25–$85 worker + ~$5 disk + Upstash/Supabase |

**Verdict:** Acceptable only for **sync-assess-on-API** with checkpoint on API disk and **no** worker file dependency. Not a full ML platform.

### Option B — Render API + worker + shared external object storage

| | |
|---|---|
| Paid services | API + worker + R2/S3 (+ Supabase/Upstash); **no** Valkey; disk optional for scratch |
| Code changes | **Required** for geological + TrainingStorage/registry object backends; assess GeoTIFF already S3-capable |
| Env | `SSRI_OBJECT_STORAGE_BACKEND=s3` (+ bucket/keys); geological backend **cannot** be flipped today |
| Storage sharing | API and worker both use object API — **correct** for two services |
| Risks | Incomplete migration leaves hybrid FS/object inconsistency (explicitly called unsafe in `durable.py`) |
| Pros | Matches distributed mode; portable; no duplicate Redis |
| Cons | Engineering before geological/training cutover |
| Min recurring (list) | ~$25+$25–$85 compute + object storage usage + existing Supabase/Upstash |

**Verdict:** **Preferred target architecture.** Do not claim ready until geological/training object paths exist **or** a temporary single-host FS is used.

### Hybrid (cost-minimizing, valid FS share)

Run API+worker on **one** always-on host (Render private service with process supervisor, or a single VPS) with one disk at `/data/outputs`. Avoids Render’s cross-service disk limit. Trade-off: operational packaging work.

---

## Audit H — Production verification summary

| Endpoint / area | Method | Result | Status |
|---|---|---|---|
| `/api/v1/health` | Live GET | `ok` | VERIFIED |
| `/api/v1/ready` | Live GET | Infra ready; model not | VERIFIED |
| `/openapi.json` | Live GET | 67 paths; key routes present | VERIFIED |
| Authenticated assess/upload/train | — | Credentials not used (by design) | NOT_VERIFIED |
| Worker logs / Render dashboard worker | — | No access this pass | NOT_VERIFIED |
| Upstash URL equality across three env vars | — | Owner-stated; secrets not printed | PARTIALLY VERIFIED |
| Source routes assess/training/geological/registry/jobs | Code read | Present and wired | VERIFIED |

---

## 14. Git commit author and identity verification

### Inspected values

| Check | Actual value | Expected value | Status |
|---|---|---|---|
| Local Git username | `hazeez-edunjobi` | Intended GitHub user `hazeez-edunjobi` | PASS |
| Local Git email | `ifeoluwasuccess520@gmail.com` | Email verified on that GitHub account | PARTIALLY VERIFIED (local ok; GitHub email verification **NOT_VERIFIED** via API this pass) |
| Global Git username | `olaniyanp11` | Same as intended project identity | **FAIL / WARNING** — mismatches local |
| Global Git email | `olaniyanp11@gmail.com` | Same as intended | **FAIL / WARNING** — mismatches local |
| Latest commit author | `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>` (`d6e877a`) | Intended identity | PASS (local repo) |
| Latest commit committer | Same as author | Consistent | PASS |
| Recent commit consistency (last 10) | All `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>` | Consistent | PASS |
| Full-history email diversity | 135× `ifeoluwasuccess520@gmail.com`; 1× `113791070+hazeez-edunjobi@users.noreply.github.com` (`21535e6`, author name `edunjobi-hazeez`) | Prefer one verified email | PASS WITH WARNING |
| GitHub attribution | Cannot confirm which emails are verified on `hazeez-edunjobi` without GitHub account API | Linked to intended account | **NOT_VERIFIED** |
| Branch / upstream | `main` → `origin/main` @ `d6e877a` | Tracking main | PASS |

### Discrepancies

1. **Global vs local config:** Global `olaniyanp11` / `olaniyanp11@gmail.com` would attribute commits incorrectly on any clone/directory **without** repo-local `user.*`. Recent SSRI commits used local override — safe for this repo tip, risky for the next bare repo.  
2. **Historical noreply commit:** `21535e6` uses GitHub noreply for `hazeez-edunjobi` with display name `edunjobi-hazeez` — likely still attributes to the same GitHub user if noreply ID matches, but naming is inconsistent.  
3. **GitHub email verification** of `ifeoluwasuccess520@gmail.com` on account `hazeez-edunjobi`: **NOT_VERIFIED** independently here.

### Git identity verdict

**PASS WITH WARNING.**

Recent `main` commits are consistently authored/committed as `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>`. Global git config on this machine is a different identity and must be corrected **by the owner** (not executed in this audit) before relying on global defaults:

```text
# Recommended for the owner to run later (NOT executed by this audit):
git config --global user.name "hazeez-edunjobi"
git config --global user.email "ifeoluwasuccess520@gmail.com"
# Ensure that email is verified on the hazeez-edunjobi GitHub account.
```

Do **not** amend or rewrite history.

---

## Bottom line

Paid Render API upgrade is **necessary but far from sufficient**. The binding blockers are **missing promoted checkpoint**, **unverified worker**, and **filesystem durability that cannot be naively shared across Render services**. Firebase is an owner preference with **zero** current integration — not a billing unlock. Fund API + worker + one coherent storage plan; complete promotion and storage/worker proofs before calling SSRI a paid production ML platform.
