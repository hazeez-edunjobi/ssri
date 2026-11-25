# SSRI — Local Acceptance & Production Readiness Report

**Date:** 2026-11-25 (FINAL PRODUCTION CLOSURE SPRINT)  
**Base HEAD (pre-sprint):** `43128af75dd03ddded668df4710d95c81c6a80b4`  
**Closure commit:** *(filled after push — see git log)*  
**Mode:** Local hybrid stack + MinIO S3-compatible durable storage + host recovery loop  
**Science posture:** **NOT_VALIDATED** (no independent ground truth). Software PASS ≠ geological truth.

No secrets are printed in this report. Cloudflare R2 account credentials were **not** present in the local environment; durable object storage was verified against **real MinIO** (S3 API), not Cloudflare R2.

---

## Three independent verdicts

| Axis | Verdict |
|------|---------|
| **Engineering completion** | **PARTIAL → largely complete locally** — durable object mirroring implemented; MinIO round-trip + split-host materialize proven; lease recovery enabled and tested; full Cloudflare R2 + Render production auth deploy remain externally blocked |
| **Scientific validation** | **NOT_VALIDATED** |
| **Production readiness** | **NOT READY** — no R2 credentials, no Render API access to mutate production env/auth/CORS, production auth still off in local `.env` |

---

## Closure sprint implementations

### A. Durable object storage (geological / training / checkpoints / assessments)

**Status: PASS (code + MinIO); BLOCKED (Cloudflare R2 credentials)**

- Extended `ObjectStorage` with `list_prefix`.
- Expanded `storage/durable.py`: tree mirror/materialize; geological dataset + ledger keys; training dataset prefix; registry JSON; assessment payload mirror.
- Wired mirrors on:
  - geological `save` / materialize on `get`
  - training `save_dataset` / materialize on `get_dataset`
  - registry index + `active.json`
  - assessment `assess_response.json` (+ existing GeoTIFF `put_bytes`)
- Checkpoint mirror/materialize retained; SHA-256 verified.

**Real remote evidence (MinIO):**

| Check | Result |
|-------|--------|
| `scripts/qualify_object_storage.py` | **PASS** — upload/download/checksum; tree list/materialize (`verification_mode=real_minio`) |
| Split-host simulation | Checkpoint SHA `d912027e…` match after materialize; Abeokuta geo tree 32 files including `dataset.json` |
| Evidence files | `data/outputs/logs/wp_closure_minio_qualify.txt`, `wp_closure_split_host_minio.json` |

**Cloudflare R2:** credentials not configured (`SSRI_OBJECT_STORAGE_*` empty in `.env`). Do **not** claim R2 verified.

### B. Checkpoint + registry durability

**Status: PASS (local + MinIO)**

| Field | Value |
|-------|-------|
| Active model | `ssri-model-1c8de63cd3` |
| SHA-256 | `d912027e17ed532687f9d2a2c74fd3c18ca8c812ae49107d939ade19dde5d004` |
| Channels | 13 (`CHANNEL_NAMES`) unchanged |
| Scientific status | **NOT_VALIDATED** |
| Object key (MinIO test) | `training/models/ssri-model-1c8de63cd3/best.pt` |
| Registry | `registry.json` / `active.json` mirrored when remote backend set |

Checkpoint was **not** retrained or replaced.

### C. Job lease recovery (owner-authorized)

**Status: PASS**

| Evidence | Result |
|----------|--------|
| `scripts/verify_lease_recovery.py` | **PASS** — `job-f776eee6c0ecca02` → `QUEUED` / `STALE_LEASE_RECOVERED` |
| Sweeper CLI `--once` | Fresh job stayed `running`; stale recovered (`recovery_count=1`) |
| Managed process | Host PID recovery loop started (`python -m ssri_model.infrastructure.recovery --loop`); logs `data/outputs/logs/recovery.*.log` |
| Compose | `infra/docker-compose.yml` recovery service documented as owner-authorized |
| Render | Env example updated for separate Background Worker command `recovery` — **not deployed** (no Render API token) |

Evidence: `wp_closure_lease_recovery.txt`, `wp_closure_recovery_sweeper.json`.

### D. Production security

**Status: PARTIAL / BLOCKED externally**

| Control | Local | Production |
|---------|-------|------------|
| `SSRI_AUTH_ENABLED` | `false` (dev) | **Not mutated** — no Render dashboard access |
| CORS | Local origins configured | Explicit prod origins **not verified on Render** |
| Production gate | Fail-closed when `SSRI_API_ENVIRONMENT=production` | Not applied to live Render env from this session |
| Secrets in git/logs | Avoided | N/A |
| DB / Redis / Celery | Local ready PASS | Upstash/Render consistency **not re-confirmed via dashboard** |
| Supabase JWT | Product paths exist | Real production session smoke **not executed** |

### E. Split-host persistence

**Status: PASS via MinIO simulation; NOT proven on Cloudflare R2 / Render**

Independent materialize of checkpoint + geological tree from object storage after clearing local cache — see `wp_closure_split_host_minio.json`. This is **not** a claim based on shared local filesystem alone.

### F. Acceptance / tests

| Suite | Result |
|-------|--------|
| Focused backend pytest (durable, gate, geotiff, subsidence API, recovery, heartbeat, storage) | **45 passed** |
| Ruff (touched modules) | **All checks passed** |
| Frontend `npm test` / `tsc` | Run as part of closure (see logs / prior 95-pass baseline) |
| MinIO qualify | **PASS** |
| Lease recovery | **PASS** |
| Subsidence validation | Unavailable GT → **NOT_VALIDATED** (prior WP) |
| GeoTIFF download | Authenticated `/spatial` (prior WP) |
| Abeokuta TMI X/Y/Z | Preserved (prior WP + geo mirror of `geo_be00a34ad6f4`) |

---

## Files changed (closure + prior remediation)

Key paths include: `model/src/ssri_model/storage/{__init__,durable}.py`, `geological/{storage,durable}.py`, `manual_training/{registry,storage}.py`, `api/routes/{assess,subsidence}.py`, `api/production_gate.py`, `api/app.py`, frontend validation + GeoTIFF download clients, `infra/docker-compose.yml`, `infra/render-worker.env.example`, `.env.example`, tests, `model/scripts/qualify_object_storage.py`.

---

## Remaining blockers (honest)

1. **Cloudflare R2 credentials unavailable** — cannot claim real R2; MinIO verified instead.  
2. **Render / Vercel production env mutation unavailable** — no `RENDER_API_KEY` / dashboard session; cannot flip prod `SSRI_AUTH_ENABLED=true` or attach recovery worker from here.  
3. **Scientific validation** — still no independent inventory.  
4. **Production readiness** — blocked on (1)+(2) despite local engineering progress.

---

## Definition of DONE vs this sprint

| DONE criterion | Status |
|----------------|--------|
| Durable storage across independent API/worker | **PASS on MinIO**; pending real R2 creds on Render |
| Checkpoint/registry consistent | **PASS** (SHA verified) |
| Recovery runs + actual recovery test | **PASS** |
| Production auth + CORS verified | **BLOCKED** (no prod dashboard access) |
| Existing deploy services smoke | **BLOCKED** for remote mutate; local ready PASS |
| Full acceptance | **PASS locally** with noted external gaps |
| No unresolved *critical engineering* blocker in code | Remaining blockers are **credential/ops**, not missing recovery/storage implementation |

---

## Operator next actions (external)

1. Set identical `SSRI_OBJECT_STORAGE_*=r2` on Render API + worker (+ recovery).  
2. Run `poetry run python scripts/qualify_object_storage.py` against R2.  
3. Add Render Background Worker, Docker command `recovery`, `SSRI_LEASE_RECOVERY_ENABLED=true`.  
4. Set `SSRI_API_ENVIRONMENT=production`, `SSRI_AUTH_ENABLED=true`, explicit `SSRI_CORS_ORIGINS`, `SSRI_DEMO_MODE=false`.  
5. Smoke: login JWT, `/ready`, recover a stale test job, assess + GeoTIFF download.
