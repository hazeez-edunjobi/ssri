# SSRI — Dashboard Preflight UX and Model Status Remediation Report

**Date:** 2026-11-21  
**Baseline:** `5d2e0cb18de77b2494a79719e06b32b20a3a2704`  
**Scope:** Frontend-only remediation (no Git, deploy, promote, or backend changes)

---

## 1. Root cause addressed

From `SSRI_DASHBOARD_ASSESSMENT_PREFLIGHT_AUDIT.md`:

| Issue | Remediation |
|-------|-------------|
| Run Assessment stayed enabled while local preflight blocked missing models | Button now uses `assessmentButtonDisabled(...)` |
| 401 / 403 / network collapsed into “no promoted model” | Explicit `ActiveModelView.kind`: `loading` \| `available` \| `missing` \| `unauthorized` \| `forbidden` \| `error` |
| No refresh after session restore / operator promote | Refresh on mount (current credentials), when `email` changes, on `visibilitychange` / `pageshow`, and via **Refresh status** |
| Confusing “click with no network” UX | Disabled control + visible `assess-model-blocked-hint` near the button |

Local missing-checkpoint guard in `onAssess` **preserved**.

---

## 2. Files changed

| Path | Change |
|------|--------|
| `frontend/lib/activeModelStatus.ts` | **New** status model, button/hint helpers |
| `frontend/lib/activeModelStatus.test.ts` | **New** unit coverage |
| `frontend/lib/api.ts` | `loadActiveModelStatus()` — status-aware fetch using current `authHeaders()` |
| `frontend/app/dashboard/page.tsx` | Status UI, disable rules, refresh lifecycle |
| `frontend/e2e/dashboard.spec.ts` | Disabled-button + unlock-via-operator-path for AOI validation |

Unchanged: `assessRequest.ts` (still omits empty paths); backend; registry; production infra.

---

## 3. Before / after state behaviour

| Situation | Before | After |
|-----------|--------|-------|
| Empty active registry (200) | Amber “no checkpoint”; button **enabled**; click local-returns | `missing`; button **disabled**; hint under button |
| 401 on `/models/active` | Same as empty registry | `unauthorized` — sign-in messaging |
| 403 | Same as empty registry | `forbidden` — permission messaging |
| Network / other HTTP failure | Same as empty registry | `error` — retry messaging + Refresh |
| Promoted model (`checkpoint_available`) | Enabled when available | `available`; button enabled (hazards permitting) |
| Operator fills advanced checkpoint | Assess could proceed after click | Button **enables** when path non-empty; backend still authorizes/jails path |
| Point/polygon/CRS checks | Unchanged order | Unchanged; still run if button unlocked |

---

## 4. Authentication and refresh lifecycle

1. `loadActiveModelStatus()` always calls `authHeaders()` at request time (no mount-time token capture).  
2. Dashboard refresh triggers:  
   - Initial workspace load (after health/ready path).  
   - `email` change from `useRequiredSession` (session restoration).  
   - Document `visibilitychange` / window `pageshow` (return after promote).  
   - Explicit **Refresh status** control (`data-testid="refresh-active-model"`).  
3. No polling loop.

---

## 5. Tests and exact results

| Command | Exit | Result |
|---------|------|--------|
| `npm run typecheck` | **0** | Pass |
| `npm run lint` | **0** | Pass |
| `npm test` | **0** | **58 passed** (was 46; +12 from `activeModelStatus.test.ts`) |
| `npm run build` | **0** | Pass |

E2E: specs updated for disabled Run assessment; full Playwright against production not required for this remediation and was not claimed as run.

Covered unit behaviours: missing disables; operator path unlocks; 401/403/error ≠ missing; available enables; Stage 2.5 wording without invented paths.

---

## 6. Backend safety and scientific contracts

| Contract | Status |
|----------|--------|
| Backend active-model resolution / path jail / RBAC | **Unchanged** |
| Local preflight guard retained | **Yes** |
| No fabricated checkpoint paths | **Yes** |
| Ordinary users not asked for server paths | **Yes** (advanced details only) |
| 13-channel Stage 2.5 live contract copy | **Preserved** |
| Three hazards + separate geological panel | **Preserved** (`ProductCapabilities`) |
| `NOT_VALIDATED` / Phase 6 | **Unchanged** (frontend does not claim validation) |

---

## 7. Remaining production checkpoint blocker

Dashboard UX no longer implies “empty registry” on auth/network failure, but **assess still cannot succeed in production until an operator promotes a real Stage 2.5 13-channel checkpoint** on durable API storage.

```text
PRODUCTION_CHECKPOINT_VERIFICATION = NOT_VERIFIED
```

See `SSRI_PRODUCTION_CHECKPOINT_DISCOVERY_AND_VERIFICATION_REPORT.md`.

---

## 8. Git / deployment confirmation

```text
No git add / commit / push / tag
No Vercel or Render deploy
No environment or registry mutation
No model promotion
```

Working-tree frontend changes are local until a separate owner-approved frontend release.
