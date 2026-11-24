# SSRI — Targeted Frontend Remediation Report

**Date:** 2026-11-24  
**Mode:** Local implementation + verification (no commit, no push, no deploy)  
**Baseline HEAD:** `44558779ffe93a0f2a3d151e8f0a9d309f7e8753` (`main`)  
**Scope:** Audit findings F-01, F-03, F-04 only  
**Abeokuta evidence:** preserved (unchanged)

---

## Findings addressed

| ID | Finding | Resolution |
|---|---|---|
| **F-01** | Marketing pages implied live `/v1/hazard` / SDK packages | `/developers` and `/platform` now advertise `POST /api/v1/assess` as live; `/v1/hazard`, SDKs, and `/v1/assessments` are labelled roadmap / not shipped |
| **F-03** | `/training/operator` and `/shell` had no UI session/operator gate | Both wrapped in `RequireOperatorAccess` (local acceptance, operator API key, or platform `admin`) |
| **F-04** | `/admin` relied only on API 403 | Wrapped in `RequireAdminAccess` (session + `role === admin` only; local acceptance does **not** grant admin) |

---

## Files changed

### New

| Path | Role |
|---|---|
| `frontend/lib/marketingApiCopy.ts` | Shared accurate available / roadmap API copy |
| `frontend/lib/marketingApiCopy.test.ts` | Marketing accuracy tests |
| `frontend/lib/operatorAccess.ts` | Client operator/admin access helpers |
| `frontend/lib/operatorAccess.test.ts` | Access-gate unit + wiring tests |
| `frontend/components/auth/RequireOperatorAccess.tsx` | Operator UI gate |
| `frontend/components/auth/RequireAdminAccess.tsx` | Admin UI gate |

### Modified

| Path | Change |
|---|---|
| `frontend/app/developers/page.tsx` | Live assess example + available / roadmap sections |
| `frontend/app/platform/page.tsx` | Same copy model; removed fictional live endpoint list |
| `frontend/app/training/operator/page.tsx` | `RequireOperatorAccess` wrapper |
| `frontend/app/shell/page.tsx` | `RequireOperatorAccess` wrapper; keeps `SSRI_RELEASE_SHELL` UX |
| `frontend/app/admin/page.tsx` | `RequireAdminAccess` wrapper |

**Not modified:** backend APIs, migrations, checkpoints, inference architecture, CORS, Abeokuta evidence artifacts.

---

## Implementation details

### F-01 — Marketing / API accuracy

- Canonical live route: **`POST /api/v1/assess`**
- Available list also includes real readiness/training-active helpers under `/api/v1`
- Explicit roadmap items: public `GET /v1/hazard`, `pip install ssri-python` / `@ssri/sdk`, `POST/GET /v1/assessments`
- Visual layout (SiteShell, PageHeader, cards, Reveal) preserved

### F-03 — Operator access

`canAccessOperatorUi` allows any of:

1. Local acceptance session (`NEXT_PUBLIC_SSRI_LOCAL_ACCEPTANCE_SESSION` non-prod opt-in)
2. Configured `NEXT_PUBLIC_SSRI_API_KEY`
3. Signed-in session with platform profile `role === "admin"`

Otherwise: redirect to `/login?next=…` when unauthenticated, or access-denied panel for signed-in non-admin users.

`/shell` still surfaces the backend `release_shell_enabled` / `SSRI_RELEASE_SHELL` banner; the feature flag is not replaced by the UI gate.

### F-04 — Admin access

`canAccessAdminUi` requires session + `role === "admin"`.

- Local acceptance **cannot** open admin UI
- Operator API key alone **cannot** open admin UI
- Denied state uses PlatformShell + plain-language message; API admin checks remain authoritative

No new roles or permission model invented (`user` | `admin` only).

---

## Access-control behaviour

| Surface | Unauthenticated | Local acceptance | Session `user` | Session `admin` | Operator API key |
|---|---|---|---|---|---|
| `/training/operator` | Login redirect / denied | Allowed (dev) | Denied | Allowed | Allowed |
| `/shell` | Login redirect / denied | Allowed (dev) | Denied | Allowed | Allowed |
| `/admin` | Login redirect | **Denied** | Denied | Allowed | N/A (not sufficient) |
| `/dashboard` | Existing `RequireSession` | Allowed (dev) | Allowed | Allowed | unchanged |
| `/workspace` | Existing PlatformShell flow | Allowed (dev) | Allowed | Allowed | unchanged |

Client gates are **UI-only**. Backend auth/RBAC is unchanged and remains the authority for mutations.

---

## Tests executed and results

**Command:**

```bash
cd frontend
npm test
```

**Result:** `89` tests, `0` failed (includes new marketing + operator access suites).

Focused coverage added:

1. Marketing pages do not advertise unimplemented endpoints as live  
2. Unauthenticated operator access blocked (helper)  
3. Non-admin / non-operator blocked where required  
4. Admin rejects non-admin (and rejects local acceptance)  
5. Admin access remains true for `role === admin`  
6. Dashboard `RequireSession` and workspace admin nav wiring still present  

---

## Browser verification

Local stack available (`:3000` frontend, `:8000` API health ok). Local acceptance flag was **on** in `frontend/.env.local`.

| Route | Observed |
|---|---|
| `/developers` | Live `POST /api/v1/assess`; roadmap lists `/v1/hazard` + SDKs as not shipped |
| `/platform` | Same available / roadmap split |
| `/training/operator` | Operator training UI loads (local acceptance) |
| `/shell` | Shell UI loads; `SSRI_RELEASE_SHELL` / “Release shell is off” banner present |
| `/admin` | **Admin access required** (local acceptance correctly denied) |
| `/dashboard` | Assessment workspace intact |
| `/workspace` | Workspace shell intact |
| `/login` | HTTP 200 |

Unauthenticated-without-local-acceptance operator blocking was verified by unit tests (env currently opts into local acceptance for headed workflows).

---

## Remaining limitations

- Client gates do not replace API permission checks
- With `NEXT_PUBLIC_SSRI_LOCAL_ACCEPTANCE_SESSION` enabled, operator UIs remain reachable without a real Supabase login (intentional local-dev path; disabled in production builds)
- Admin UI still needs a real `profiles.role = 'admin'` session; this environment did not exercise a live admin login end-to-end beyond the gate denying non-admin / local-acceptance
- Audit backlog items outside F-01/F-03/F-04 (CORS DELETE, assess history UI, checkpoint load hardening, etc.) are untouched
- Marketing `frontend/README.md` still mentions a future `/v1/hazard` swap in a developer note (docs only; not a live product claim)

---

## Final Git state

| Check | Result |
|---|---|
| Branch | `main` |
| HEAD (unchanged) | `44558779ffe93a0f2a3d151e8f0a9d309f7e8753` |
| Tracking | `main...origin/main [ahead 1]` |
| Commit / push | **Not performed** (awaiting approval) |

**Modified (unstaged):**  
`frontend/app/admin/page.tsx`, `developers/page.tsx`, `platform/page.tsx`, `shell/page.tsx`, `training/operator/page.tsx`

**Untracked (this remediation + prior evidence):**  
`frontend/components/auth/RequireAdminAccess.tsx`, `RequireOperatorAccess.tsx`, `frontend/lib/marketingApiCopy.ts`, `marketingApiCopy.test.ts`, `operatorAccess.ts`, `operatorAccess.test.ts`, `SSRI_TARGETED_FRONTEND_REMEDIATION_REPORT.md`, plus prior Abeokuta/audit artifacts (`SSRI_FINAL_LOCAL_ABEOKUTA_COMPLETION_REPORT.md`, `SSRI_WHOLE_PLATFORM_LOCAL_RELEASE_AUDIT.md`, `poc/abeokuta_final_*`)

---

## Decision

**Local remediation complete for F-01, F-03, and F-04.**  
Await approval before commit.
