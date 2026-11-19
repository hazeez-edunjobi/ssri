# SSRI — Upload / Lineament / Overburden Integration Completion Report

**Date:** 2026-11-19  
**Branch:** `feature/upload-lineament-overburden-integration`  
**Starting tip:** `5f6fffd` (local main ahead of origin by report commit)  
**Deployment:** **not performed**

Scientific validation remains **NOT_VALIDATED**. Abeokuta CRS/units remain unconfirmed.

---

## 1–2. Baseline & branch

| Item | Value |
|------|-------|
| Start | `main` @ `5f6fffd` |
| Implementation branch | `feature/upload-lineament-overburden-integration` |
| Working tree at start | clean |

---

## 3. Files inspected / modified (summary)

**Upload:** `upload_limits.py`, `upload_io.py` (new), `ingest.py`, `api/routes/training.py`, `release_shell/routes.py`, frontend `lib/api.ts` + `shell/page.tsx`, tests.

**Lineaments / overburden:** `feature_apply.py` (new), `lineaments.py` (used), `validator.py`, `channel_schema.py` (existing), routes apply endpoints, shell UI, `FEATURE_SCHEMA_V2.md`, `UPLOAD_CAP_REPORT.md`.

---

## 4–5. Upload cap removal

| Before | After |
|--------|-------|
| Default `SSRI_UPLOAD_MAX_BYTES` = **1 GiB** | Default **unset = no application-level byte cap** |
| Hard reject above 1 GiB | Optional env backstop only when set |
| Full `await file.read()` into RAM | Disk spool via `spool_upload_to_temp` + `ingest_zip_path` |

**Safeguards retained / added:** path-traversal ZIP extract, ZIP bomb ratio, max uncompressed bytes (default 50 GiB), max ZIP files, optional row cap, content-type/zip magic checks.

**Proof above former 1 GiB default:** `reject_if_upload_too_large(1 GiB + ε)` and `reject_if_upload_too_large(2 GiB)` succeed when unset (`test_no_app_byte_cap_by_default`, `test_ingest_accepts_payload_above_former_1gib_when_unlimited`). Optional 1 GiB still enforceable when env set.

Frontend: XHR upload progress; no client-side arbitrary size reject.

**Not claimed:** “unlimited forever” — disk, proxy, and ZIP expansion guards still apply.

---

## 6. Lineaments

- Inspect (existing) + **apply** `POST .../datasets/{id}/lineaments/apply`
- Derives `lineament_density` / `lineament_distance` per tile from GeoJSON using documented window method
- Promotes v1 stacks → v2; updates manifest
- UI: CRS + inspect + apply

## 7. Overburden

- Validate with `measurement_type` + `units`
- Depth vs thickness contract (FAIL if depth claimed as `overburden_thickness`)
- **Apply** `POST .../datasets/{id}/overburden/apply` resamples thickness onto tiles
- No silent depth→thickness conversion

## 8. Feature schema

- v1 = 13, v2 = 16 (unchanged contract); apply paths rewrite to v2 explicitly
- Assess still rejects schema mismatch
- Docs: `poc/release_shell/FEATURE_SCHEMA_V2.md`

## 9. Backward compatibility

- Flag-off / v1 default unchanged
- Existing 13-channel datasets train/assess as before until apply promotes them
- Checkpoint schema mismatch still errors plainly

## 10–14. Tests

| Suite | Result |
|-------|--------|
| Focused upload/feature apply + hazard v2 | **30 passed** |
| Upload contract (flag ON) | **23 passed** |
| Full pytest flag OFF | **754 passed, 2 skipped** (integration gated) |
| Full pytest flag ON | **756 passed** (incl. live Postgres/Redis integration when env set) |
| Distributed integration alone | **2 passed** |
| `verify.py` | **pass** |
| Frontend typecheck / lint / test / build | **all pass** (20 unit tests) |

Evidence: `poc/release_shell/outputs/feature_integration_full_flag_{off,on}.txt`

Skipped without `SSRI_INTEGRATION_TESTS=1`: readiness + postgres job lifecycle (documented; executed green when enabled).

End-to-end: synthetic apply lineament/overburden + unlimited-byte proof via tests; full Playwright rehearsal not re-run this session (prior SYNTHETIC evidence remains on main).

## 15. Remaining limitations

- Multi-GB wall-clock upload not exercised as a single physical file in CI (byte-cap logic proven; disk/proxy still apply)
- Shapefile/GPKG lineament ingest not added (GeoJSON complete)
- Abeokuta / client CRS-units still client-owned
- Scientific skill **NOT_VALIDATED**
- No deployment performed

## 16–19. Git / push

| Item | Value |
|------|-------|
| Final local `main` | `4efdb6924fcc86bec8261eada4b9332eb2667214` |
| Final `origin/main` | `4efdb6924fcc86bec8261eada4b9332eb2667214` |
| Push | **Succeeded** (fast-forward `0c42929..4efdb69`) |
| Deployment | **None** |

Feature branch retained: `feature/upload-lineament-overburden-integration` (same tip).
