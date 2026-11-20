# SSRI — Geological Acceptance Hardening Report

**Date:** 2026-11-20  
**Scope:** Close remaining acceptance gaps from `SSRI_GEOLOGICAL_FINAL_VERIFICATION_REPORT.md` (F2 pixel proof, F5 crash recovery, F5 concurrent ledger, F1 in-process path)  
**Baseline / final HEAD:** `28908383555136d63dc7d15283472850e1a456c8`  
**Phase 6:** remains **BLOCKED**  
**Commit / push / deploy:** not performed  

---

## 1. Executive summary

Acceptance hardening is complete locally:

| Gap | Result |
|-----|--------|
| F2 pixel-value integration | **Done** — mapped `Thickness_m` values (10/11/12) asserted at correct cells; `Notes` unused; uncovered offset tile = `FEATURE_NODATA`; 16 channels; overburden index 13 |
| F5 crash recovery | **Done** — durable PASS report + idempotent `recover_feature_applications_from_report`; FAIL reports never mark success |
| F5 concurrent ledger | **Done** — cross-platform `JsonlAppendLock`; concurrent append + duplicate-identity tests |
| F1 in-process path | **Done** — default requires registered `target_dataset_id`; `allow_direct_target_root=True` is the trusted escape hatch (API + tests only after confinement) |

Production 13-channel inference files untouched. Hazards (subsidence, landslide, sinkhole) unchanged. Live v2 inference not activated.

---

## 2. Exact files changed

| Path | Role |
|------|------|
| `model/src/ssri_model/geological/target.py` | **New** — `resolve_offline_apply_target` (moved out of API route to avoid cycles) |
| `model/src/ssri_model/geological/ledger_lock.py` | **New** — Windows `msvcrt` / POSIX `fcntl` exclusive lock |
| `model/src/ssri_model/geological/storage.py` | Locked append; identity dedup; `recover_feature_applications_from_report` |
| `model/src/ssri_model/geological/apply.py` | Path policy; `application_id`; atomic report write; ledger + reconcile |
| `model/src/ssri_model/api/routes/geological.py` | Import resolve from `target.py`; call apply with trusted root after resolve |
| `model/tests/test_geological_acceptance_hardening.py` | **New** — F1/F2/F5 hardening tests |
| `model/tests/test_geological_remediation.py` | `allow_direct_target_root=True`; import from `target` |
| `model/tests/test_geological_ingest.py` | `allow_direct_target_root=True` |
| `SSRI_GEOLOGICAL_ACCEPTANCE_HARDENING_REPORT.md` | This report |

**Not modified:** `assess.py`, `inference/safety.py`, `architecture/config.py`.

---

## 3. Implementation decisions

### F2 — Pixel-value test

Uses `nonstandard_headers.csv` with declare mapping `Easting_m` / `Northing_m` / `Thickness_m`. Tile geotransform aligns cell centres with those coordinates so nearest-neighbour sampling is deterministic. Asserts full 3×3 overburden band equals `[[10,11,12]]×3` rows, channel count 16, index 13, and a far-offset tile remains all `FEATURE_NODATA`.

### F5 — Crash recovery

Recoverable window: **PASS** `geological_apply_report.json` on disk, ledger incomplete.

- Assign `application_id` before mutations.
- After successful stack updates, **atomically** write the PASS report, then append ledger under lock.
- `recover_feature_applications_from_report` rebuilds missing ledger rows from that report only when `overall == PASS`.
- Identity `(application_id, geo_id, content_sha256, target_dataset_id)` prevents duplicate successful rows.
- Mid-apply crashes **before** a PASS report are **not** marked successful (no invented success).

Not a full transactional filesystem; no claim of ACID across processes/volumes.

### F5 — Concurrent appends

`JsonlAppendLock` on `feature_applications.lock` wraps read-dedup + append + flush. Platform-compatible local FS lock only (not distributed).

### F1 — In-process path

Default `apply_geological_to_offline_dataset` requires `target_dataset_id` and resolves via `TrainingStorage(storage.root.parent)`.  
`allow_direct_target_root=True` is the internal/trusted interface used by:

- HTTP handler **after** `resolve_offline_apply_target`
- Focused unit tests that intentionally use temp roots

Raw paths without the flag → `APPLY_TARGET_ID_REQUIRED`.

---

## 4. Pixel-level test evidence

Command:

```text
cd model
poetry run pytest tests/test_geological_acceptance_hardening.py::test_f2_pixel_values_use_thickness_not_notes -q --tb=short
```

Covered by the suite run below (passed). Evidence encoded in assertions:

- Mapping fields are exactly the three declared headers; `Notes` absent.
- Overburden band matches thickness values 10/11/12 at spatially correct cells.
- Offset tile band entirely `FEATURE_NODATA`.
- `stack.shape[0] == 16` and `CHANNEL_NAMES_V2.index("overburden_thickness") == 13`.

---

## 5. Crash recovery and concurrency test evidence

Working directory: `C:\Users\LENOVO\Documents\MrBusoye\ssri\model`

| Command | Exit | Result |
|---------|------|--------|
| `poetry run pytest tests/test_geological_acceptance_hardening.py tests/test_geological_remediation.py tests/test_geological_ingest.py -q --tb=short` | 0 | **34 passed, 1 skipped** |
| `poetry run pytest tests/test_feature_apply_and_upload_unlimited.py tests/test_assess_conditioning.py -q --tb=line` | 0 | **9 passed** |

Hardening-specific cases:

- `test_f5_crash_recovery_from_pass_report` — report without ledger → recover → status true; second recover adds 0 rows  
- `test_f5_incomplete_report_not_recovered_as_success` — FAIL report → recovered 0  
- `test_f5_concurrent_ledger_appends` — 8 parallel unique writes + 4 parallel duplicate identity → 8+1 valid JSON lines  

Skipped: existing F1 symlink OS-limited test in remediation suite.

**Full backend suite:** NOT RUN.

---

## 6. Remaining limitations

- Crash **after** partial stack mutation but **before** PASS report still cannot be auto-marked successful (by design).
- Ledger lock is local-filesystem only; not a network/distributed lock.
- `allow_direct_target_root` remains available to trusted callers — misuse in new scripts could bypass HTTP confinement (documented).
- Valid-cell AOI coverage, multi-tenant ACL, F6–F9 items remain out of scope.
- Phase 6 live 16-channel inference remains **BLOCKED**.

---

## 7. Production inference isolation

| Check | Status |
|-------|--------|
| `assess.py` diff vs HEAD | none |
| `inference/safety.py` diff vs HEAD | none |
| `architecture/config.py` diff vs HEAD | none |
| Live AOI acquisition ↔ geological catalogue | not wired |
| Hazards: subsidence / landslide / sinkhole | intact |
| `used_in_inference` on apply/ledger/recovery | forced `false` |
| Schema-v2 live inference | not activated; Phase 6 **BLOCKED** |

---

## 8. Git state

### Baseline (hardening start)

- Branch: `main` … `origin/main` (even)
- HEAD: `28908383555136d63dc7d15283472850e1a456c8`
- Existing geological implementation untracked/modified; preserved

### Final

- HEAD unchanged: `28908383555136d63dc7d15283472850e1a456c8`
- New/updated hardening files present (see §2); prior user work preserved
- Nothing staged; **no** commit, push, reset, rebase, amend, or deploy

Await approval before commit, push, or deployment.
