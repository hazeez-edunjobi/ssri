# SSRI — Production Geological CSV Upload Verification Audit

**Date:** 2026-11-21  
**Mode:** READ-ONLY verification (no Git, deploy, restart, env change, promote, or production data mutation)  
**Production API:** `https://ssri-api.onrender.com`  
**Frontend (reference):** `https://ssri-gamma.vercel.app` → `/geological`

---

## Executive verdicts

| Verdict key | Result |
|-------------|--------|
| `UPLOAD_IMPLEMENTATION` | **VERIFIED** |
| `PRODUCTION_UPLOAD` | **NOT_VERIFIED** |
| `FILE_STORAGE_LOCATION` | **NOT_VERIFIED** (pattern VERIFIED in code; live disk path inaccessible) |
| `PERSISTENCE_AFTER_RESTART` | **NOT_VERIFIED** |
| `API_WORKER_STORAGE_SHARING` | **NOT_VERIFIED** (Compose intent VERIFIED; Render Free disk sharing unconfirmed) |

**Controlled production upload test:** **not performed** — no operator/admin bearer token or Render disk access in this environment.

---

## 1. Frontend upload execution path

### Routes and client

| Layer | Path / symbol |
|-------|----------------|
| List + create/upload UI | `frontend/app/geological/page.tsx` |
| Detail (declare / validate / activate) | `frontend/app/geological/[id]/page.tsx` |
| API helpers | `frontend/lib/geologicalApi.ts` |
| API origin | `frontend/lib/env.ts` → `apiUrl` (prod default `https://ssri-api.onrender.com`) |
| Shell chrome | `frontend/components/platform/PlatformShell.tsx` (nav `/geological`) |

### Create & upload sequence (actual code)

1. User fills display name, asset kind (`point_grid_csv` default), optional source, selects file (`accept=".csv,text/csv"`).  
2. `onCreateAndUpload` → `createGeologicalDataset(...)` → `POST {apiUrl}/api/v1/geological/datasets` with JSON body and `Authorization: Bearer <Supabase access_token>` only (`geologicalApi.authHeader` — **no** `NEXT_PUBLIC_SSRI_API_KEY` fallback, unlike `frontend/lib/api.ts`).  
3. On success, reads `dataset.geo_id`.  
4. `uploadGeologicalFile(geoId, file, setProgress)` builds `FormData`, appends field name **`file`**, `XMLHttpRequest` `POST …/datasets/{geoId}/upload`, sets Bearer header, reports `upload.onprogress`.  
5. Success only after HTTP 2xx and JSON parse; errors show `error.message` from API body.  
6. UI success string: `Uploaded as {geoId}…`; then `listGeologicalDatasets` reload.

### Detail / refresh / download

- Detail loads `GET /datasets/{geoId}` on mount and after declare/validate.  
- Status shown: `validation_status`, `activation_status`, `scientific_validation_status` (defaults `NOT_VALIDATED`).  
- **No frontend helper or button** calls `GET /datasets/{geo_id}/original` — original download is API-only today.  
- Success is not claimed before the create/upload HTTP responses resolve.

### Auth implication for ordinary product users

Signed-in Supabase `user` profiles map to `Role.USER` (`READ_STATUS`, `READ_METADATA`, `RUN_ASSESS` only). They can **list/get** geological datasets if authenticated, but **cannot** create/upload/declare/validate/activate/download original (`MANAGE_GEOLOGICAL` required → **403** if authenticated without that permission). Operators/admins (or API keys with those permissions) can mutate.

---

## 2. Backend upload execution path

Router: `model/src/ssri_model/api/routes/geological.py` (prefix `/geological` under `/api/v1`).

| Step | Endpoint | Dependency | Service / storage |
|------|----------|------------|-------------------|
| Create shell | `POST /datasets` | `require_manage_geological` | `GeologicalService.create` → `GeologicalStorage.create_shell` |
| Upload | `POST /datasets/{geo_id}/upload` | `require_manage_geological` | `UploadFile` field `file` → `upload_csv` / `upload_lineament` |
| List | `GET /datasets` | `require_read_status` | `GeologicalStorage.list` |
| Get | `GET /datasets/{geo_id}` | `require_read_status` | `get` + inspect/validation + feature_application status |
| Original | `GET /datasets/{geo_id}/original` | `require_manage_geological` | `FileResponse` of original path |
| Declare | `POST /datasets/{geo_id}/declare` | `require_manage_geological` | `GeologicalService.declare` |
| Validate | `POST /datasets/{geo_id}/validate` | `require_manage_geological` | `validate` → `validate_declared_point_grid` / lineament validator |

### Upload CSV internals (`GeologicalService.upload_csv`)

1. `reject_if_upload_too_large(len(content))` — only if `SSRI_UPLOAD_MAX_BYTES` set; else no app-level byte cap.  
2. Reject wrong `asset_kind`; reject second original (`ORIGINAL_IMMUTABLE`).  
3. `safe_filename(filename)` — basename sanitize; path traversal blocked via geo_id regex + `resolve_under`.  
4. Write `{dataset_dir}/original/{safe}` via `write_bytes`.  
5. Copy to `{dataset_dir}/working/layer.csv`.  
6. `inspect_point_grid_bytes` → `working/inspect.json`.  
7. Persist `dataset.json` via temp file + `replace` (atomic metadata).  
8. Append event to `index.jsonl` (`uploaded` + sha256).  
9. Set `validation_status="inspected"`, `content_sha256`, relpaths.

Geological code does **not** call `build_object_storage_from_env` / S3/R2. Uploads are **local filesystem under `output_root`**. Postgres stores jobs/platform auth — **not** geological CSV bytes.

OpenAPI on production lists all nine geological paths (live surface present).

---

## 3. Exact storage destination pattern

### How `SSRI_API_OUTPUT_ROOT` is resolved

`APIConfig.from_env(prefix="SSRI_API_")` →  
`output_root = os.getenv("SSRI_API_OUTPUT_ROOT", "outputs/service")`  
(`model/src/ssri_model/api/config.py`).

`GeologicalStorage(output_root)` →  
`self.root = Path(output_root).resolve() / "geological"`.

### Expected path pattern (code + Compose/docs)

```text
{SSRI_API_OUTPUT_ROOT}/geological/
  index.jsonl
  feature_applications.jsonl
  feature_applications.lock
  datasets/
    geo_{12hex}/
      dataset.json                 # metadata (atomic tmp→replace)
      original/{safe_filename}     # immutable original bytes
      working/layer.csv            # working copy for CSV
      working/inspect.json
      working/validate.json        # after validate
```

Compose / worker example: `SSRI_API_OUTPUT_ROOT=/data/outputs`  
→ expected originals: `/data/outputs/geological/datasets/geo_*/original/*`

Paths in records are **relative** (`original/…`, `working/…`); storage resolves them under the dataset directory with jail checks.

### Actual verified production path

**NOT_VERIFIED.** Render shell / disk console / `RENDER_API_KEY` unavailable this session. Ready payload confirms postgres/redis/queue only — **does not expose** `output_root` or mount info.

---

## 4. Effective production output-root evidence

| Probe | Result |
|-------|--------|
| `GET /api/v1/health` | **200** `status=ok` |
| `GET /api/v1/ready` | **200** distributed ready (postgres, redis, queue) |
| `GET /api/v1/geological/datasets` (no auth) | **401** `AUTHENTICATION_REQUIRED` |
| `POST /api/v1/geological/datasets` (no auth) | **401** `AUTHENTICATION_REQUIRED` |
| OpenAPI geological paths | Present (9 routes) |
| Operator/admin bearer in agent env | **Absent** |
| Render persistent disk inspection | **Unavailable** |

Intended env name from repo: `SSRI_API_OUTPUT_ROOT` (example `/data/outputs`). Live value not printed (and not readable without host access).

---

## 5. Render storage durability verdict

| Question | Finding |
|----------|---------|
| Persistent disk configured in repo? | **No** `render.yaml` in repo; only `infra/render-worker.env.example` + prose (`WORKER_PRODUCTION_DEPLOY.md` says attach same persistent disk / object storage as API) |
| Geological uses object storage? | **No** — filesystem only under `GeologicalStorage` |
| Ephemeral vs durable on Render Free? | **NOT_VERIFIED** — Free instances commonly use ephemeral FS unless a paid disk is attached; cannot confirm attachment |
| Survive process restart? | Survives **if** `output_root` is on durable storage; otherwise lost — **NOT_VERIFIED** |
| Survive redeploy / instance replace? | Same — **NOT_VERIFIED** |
| HTTP 200 upload as persistence proof? | **Invalid** — success only proves write to the current instance FS |

**`PERSISTENCE_AFTER_RESTART`: NOT_VERIFIED**

---

## 6. API / worker shared-storage verdict

| Evidence | Status |
|----------|--------|
| Compose: API + worker both `SSRI_API_OUTPUT_ROOT=/data/outputs` on volume `ssri_data` | **VERIFIED** (local Compose contract) |
| Docs: worker root “must match API artifact root / volume” | **VERIFIED** as intent |
| Production Render API + worker share one disk | **NOT_VERIFIED** (no console access) |
| Geological catalogue used by worker jobs? | Offline apply / training targets may need same root; upload itself is API-local FS |

**`API_WORKER_STORAGE_SHARING`: NOT_VERIFIED** for production; Compose intent verified.

---

## 7. Authentication and permission requirements

| Operation | Permission | Unauthenticated | Authenticated without permission |
|-----------|------------|-----------------|----------------------------------|
| List / get / coverage | `READ_STATUS` | **401** | **403** |
| Create / upload / declare / validate / activation / original / offline apply | `MANAGE_GEOLOGICAL` | **401** | **403** |

Roles with `MANAGE_GEOLOGICAL`: **OPERATOR**, **ADMIN** only (`auth/authorization.py`).  
`Role.USER` (ordinary signed-in product user): **cannot** upload.

Other error codes (from implementation):

| Situation | Typical status / code |
|-----------|----------------------|
| Upload too large (`SSRI_UPLOAD_MAX_BYTES`) | **413** `UPLOAD_TOO_LARGE` |
| Bad CSV / declare / validate business rules | **400** (+ validation FAIL may return **400** with report) |
| Missing dataset | **404** |
| Wrong asset kind / immutable original | **400** |
| Unsupported media type | No dedicated **415** — rejected as **400** / inspect failure |
| Auth required | **401** `AUTHENTICATION_REQUIRED` |
| Permission denied | **403** (AuthorizationError) |
| Server / disk write failure | Possible **5xx** (not exercised) |

Production auth is **enabled** (unauthenticated create/list → 401).

---

## 8. Controlled test details (not executed)

**Not performed.** No production credentials in the agent environment. Do not fabricate success.

### Operator commands (secrets via env only)

```bash
# Requires MANAGE_GEOLOGICAL (operator/admin API key or Supabase JWT for operator/admin profile)
export SSRI_BEARER="…"   # do not echo
export API="https://ssri-api.onrender.com/api/v1"

# Synthetic CSV — no client data
cat > /tmp/ssri_upload_verification_test.csv <<'CSV'
X,Y,Z
100.0,200.0,12.5
200.0,200.0,13.0
100.0,300.0,11.5
CSV
sha256sum /tmp/ssri_upload_verification_test.csv

# 1 Create
curl -sS -X POST "$API/geological/datasets" \
  -H "Authorization: Bearer $SSRI_BEARER" -H "Content-Type: application/json" \
  -d '{"display_name":"SSRI_UPLOAD_VERIFICATION_TEST","asset_kind":"point_grid_csv","source_client":"upload_verification"}'

# 2 Upload (multipart field name MUST be file)
GEO_ID=geo_…   # from create response
curl -sS -X POST "$API/geological/datasets/$GEO_ID/upload" \
  -H "Authorization: Bearer $SSRI_BEARER" \
  -F "file=@/tmp/ssri_upload_verification_test.csv;type=text/csv"

# 3 Metadata
curl -sS -H "Authorization: Bearer $SSRI_BEARER" \
  "$API/geological/datasets/$GEO_ID"

# 4 Download original + SHA256 compare
curl -sS -H "Authorization: Bearer $SSRI_BEARER" \
  -o /tmp/ssri_upload_verification_downloaded.csv \
  "$API/geological/datasets/$GEO_ID/original"
sha256sum /tmp/ssri_upload_verification_test.csv /tmp/ssri_upload_verification_downloaded.csv

# 5 Declare
curl -sS -X POST "$API/geological/datasets/$GEO_ID/declare" \
  -H "Authorization: Bearer $SSRI_BEARER" -H "Content-Type: application/json" \
  -d '{"measurement_type":"overburden_thickness","crs":"EPSG:32631","units":"m","x_column":"X","y_column":"Y","z_column":"Z"}'
  

# 6 Validate
curl -sS -X POST "$API/geological/datasets/$GEO_ID/validate" \
  -H "Authorization: Bearer $SSRI_BEARER"

# Do NOT activate for inference; leave inactive / reporting_only only if testing catalogue UX.
```

Afterward: open `/geological` and `/geological/{geo_id}` signed in as operator/admin; confirm list + inspect + validation UI. Confirm SHA256 match for original download.

---

## 9. Original-file retrieval result

| Check | Result |
|-------|--------|
| API route implemented | **Yes** — `GET …/original` → `FileResponse` |
| Frontend download UX | **Missing** — no client call |
| Production SHA256 round-trip | **NOT_VERIFIED** (no authenticated test) |

---

## 10. Validation result

| Check | Result |
|-------|--------|
| Server path | `GeologicalService.validate` → `validate_declared_point_grid` / lineament validator |
| Requires | Original on disk + declared CRS (+ measurement_type for CSV) |
| Writes | `working/validate.json`; sets `validation_status` `validated` or `failed` |
| Scientific status | Remains `NOT_VALIDATED` on record |
| Production validate exercised | **NOT_VERIFIED** |

---

## 11. Frontend refresh / reload result

| Check | Code evidence | Production UI |
|-------|---------------|---------------|
| Post-upload list refresh | `reload(0)` after successful upload | **NOT_VERIFIED** live |
| Detail remount loads server state | `useEffect` → `getGeologicalDataset` | **NOT_VERIFIED** live |
| Status labels | validation · activation · scientific | Present in UI copy |
| Success before server confirm | No — awaits HTTP | **VERIFIED** in source |

---

## 12. Assessment error — separate investigation

Dashboard / assess message:

> `No valid production checkpoint is configured.`

| Claim | Evidence |
|-------|----------|
| Independent of geological CSV upload | **Yes** — assess resolver uses training `ModelRegistry` / active checkpoint under `{output_root}/training/…` (`assess.py`); no `GeologicalStorage` import in assess route |
| Geological catalogue feeds live 13-ch scores? | **No** — UI and apply paths state offline / not live inference; `used_in_inference` forced false in provenance |
| Hazards unchanged | Subsidence, landslide, sinkhole preserved |
| This audit changed checkpoint resolution | **No** |

Production promoted checkpoint remains **`NOT_VERIFIED`** (prior audits).

---

## Outstanding risks and recommended remediation

1. **Durability:** Confirm on Render whether a **persistent disk** is mounted at the configured `SSRI_API_OUTPUT_ROOT`. Without it, geological uploads (and training registries) are lost on redeploy.  
2. **Shared root:** Confirm API and worker use the **same** mount if offline apply / jobs must see catalogue files.  
3. **Authorization UX:** Ordinary signed-in users hitting Create & upload will get **403**; UI should surface role requirements. Geological client should optionally align with `api.ts` API-key fallback for operator machine keys.  
4. **Original download UX:** Add authenticated download using `GET …/original` or document API-only access.  
5. **Atomic originals:** Metadata is atomic; original `write_bytes` is not temp+rename — small crash window mid-write.  
6. **Run controlled test** with operator credentials (commands above); compare SHA256; leave test dataset **inactive**.  
7. Do not treat upload success as scientific validation or as a fix for the missing production checkpoint.

---

## Confirmation of non-mutation

- No Git commit / push / history rewrite  
- No Render / Vercel deploy or restart  
- No env / registry / checkpoint changes  
- No production dataset create/upload (credentials absent)  
- No activation of geological layers for inference  

---

*End of geological CSV upload verification report.*
