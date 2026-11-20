# SSRI — Production Security and Reliability Report

**Date:** 2026-11-21  
**Mode:** Focused code/architecture review + local test evidence  
**Does not claim:** penetration test, load test at scale, or distributed FS lock certification  

---

## Scope

Reviewed authoritative stack under `model/src/ssri_model/` and `frontend/` for geological + core API risk areas. No credential values inspected or logged.

---

## Findings

| ID | Area | Severity | Status |
|----|------|----------|--------|
| S1 | Auth defaults off in development | Info / ops | By design; `production_gate` can require `SSRI_AUTH_ENABLED` |
| S2 | Geological single-tenant catalogue | Medium if multi-user | Documented; role gates still apply |
| S3 | HTTP offline apply path confinement | Mitigated | Resolves via registered `target_dataset_id`; no client `allow_direct_target_root` |
| S4 | In-process `allow_direct_target_root` | Low | Tests/scripts only; misuse possible |
| S5 | Upload size limits | Present | `reject_if_upload_too_large` |
| S6 | Path traversal on geo_id / zip | Mitigated | `resolve_under`, zip `..` checks |
| S7 | JSONL ledger lock | Local FS only | Concurrent test on Windows; Linux via CI once committed |
| S8 | Secrets in repo | Critical if committed | `.env` must stay gitignored; never commit |
| S9 | Error leakage | Partial | Operator-facing messages; stack traces should stay in logs |
| S10 | Assess offline C=16 | Pre-existing | Safety still enforces model channel count |

No SQL injection surface found in geological JSON/file catalogue (filesystem + JSON metadata, not SQL). Platform/Supabase paths rely on Supabase client patterns — treat as separate tenancy review.

---

## Reliability

| Topic | Observation |
|-------|-------------|
| Health / ready | `/health`, `/api/v1/ready` with infra probes |
| Jobs | Celery `ssri.execute_job`; types inference/batch/training |
| Redis failure | Documented in infra readiness reports — re-verify on deploy |
| Geological crash window | Partial stack write before PASS report ≠ success; recover from PASS report only |
| Worker restart | Compose/worker docs exist; not re-load-tested here |

**Performance:** No new AOI latency/memory campaign in this pass. Do not claim scalability from unit tests alone.

---

## Recommendations (ops)

1. Keep production auth enabled; disable development principal.  
2. Commit geological work only after file review (exclude `.env`, large client CSV if policy requires).  
3. Run Ubuntu CI (already in `.github/workflows/ci.yml`) after push to exercise POSIX locks.  
4. Smoke `/api/v1/ready`, assess, and geological list after deploy.  
5. Do not enable Phase 6 until scientific gate passes.

---

## Verdict

**Acceptable for continued research / Stage 2.5 ops with known limitations**, contingent on auth-on production, secret hygiene, and Phase 6 remaining blocked. **Not** a substitute for a formal external security audit.
