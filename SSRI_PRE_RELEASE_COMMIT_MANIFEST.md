# SSRI — Pre-Release Commit Manifest and Change Review

**Mode:** READ-ONLY  
**Date:** 2026-11-21  
**Branch:** `main`  
**HEAD:** `28908383555136d63dc7d15283472850e1a456c8`  
**Upstream:** `main...origin/main` (even: **0 ahead / 0 behind**)  
**Staged index:** empty (`git diff --cached --stat` empty)  
**Commit / push / deploy:** not authorised; none performed  

---

## Executive summary

The working tree contains a coherent **geological implementation release candidate** plus **unrelated/temporary** and **client-private** artifacts that must not be committed without separate approval.

| Gate check | Result |
|------------|--------|
| HTTP exposes `allow_direct_target_root`? | **No** — `ApplyBody` has no such field; `apply_offline` never passes the flag (defaults false; re-resolves by `target_dataset_id`) |
| Production 13-channel contract? | **Yes** — `assess.py` / `safety.py` / `architecture/config.py` **unchanged vs HEAD** |
| Phase 6 | Remains **BLOCKED** (docs + no v2 checkpoint) |
| Abeokuta CSV in commit? | **Must EXCLUDE** — ~10.1 MB client data; already `.gitignore`d |
| `.env` in commit? | **Must EXCLUDE** — gitignored; present locally (~3.5 KB) |

**Recommended split:** **two commits** (or one implementation + one docs), excluding temps/client/secrets. Unrelated tracked edits are all geological-related in this tree — no unrelated feature branch noise in the four modified tracked files.

---

## Proposed commit plan

### Commit A — Geological implementation (code + tests + FE)

INCLUDE all rows marked `INCLUDE — geological implementation` below.

### Commit B — Geological / completion documentation

INCLUDE rows marked `INCLUDE — required documentation` (and optionally Abeokuta *prep docs* that contain no raw client CSV).

### Do not commit

All `EXCLUDE — *` and most `REVIEW` until you decide.

---

## Tracked modifications (vs HEAD)

| Path | Size (approx) | Purpose | Classification | Reason |
|------|---------------|---------|----------------|--------|
| `frontend/components/platform/PlatformShell.tsx` | small (+7 lines) | Nav link + banner for `/geological` | **INCLUDE — geological implementation** | Required UI entry |
| `model/src/ssri_model/api/app.py` | small (+2 lines) | Mount `geological` router | **INCLUDE — geological implementation** | Required API wiring |
| `model/src/ssri_model/release_shell/validator.py` | small (+9 lines) | Pass XYZ column overrides into ingest | **INCLUDE — geological implementation** | F2 column mapping |
| `poc/release_shell/scripts/inspect_client_csv.py` | ~rewrite (−248/+40) | Delegates inspect to geological package; default path still Abeokuta candidate | **INCLUDE — geological implementation** *or* **SEPARATE** if you want POC tooling alone | Supports operator inspect; does not embed CSV bytes. Default path references gitignored client file. |

---

## Untracked — geological backend

| Path | Size | Purpose | Classification | Reason |
|------|------|---------|----------------|--------|
| `model/src/ssri_model/api/routes/geological.py` | 11 546 B | Geological HTTP API | **INCLUDE — geological implementation** | Core |
| `model/src/ssri_model/geological/__init__.py` | 373 B | Package | **INCLUDE — geological implementation** | Core |
| `model/src/ssri_model/geological/models.py` | 7 612 B | Catalogue records | **INCLUDE — geological implementation** | Core |
| `model/src/ssri_model/geological/storage.py` | 15 149 B | Storage + ledger | **INCLUDE — geological implementation** | Core |
| `model/src/ssri_model/geological/service.py` | 15 439 B | Orchestration | **INCLUDE — geological implementation** | Core |
| `model/src/ssri_model/geological/inspect.py` | 5 943 B | CSV inspect | **INCLUDE — geological implementation** | Core |
| `model/src/ssri_model/geological/validate.py` | 4 961 B | Validation | **INCLUDE — geological implementation** | Core |
| `model/src/ssri_model/geological/coverage.py` | 11 180 B | Bbox coverage | **INCLUDE — geological implementation** | Core |
| `model/src/ssri_model/geological/lineament_ingest.py` | 9 490 B | Lineament ingest | **INCLUDE — geological implementation** | Core |
| `model/src/ssri_model/geological/apply.py` | 12 642 B | Offline apply | **INCLUDE — geological implementation** | Core |
| `model/src/ssri_model/geological/target.py` | 2 255 B | Path resolve | **INCLUDE — geological implementation** | Core |
| `model/src/ssri_model/geological/ledger_lock.py` | 2 677 B | JSONL lock | **INCLUDE — geological implementation** | Core |
| `model/src/ssri_model/geological/__pycache__/**` | various | Bytecode | **EXCLUDE — temporary/debug artifact** | `.gitignore` `__pycache__/`; never stage |

---

## Untracked — geological frontend

| Path | Size | Purpose | Classification | Reason |
|------|------|---------|----------------|--------|
| `frontend/app/geological/page.tsx` | 11 373 B | Catalogue list / coverage UI | **INCLUDE — geological implementation** | Core |
| `frontend/app/geological/[id]/page.tsx` | 13 671 B | Dataset detail workflow | **INCLUDE — geological implementation** | Core |
| `frontend/lib/geologicalApi.ts` | 7 235 B | Central API client | **INCLUDE — geological implementation** | Core |

---

## Untracked — geological tests / synthetic fixtures

| Path | Size | Purpose | Classification | Reason |
|------|------|---------|----------------|--------|
| `model/tests/test_geological_ingest.py` | 16 379 B | Catalogue tests | **INCLUDE — geological implementation** | Required |
| `model/tests/test_geological_remediation.py` | 16 298 B | F1–F5 remediation tests | **INCLUDE — geological implementation** | Required |
| `model/tests/test_geological_acceptance_hardening.py` | 12 452 B | Pixel/lock/recovery tests | **INCLUDE — geological implementation** | Required |
| `model/tests/fixtures/geological/regular.csv` | 121 B | Synthetic | **INCLUDE — geological implementation** | Tiny synthetic |
| `model/tests/fixtures/geological/gapped.csv` | 83 B | Synthetic | **INCLUDE — geological implementation** | Tiny synthetic |
| `model/tests/fixtures/geological/irregular.csv` | 63 B | Synthetic | **INCLUDE — geological implementation** | Tiny synthetic |
| `model/tests/fixtures/geological/negative_thickness.csv` | 45 B | Synthetic | **INCLUDE — geological implementation** | Tiny synthetic |
| `model/tests/fixtures/geological/depth_candidate.csv` | 121 B | Synthetic | **INCLUDE — geological implementation** | Tiny synthetic |
| `model/tests/fixtures/geological/nonstandard_headers.csv` | 172 B | Synthetic mapped headers | **INCLUDE — geological implementation** | Tiny synthetic |
| `model/tests/fixtures/geological/lineaments.geojson` | 276 B | Synthetic vectors | **INCLUDE — geological implementation** | Tiny synthetic |

---

## Untracked — documentation (five completion reports + geological suite)

| Path | Size | Purpose | Classification | Reason |
|------|------|---------|----------------|--------|
| `SSRI_MASTER_COMPLETION_BASELINE.md` | 8 602 B | Phase 0 baseline | **INCLUDE — required documentation** | Completion pack |
| `SSRI_SCIENTIFIC_DATA_READINESS_REPORT.md` | 4 740 B | Data readiness | **INCLUDE — required documentation** | Completion pack |
| `SSRI_MODEL_SCIENTIFIC_VALIDATION_REPORT.md` | 3 022 B | Phase 6 blocked | **INCLUDE — required documentation** | Completion pack |
| `SSRI_PRODUCTION_SECURITY_AND_RELIABILITY_REPORT.md` | 2 993 B | Security review | **INCLUDE — required documentation** | Completion pack |
| `SSRI_FINAL_PROJECT_COMPLETION_REPORT.md` | 6 915 B | Final scores | **INCLUDE — required documentation** | Completion pack |
| `SSRI_GEOLOGICAL_CSV_INGESTION_ARCHITECTURE.md` | 21 075 B | Architecture | **INCLUDE — required documentation** | Geological design |
| `SSRI_GEOLOGICAL_PHASES_2_6_ACCEPTANCE_REPORT.md` | 9 129 B | Acceptance | **INCLUDE — required documentation** | Gate evidence |
| `SSRI_GEOLOGICAL_INDEPENDENT_AUDIT_REPORT.md` | 20 014 B | Independent audit | **INCLUDE — required documentation** | Gate evidence |
| `SSRI_GEOLOGICAL_REMEDIATION_REPORT.md` | 10 995 B | F1–F5 remediation | **INCLUDE — required documentation** | Gate evidence |
| `SSRI_GEOLOGICAL_FINAL_VERIFICATION_REPORT.md` | 12 066 B | Verification | **INCLUDE — required documentation** | Gate evidence |
| `SSRI_GEOLOGICAL_ACCEPTANCE_HARDENING_REPORT.md` | 7 221 B | Hardening | **INCLUDE — required documentation** | Gate evidence |
| `SSRI_GEOLOGICAL_FINAL_RELEASE_GATE_REPORT.md` | 7 955 B | Release gate | **INCLUDE — required documentation** | Gate evidence |
| `SSRI_PRE_RELEASE_COMMIT_MANIFEST.md` | (this file) | Commit review | **INCLUDE — required documentation** | Release process |
| `SSRI_LIVE_V2_CONDITIONING_INTEGRATION_PLAN.md` | 12 735 B | Future Phase 6 plan | **REVIEW** | Planning only; not runtime code — include in docs commit if you want history |
| `SSRI_ABEOKUTA_PROVISIONAL_INTEGRATION_PREP.md` | 7 504 B | Abeokuta prep (no raw CSV) | **REVIEW** | Safe text; references client file by name — confirm you want it public in git |
| `SSRI_CLIENT_LINEAMENT_OVERBURDEN_DATA_AUDIT.md` | 8 394 B | Client data audit | **REVIEW** | Describes client holdings; no CSV bytes — confirm publication |

---

## Client / private data and secrets

| Path | Size | Purpose | Classification | Reason |
|------|------|---------|----------------|--------|
| `sheet 260_Abeokuta.csv` | **10 143 316 B** | Client candidate geology | **EXCLUDE — client/private dataset** | Gitignored; do not force-add |
| `poc/release_shell/outputs/client_csv_inspect/260_abeokuta_COPY.csv` | ~10.1 MB | Working copy of client CSV | **EXCLUDE — client/private dataset** | Duplicate client data under outputs |
| `.env` | 3 565 B | Local secrets | **EXCLUDE — secret or environment file** | Gitignored |
| `.env.example` | 5 959 B | Template | Already tracked / not in dirty set | Keep as template only |
| `credentials/**` | — | Creds | **EXCLUDE — secret or environment file** | Gitignored pattern |

---

## Temporary / debug / POC probe artifacts

| Path | Purpose | Classification | Reason |
|------|---------|----------------|--------|
| `poc/_tmp_classify_redis_env.py` | Probe | **EXCLUDE — temporary/debug artifact** | `_tmp_` operator scratch |
| `poc/_tmp_conditioning_ui_fixture.html` | Probe | **EXCLUDE — temporary/debug artifact** | Scratch |
| `poc/_tmp_handover_assess.json` | Probe | **EXCLUDE — temporary/debug artifact** | Scratch |
| `poc/_tmp_handover_integration.txt` | Probe | **EXCLUDE — temporary/debug artifact** | Scratch |
| `poc/_tmp_handover_pytest.txt` | Probe | **EXCLUDE — temporary/debug artifact** | Scratch |
| `poc/_tmp_probe_dashboard_release.py` | Probe | **EXCLUDE — temporary/debug artifact** | Scratch |
| `poc/_tmp_probe_frontend_release.py` | Probe | **EXCLUDE — temporary/debug artifact** | Scratch |
| `poc/_tmp_probe_openapi_schemas.py` | Probe | **EXCLUDE — temporary/debug artifact** | Scratch |
| `poc/release_shell/configs/abeokuta_provisional.hypotheses.json` | Explicit **hypotheses only**; points at client paths | **REVIEW** / lean **EXCLUDE — client/private dataset** adjacency | Not production config; activation disabled; still client-context |

Other root `SSRI_*` / `ssri_*` reports already tracked or outside this dirty set are out of scope unless you expand the release.

---

## Exact proposed INCLUDE manifest (Commit A — code)

```text
frontend/components/platform/PlatformShell.tsx
frontend/app/geological/page.tsx
frontend/app/geological/[id]/page.tsx
frontend/lib/geologicalApi.ts
model/src/ssri_model/api/app.py
model/src/ssri_model/api/routes/geological.py
model/src/ssri_model/geological/__init__.py
model/src/ssri_model/geological/models.py
model/src/ssri_model/geological/storage.py
model/src/ssri_model/geological/service.py
model/src/ssri_model/geological/inspect.py
model/src/ssri_model/geological/validate.py
model/src/ssri_model/geological/coverage.py
model/src/ssri_model/geological/lineament_ingest.py
model/src/ssri_model/geological/apply.py
model/src/ssri_model/geological/target.py
model/src/ssri_model/geological/ledger_lock.py
model/src/ssri_model/release_shell/validator.py
model/tests/test_geological_ingest.py
model/tests/test_geological_remediation.py
model/tests/test_geological_acceptance_hardening.py
model/tests/fixtures/geological/
poc/release_shell/scripts/inspect_client_csv.py   # optional: confirm with you
```

## Exact proposed INCLUDE manifest (Commit B — docs)

```text
SSRI_MASTER_COMPLETION_BASELINE.md
SSRI_SCIENTIFIC_DATA_READINESS_REPORT.md
SSRI_MODEL_SCIENTIFIC_VALIDATION_REPORT.md
SSRI_PRODUCTION_SECURITY_AND_RELIABILITY_REPORT.md
SSRI_FINAL_PROJECT_COMPLETION_REPORT.md
SSRI_GEOLOGICAL_CSV_INGESTION_ARCHITECTURE.md
SSRI_GEOLOGICAL_PHASES_2_6_ACCEPTANCE_REPORT.md
SSRI_GEOLOGICAL_INDEPENDENT_AUDIT_REPORT.md
SSRI_GEOLOGICAL_REMEDIATION_REPORT.md
SSRI_GEOLOGICAL_FINAL_VERIFICATION_REPORT.md
SSRI_GEOLOGICAL_ACCEPTANCE_HARDENING_REPORT.md
SSRI_GEOLOGICAL_FINAL_RELEASE_GATE_REPORT.md
SSRI_PRE_RELEASE_COMMIT_MANIFEST.md
# optional after your OK:
# SSRI_LIVE_V2_CONDITIONING_INTEGRATION_PLAN.md
# SSRI_ABEOKUTA_PROVISIONAL_INTEGRATION_PREP.md
# SSRI_CLIENT_LINEAMENT_OVERBURDEN_DATA_AUDIT.md
```

---

## Safety verifications (this review)

### HTTP `allow_direct_target_root`

- `ApplyBody` fields: `geo_ids`, `target_dataset_id`, `target_dataset_root` (compat match only), `window_m` — **no** escape-hatch field.
- `apply_offline` calls `apply_geological_to_offline_dataset(...)` **without** `allow_direct_target_root=True` (default false).
- Path confinement via `resolve_offline_apply_target` then registered id.

### Production 13-channel

- No git diff on `assess.py`, `inference/safety.py`, `architecture/config.py`.
- Live acquisition remains separate from geological catalogue.

### Unrelated user work

- The four **tracked** dirty files are all geological-related.
- Untracked `poc/_tmp_*` and client CSV are **not** part of the geological product commit.
- No evidence of a second unrelated feature mixed into the same dirty tracked set.

---

## Decisions requiring your approval

1. **Authorise Commit A** (code/tests/FE) using the INCLUDE list above?  
2. **Authorise Commit B** (documentation pack)?  
3. Include `poc/release_shell/scripts/inspect_client_csv.py` in A, or leave POC separate?  
4. Include Abeokuta **docs** (`SSRI_ABEOKUTA_*`, `SSRI_CLIENT_*`, live-v2 plan) in B, or keep private?  
5. Confirm **never** force-add `sheet 260_Abeokuta.csv` / COPY / `.env`.  
6. Include or discard `poc/release_shell/configs/abeokuta_provisional.hypotheses.json`?  
7. After commits: authorise **push** and/or **deploy** separately?  
8. Preferred: **two commits** (A then B) vs single combined commit?

---

## Strict permissions confirmation

This review was **read-only**. No stage, commit, push, deploy, delete, move, source edit, or history rewrite was performed. Only this manifest file was created.
