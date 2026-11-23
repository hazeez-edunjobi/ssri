# SSRI — Geological Upload Durability Remediation Report

**Date:** 2026-11-21  
**Mode:** Implementation + local verification (no commit / push / deploy / production env changes)  
**Prior audit:** `SSRI_PRODUCTION_GEOLOGICAL_CSV_UPLOAD_VERIFICATION_REPORT.md`

---

## Required status (unchanged)

```text
Project engineering: COMPLETE (platform)
Scientific model validation: NOT_VALIDATED
Stage 2.5 data readiness: REAL FEATURES FOUND — LABEL ACQUISITION REQUIRED
Production promoted checkpoint: NOT_VERIFIED
Scientific production release: NOT QUALIFIED
```

Hazards remain **subsidence / landslide / sinkhole**. Live assess remains **13-channel**. Geological catalogue does **not** feed live inference scores.

---

## Distinction: implementation vs production persistence

| Layer | Status |
|-------|--------|
| Code/tests for upload auth, original download, atomic local writes, USER denial | **Implementation verified locally** |
| Production upload + SHA256 round-trip on Render | **NOT_VERIFIED** (no operator credentials / disk access this session) |
| Production filesystem durability after redeploy | **NOT_VERIFIED** — requires Render persistent disk at `SSRI_API_OUTPUT_ROOT` |
| Complete R2-backed geological catalogue | **Not implemented** — architectural gap documented and refused at runtime |

---

## 1. Architecture (Phase 1)

### Existing object storage

`ssri_model.storage.ObjectStorage` (local + S3/R2 via boto3) historically offered `put_bytes` / `signed_url` / `delete` for assess GeoTIFF artifacts. This remediation added **`get_bytes`** to the protocol and both backends.

### Why R2 alone cannot host the geological catalogue yet

`GeologicalStorage` requires:

| Capability | Filesystem today | Current ObjectStorage / R2 |
|------------|------------------|---------------------------|
| Original + working bytes | Yes | Partial (`put`/`get` now) |
| Atomic `dataset.json` | tmp → `replace` | No conditional write / CAS |
| `index.jsonl` append | Local file append | No safe distributed append |
| `feature_applications.jsonl` + lock | `JsonlAppendLock` (local FS only) | No distributed lock |
| Catalogue list | Directory scan | No `list_prefix` in protocol |
| `FileResponse` / offline apply | Local `Path` | Needs hydrate or streaming redesign |
| API + worker shared view | Shared mount | Shared bucket possible *after* full redesign |

**Rejected incomplete pattern:** originals in R2 + metadata/indexes on ephemeral Render disk.

`SSRI_GEOLOGICAL_STORAGE_BACKEND=r2|s3|minio|object` now raises `InvalidServiceConfigError` via `build_geological_storage()` with an explicit message. Default remains **filesystem**.

### Supported durable strategy (production)

1. Keep `GeologicalStorage` on **filesystem** under `{SSRI_API_OUTPUT_ROOT}/geological/`.  
2. Attach a **Render persistent disk** (or equivalent) mounted at the configured output root.  
3. Set the **same** `SSRI_API_OUTPUT_ROOT` on API and worker.  
4. Leave `SSRI_GEOLOGICAL_STORAGE_BACKEND` unset or `filesystem`.  
5. Treat assess `SSRI_OBJECT_STORAGE_*` R2 settings as **orthogonal** (GeoTIFF artifacts only) until a full object-backed catalogue ships.

### Local durability hardening shipped

- `write_bytes_atomic()` for original (and lineament working) bytes.  
- Metadata already used tmp → replace.  
- Routes construct storage through `build_geological_storage()`.

---

## 2. Authentication (Phase 2)

`frontend/lib/geologicalApi.ts` now mirrors the Stage 2.5 client:

1. `NEXT_PUBLIC_SSRI_API_KEY` (operator machine key) if set.  
2. Else Supabase session access token.

Backend RBAC unchanged:

- Mutations + original download: `MANAGE_GEOLOGICAL` (**OPERATOR** / **ADMIN** only).  
- List/get: `READ_STATUS` (includes **USER**).  
- Ordinary **USER** cannot upload/declare/validate/download original (**403**).

Clear 401 / 403 / 413 messaging via `geologicalHttpErrorMessage` (`geologicalErrors.ts`).

---

## 3. Original-file retrieval (Phase 3)

Detail page (`/geological/[id]`) adds **Download original file**, calling:

`GET /api/v1/geological/datasets/{geo_id}/original`

via `downloadGeologicalOriginal()`. Authorization preserved. Byte-for-byte equality covered by API tests (SHA256).

---

## 4. Upload UX (Phase 4)

- Multipart field remains **`file`**.  
- Progress via XHR `upload.onprogress`.  
- Success only after HTTP 2xx.  
- List refresh after upload.  
- Operator/admin permission copy on list + detail.  
- Size limit surfaced when `SSRI_UPLOAD_MAX_BYTES` triggers **413**.

---

## 5. Changed files

| Path | Change |
|------|--------|
| `model/src/ssri_model/storage/__init__.py` | `get_bytes` on protocol + Local/S3 backends |
| `model/src/ssri_model/geological/durable.py` | **New** — atomic write + refuse incomplete object backend |
| `model/src/ssri_model/geological/service.py` | Atomic original/working writes |
| `model/src/ssri_model/api/routes/geological.py` | `build_geological_storage` |
| `frontend/lib/geologicalApi.ts` | API-key fallback, errors, original download |
| `frontend/lib/geologicalErrors.ts` | **New** — shared HTTP error messages |
| `frontend/lib/geologicalApi.test.ts` | **New** — error messaging tests |
| `frontend/app/geological/page.tsx` | Operator permission copy |
| `frontend/app/geological/[id]/page.tsx` | Download original action |
| `model/tests/test_geological_upload_durability.py` | **New** — durability/auth/download tests |
| `model/tests/test_storage.py` | `get_bytes` coverage |

---

## 6. Tests executed

| Suite | Result |
|-------|--------|
| `pytest tests/test_geological_upload_durability.py tests/test_storage.py` (+ ingest original bytes) | **13 passed** |
| Frontend `npm test` (incl. `geologicalHttpErrorMessage`) | **61 passed** |
| `npm run typecheck` | **exit 0** |

Coverage includes: local FS atomic write, object `get_bytes`, R2 backend refusal, operator SHA256 upload/download round-trip, declare/validate, USER mutation denial, unauthenticated **401**, concurrent unique `geo_id` creation.

No client-private geological data used.

---

## 7. Environment variables

| Variable | Role |
|----------|------|
| `SSRI_API_OUTPUT_ROOT` | Catalogue root (`…/geological`); **must be durable in production** |
| `SSRI_GEOLOGICAL_STORAGE_BACKEND` | `filesystem` (default). `r2`/`s3`/… **refused** until full catalogue exists |
| `SSRI_UPLOAD_MAX_BYTES` | Optional app-level upload cap → **413** |
| `NEXT_PUBLIC_SSRI_API_KEY` | Optional browser operator key for geological mutations |
| `SSRI_OBJECT_STORAGE_*` | Assess/object artifacts only — **not** geological catalogue today |

Do **not** change production env in this remediation session (constraint obeyed).

---

## 8. Migration / rollout instructions

1. **Commit/push** these changes only after owner approval (not done here).  
2. On Render API (and worker): attach **persistent disk** at the same path as `SSRI_API_OUTPUT_ROOT` (e.g. `/data/outputs`).  
3. Confirm API and worker share that mount.  
4. Deploy API + frontend.  
5. As **operator/admin**, run the controlled synthetic upload from the prior verification report; compare SHA256 of downloaded original.  
6. Confirm `/geological` shows the dataset after refresh; do **not** activate for live inference.  
7. Only after disk durability is confirmed, claim `PERSISTENCE_AFTER_RESTART` / production upload verification.

### Future R2 catalogue (out of scope)

Would need: `list_prefix`, conditional metadata writes, distributed ledger lock (or Postgres ledger), hydrate/stream for `FileResponse` and offline apply, dual API/worker access tests. Do not ship a partial adapter.

---

## 9. Storage limitations (remaining)

- Production durability still depends on **ops** attaching a persistent volume.  
- Free Render without a disk remains ephemeral.  
- `JsonlAppendLock` is not cluster-safe across machines without shared FS.  
- Original write is atomic per file; index append is still append-only local JSONL.  
- Frontend download requires operator/admin; USER still blocked by design.

---

## 10. Confirmation

- No Git commit / push  
- No Render / Vercel deploy  
- No production env / registry / checkpoint changes  
- No training / promote  
- No client data upload  

---

*End of geological upload durability remediation report.*
