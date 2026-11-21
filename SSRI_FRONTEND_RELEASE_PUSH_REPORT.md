# SSRI — Frontend Release Push Report

**Date:** 2026-11-21  
**Scope:** Frontend-only commit + push to `origin/main`  
**Backend deploy:** Not authorized; not performed

---

## 1. Original Git baseline

| Field | Value |
|-------|-------|
| Branch | `main` |
| HEAD (pre-commit) | `d06878699f398a3b364a3ce48498c9cc0149786d` (Commit C) |
| Remote | `origin/main` at same SHA |
| Divergence | 0 ahead / 0 behind |
| Staged index | Empty before this operation |

Baseline matched expectations. Commit C preserved as parent.

---

## 2. Exact frontend files committed

| Path | Status |
|------|--------|
| `frontend/app/dashboard/page.tsx` | Modified |
| `frontend/app/page.tsx` | Modified |
| `frontend/app/shell/page.tsx` | Modified |
| `frontend/app/training/operator/page.tsx` | Modified |
| `frontend/components/product/ProductCapabilities.tsx` | Added |
| `frontend/e2e/dashboard.spec.ts` | Modified |
| `frontend/lib/api.ts` | Modified |
| `frontend/lib/assessRequest.ts` | Added |
| `frontend/lib/assessRequest.test.ts` | Added |
| `frontend/lib/productCapabilities.ts` | Added |
| `frontend/lib/productCapabilities.test.ts` | Added |

**11 files**, +592 / −38 lines.

`frontend/lib/api.auth.test.ts` was listed in the approved set but had **no working-tree changes** — not staged.

---

## 3. Tests and build results

Re-run from `frontend/` before commit:

| Command | Exit | Result |
|---------|------|--------|
| `npm run typecheck` | **0** | Pass |
| `npm run lint` | **0** | Pass |
| `npm test` | **0** | **46 passed**, 0 failed |
| `npm run build` | **0** | Pass |

---

## 4. Commit SHA and subject

| Field | Value |
|-------|-------|
| Subject | `Update SSRI assessment and geological capability UI` |
| Short SHA | `742aa6c` |
| Full SHA | `742aa6c5e8ff089f147713dcf2f0b82140f83129` |
| Parent | `d068786` (Commit C) |

---

## 5. Push result

```text
To https://github.com/hazeez-edunjobi/ssri.git
   d068786..742aa6c  main -> main
PUSH_EXIT=0
```

No force-push. No history rewrite.

---

## 6. Remote SHA verification

| Ref | SHA |
|-----|-----|
| Local `HEAD` | `742aa6c5e8ff089f147713dcf2f0b82140f83129` |
| Local `origin/main` | `742aa6c5e8ff089f147713dcf2f0b82140f83129` |
| `git ls-remote origin refs/heads/main` | `742aa6c5e8ff089f147713dcf2f0b82140f83129` |

Local `main`, `origin/main`, and remote tip are identical.

---

## 7. Vercel deployment evidence

| Field | Value |
|-------|-------|
| GitHub Deployment ID | `7961967357` |
| Environment | Production |
| Deployed SHA | `742aa6c5e8ff089f147713dcf2f0b82140f83129` |
| Created | 2026-11-21T10:17:32Z |
| Status | **success** (`Deployment has completed`) |
| Deployment URL | `https://ssri-p1rvvwgha-hazeez-edunjobi.vercel.app` |
| Production alias | `https://ssri-gamma.vercel.app` |

Deployed source SHA matches the pushed commit.

---

## 8. Production URL smoke-test results

| Check | Result |
|-------|--------|
| `https://ssri-gamma.vercel.app` | HTTP **200** |
| Subsidence / Landslide / Sinkhole | Present in HTML |
| Overburden / Lineament density / Distance to lineaments / Geological ingestion | Present |
| `NOT_VALIDATED` | Present |
| Live-inference-pending labels | Present |
| `https://ssri-gamma.vercel.app/dashboard` | HTTP **200** (client-rendered assess chrome; map shell loads) |

Assessment auth/error paths depend on the **current production API** (still Commit C-era backend until a separate API deploy). Frontend correctly uses Supabase bearer + omits empty checkpoint/model_id via `buildAssessRequestBody`.

---

## 9. Backend / unrelated exclusions confirmed

Staged index contained **only** the 11 frontend paths above.

**Preserved uncommitted (not pushed):**

- All `model/` Ruff, assess, training, health, and authorization changes
- `model/tests/test_assess_checkpoint_*.py`
- `poc/` temps and `inspect_client_csv.py`
- Client/Abeokuta docs and prior release reports
- `.env` / secrets

---

## 10. Remaining backend release blockers

1. Backend assessment resolution + checkpoint authorization still **uncommitted**.
2. Backend Ruff remediation still **uncommitted**.
3. `PRODUCTION_CHECKPOINT_VERIFICATION = NOT_VERIFIED` on Render.
4. No authorized API/worker deploy for this frontend push.
5. Full authenticated production assess smoke still pending after API deploy + promoted 13-channel checkpoint.

---

## Verdict

**Frontend release succeeded:** commit `742aa6c` is on `origin/main`, Vercel Production deployment `7961967357` is **success** for that SHA, and the live landing page shows the three hazards plus separate geological conditioning.
