# SSRI — Master Completion Baseline

**Date:** 2026-11-21  
**Mode:** Phase Zero discovery (no source changes for this document’s production)  
**Branch / HEAD:** `main` @ `28908383555136d63dc7d15283472850e1a456c8` (even with `origin/main`)  
**Positioning:** SSRI — See the ground before you build.  

This baseline verifies repository reality. It does **not** treat passing tests as project completion.

---

## 1. Git and worktree state

| Item | Value |
|------|--------|
| Tracked modified | `PlatformShell.tsx`, `api/app.py`, `release_shell/validator.py`, `poc/.../inspect_client_csv.py` |
| Untracked (material) | Full geological package + FE `/geological`, geological tests/fixtures, geological docs/reports, Abeokuta prep/plans, `poc/release_shell/configs/`, assorted `poc/_tmp_*` probes |
| Staged | Empty |
| Commit/push of geological work | **Not done** (release process blocker) |

---

## 2. Authoritative subsystems

| Subsystem | Authority | Deprecated |
|-----------|-----------|------------|
| API | `model/src/ssri_model/api/app.py` → `/api/v1` | Root `api/` Stage-0 health-only |
| Worker | `ssri_model.worker` Celery `ssri.execute_job` | Root `worker/` scaffold |
| Model | `SSRIModel` + Stage 2.5 trainer; `CHANNEL_COUNT=13` | Foundation multitask ≠ assess path |
| Frontend | `frontend/` Next.js | — |
| Compose | `infra/docker-compose.yml` | — |
| Geological catalogue | `ssri_model.geological` + `/api/v1/geological/*` | Uncommitted locally |

---

## 3. Existing capabilities (evidenced)

### Software platform

- FastAPI app with health/ready, assess, inference, batch, jobs, auth keys, training, platform, geological, gated release-shell.
- Auth via `SSRI_AUTH_*` (defaults off in development; production gate can require on).
- Job types: `inference`, `batch`, `training` via Celery worker.
- Frontend routes: dashboard assess, workspace, training, geological catalogue UI, auth pages, platform/admin.
- Central API helpers: `lib/api.ts`, `platformApi.ts`, `geologicalApi.ts`.
- Geological catalogue: inspect/declare/validate/activate/coverage/offline apply; provenance ledger + lock; HTTP path confinement.
- Latest geological gate (local): backend 813/3 skip; FE typecheck/lint/31/build — **PASS WITH LIMITATIONS**.

### Scientific / ML (partial)

- Stage 2.5 13-channel contract (`ml/constants.py`, `architecture/config.py`, `inference/safety.py`).
- Schema v2 channel list defined (`release_shell/channel_schema.py`); offline apply can expand stacks to 16.
- Manual training + registry paths for `best.pt` under `{output_root}/training/`.
- Historical research scorecard (`docs/SSRI_COMPLETION_SCORECARD.md`, 2026-09-09): foundation work done; **AUC/ECE gates failed / not measured**.

### Ops docs

- Worker deploy notes, infrastructure readiness reports, production self-test reports present at repo root / `infra/`.

---

## 4. Partially implemented capabilities

| Area | Evidence | Gap |
|------|----------|-----|
| Geological system | Code + tests local | Uncommitted; `allow_direct_target_root` escape; POSIX lock untested on Windows gate; mid-apply crash before PASS report |
| Offline 16-ch stacks | `feature_apply` / geological apply | Not live inference; no evaluated v2 checkpoint |
| Assess offline C∈{13,16} | `assess.py` `_ALLOWED_FEATURE_CHANNEL_COUNTS` | Pre-existing; does not equal Phase 6 readiness |
| Platform v4 / Supabase | Platform routes + migrations | Multi-tenant geological ACL not aligned |
| Marketing / product copy | About / developers pages | Some SDK/API marketing may exceed implemented surface (AGENTS.md warning) |
| Scientific validation status | Always `NOT_VALIDATED` in geological/training paths | Correct honesty; not a “done” science product |

---

## 5. Missing capabilities (blockers for 100%)

### Scientific product (hard blockers)

1. **No in-repo `.pt` production checkpoint** (glob empty) — cannot verify deployed weights in git.
2. **No schema-tied, evaluated 16-channel production checkpoint** — Phase 6 **BLOCKED**.
3. **Client Abeokuta CSV** (`sheet 260_Abeokuta.csv`): CRS, Z meaning, units, negatives, gaps **unconfirmed** — cannot activate as scientific overburden (`SSRI_CLIENT_LINEAMENT_OVERBURDEN_DATA_AUDIT.md`).
4. **No client lineament vectors** on disk.
5. **Scorecard scientific gates** (source AUC/ECE, African transfer, DANN) **not met / not measured**.
6. Defensible v2 baselines, per-hazard spatial validation, calibration study for production promotion — **absent as release evidence**.

### Software / release process

7. Geological + related FE/API still **uncommitted** — cannot ship without user-approved commit/push/deploy.
8. No `vercel.json` / `render.yaml` in repo — deploy topology documented in prose/env examples only.
9. Valid-cell AOI coverage (vs bbox intersection) — deferred.
10. Multi-tenant geological ownership ACL — intentionally single-tenant.

### Ops / verification gaps

11. Live production E2E of geological UI against Render/Vercel with real auth — not re-proven in this session.
12. Linux POSIX lock / process-kill lock recovery — not proven on Windows host.

---

## 6. Broken or failed scientific gates (documented)

From `docs/SSRI_COMPLETION_SCORECARD.md` (verify before treating as current metrics):

- Source AUC ≥ 0.88 — **FAILED** (reported test tile 0.750).
- Source ECE ≤ 0.08 — **FAILED** (0.094).
- African transfer / DANN deltas — **NOT MEASURED**.
- Gravity EIGEN-6C4 raster — **missing** (WGM2012 labelled honestly).

These are research scorecard findings, not geological-catalogue defects.

---

## 7. Security / integrity risks

| Risk | Severity | Notes |
|------|----------|-------|
| Auth off by default in development | Expected | Production gate must keep auth on |
| Geological shared catalogue | Medium (multi-user) | Intentional single-tenant |
| `allow_direct_target_root` in-process | Low–Medium | HTTP confined; scripts can misuse |
| Large client CSV in worktree | Ops | Do not commit oversize/secrets; `.env` present locally — never commit |
| Offline assess accepting C=16 | Pre-existing | Must not load into 13-ch checkpoint (safety enforces model `in_channels`) |

---

## 8. Test coverage snapshot

| Suite | Last evidenced | Limitation |
|-------|----------------|------------|
| Full backend `poetry run pytest` | 813 passed, 3 skipped (geological final release gate) | Must re-run after further edits |
| Frontend | typecheck/lint/31/build pass | Few/no dedicated geological page unit tests |
| POSIX lock | Untested on Windows gate | Needs Linux CI |
| Live prod smoke | Prior self-test reports exist | Re-verify after deploy of geological |

---

## 9. Three completion axes (baseline estimates)

| Axis | Evidence-backed estimate | Primary remaining blockers |
|------|--------------------------|----------------------------|
| **Software engineering** | ~78–85% | Commit geological; escape-hatch hygiene; FE geological tests; docs sync; CI Linux lock |
| **Production release** | ~70–80% | User-approved commit/push/deploy; live smoke of geological; auth-on prod; env parity |
| **Scientific product** | ~35–45% | Client CRS/units; labels/checkpoints; v2 evaluation; scorecard gates; Phase 6 |

**Combined 100% is not honest today.** Scientific axis dominates the gap.

---

## 10. Priority order for execution (post-baseline)

1. Scientific integrity / data readiness documentation and keep Phase 6 blocked.  
2. Production correctness: confine escape hatch further; preserve 13-ch isolation.  
3. Core workflows: ensure geological + assess paths remain coherent.  
4. Model training/eval scaffolding only where data exists — no fabricated metrics.  
5. Reliability: CI Linux lock test; crash-consistency docs.  
6. UI polish / documentation accuracy.

---

## 11. User decisions required (cannot invent)

1. Approve commit of geological + related FE/API/tests/docs (file list review).  
2. Approve push / Render+Vercel deploy.  
3. Answer Abeokuta CSV questionnaire (CRS, Z meaning/units, negatives, gaps, permission).  
4. Provide or waive client lineament vectors.  
5. Supply or point to evaluated Stage 2.5 / future v2 checkpoints for production.  
6. Whether to fund schema-v2 training/eval compute and accept or reject v2 for live inference.

---

*Phase Zero complete. Implementation phases may proceed on software items that do not require fabricating science or activating Phase 6.*
