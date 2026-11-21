# SSRI — Dashboard Assessment Preflight and Frontend State Audit

**Date:** 2026-11-21  
**Mode:** READ-ONLY (no source, Git, deploy, promote, or config changes)  
**Engineering baseline (reference):** `5d2e0cb18de77b2494a79719e06b32b20a3a2704`  
**Production API:** `https://ssri-api.onrender.com`

---

## 1. Executive verdict

```text
VERDICT: FRONTEND PREFLIGHT BLOCKS ASSESS — NO HTTP ASSESS REQUEST BY DESIGN
ROOT CAUSE: Local early-return when checkpointAvailable === false
BACKEND SAFETY: Intact (would also fail closed if request were sent)
UX DEFECT: Run Assessment stays enabled despite known missing active model
MAP STATUS: map-ready gravity-pending is an intentional sr-only map/gravity debug label — unrelated to assess
```

Confirmed from source: clicking **Run assessment** with no operator checkpoint path and `checkpointAvailable === false` sets a **local** error string and **returns before** `submitAssess` / `fetch(/api/v1/assess)`. That matches “no assessment network request.”

The banner *“No promoted Stage 2.5 checkpoint is configured…”* is **local UI state** derived from `GET /training/models/active` (or its failure), not a cached assess response and not the live `INVALID_REQUEST` body from `/assess` for this click path.

---

## 2. Exact dashboard initialization request sequence

From `useEffect(..., [])` in `frontend/app/dashboard/page.tsx` (mount, once):

| Step | Client call | HTTP | Auth | On success | On failure |
|------|-------------|------|------|------------|------------|
| 1 | `getHealth()` | `GET /api/v1/health` | None | Continue | `apiStatus = "down"`; still continues to model/shell |
| 2 | `getReady()` | `GET /api/v1/ready` | None | `apiStatus = "ok"` → UI “reachable · ready” | `apiStatus = "degraded"` (health ok, ready failed) |
| 3 | `getActiveTrainedModel()` | `GET /api/v1/training/models/active` | Bearer (API key env **or** Supabase session) | Sets `checkpointAvailable`, `activeModelId`, `activeModelLabel` | Catch → all three cleared / `checkpointAvailable=false` |
| 4 | `getShellStatusFull()` | Release-shell status | Via that client | Hazard list via `mergeHazardNames` | Keep fallback hazards |

Parallel / separate map effect (not in the same async IIFE):

| Step | Client call | Purpose |
|------|-------------|---------|
| Map init | MapLibre + optional `getGravityLayer()` | Overlay only; not required for assess |

**Caching / dedupe:** None beyond React mount-once `useEffect` with `[]`. No SWR/React Query. **No re-fetch** when auth session changes after mount.

**Auth attachment** (`authHeaders` in `api.ts`): explicit key → `NEXT_PUBLIC_SSRI_API_KEY` → Supabase `getSession()` access token. Health/ready intentionally unauthenticated.

---

## 3. Complete assessment submission call chain

```text
<button onClick={onAssess}>
  → onAssess (useCallback)
    → [guards / early returns]
    → setLoading(true); setError(null); setModalOpen(true)
    → submitAssess(payload)          // api.ts
      → authHeaders()
      → buildAssessRequestBody(payload)  // assessRequest.ts — omits empty checkpoint/model_id
      → POST /api/v1/assess
```

### Early returns inside `onAssess` (in order)

| # | Condition | Effect | Calls `submitAssess`? |
|---|-----------|--------|------------------------|
| 1 | Point mode, no features, no point | Local error: select point | **No** |
| 2 | Polygon mode, no features, no polygon | Local error: draw polygon | **No** |
| 3 | No features and no point/polygon | Local error: select AOI | **No** |
| 4 | Shell + checkpoint + geography without CRS | Local CRS error | **No** |
| 5 | `!checkpoint.trim() && !checkpointAvailable` | Local “No valid production checkpoint…” | **No** |
| — | Else | Network assess | **Yes** |

Button wiring: `onClick={onAssess}` is attached. Disabled only when `loading || selectedHazards.length === 0` — **not** when the active model is missing.

---

## 4. Exact reason no request is sent (confirmed)

```644:650:frontend/app/dashboard/page.tsx
    if (!checkpoint.trim() && !checkpointAvailable) {
      setError(
        "No valid production checkpoint is configured. Ask an operator to promote " +
          "a trained Stage 2.5 (13-channel) model, then retry. Ordinary assessments " +
          "do not require a server filesystem path.",
      );
      return;
    }
```

With production UI showing no promoted model, `checkpointAvailable` is `false` and the advanced checkpoint field is empty by default → **guard #5 fires** → **no** `POST /api/v1/assess`.

Origin of the **status panel** copy (separate from the click error):

```959:967:frontend/app/dashboard/page.tsx
            {checkpointAvailable && activeModelLabel ? (
              ...
            ) : (
              <p ... data-testid="active-model-missing">
                No promoted Stage 2.5 checkpoint is configured. Assessments cannot run
                until an operator promotes a trained model.
              </p>
            )}
```

| Displayed text | Source |
|----------------|--------|
| Panel “No promoted Stage 2.5 checkpoint…” | Local, from init `getActiveTrainedModel` result/failure |
| Click error “No valid production checkpoint…” | Local preflight in `onAssess` (wording aligned with backend) |
| Backend `INVALID_REQUEST` for this click | **Not reached** while guard #5 holds |

---

## 5. Active-model response handling matrix

`getActiveTrainedModel` → `GET /api/v1/training/models/active` with auth.  
Availability: `Boolean(active.checkpoint_available ?? active.checkpoint_path)`.

| Response / failure | Client handling | UI / assess preflight |
|--------------------|-----------------|------------------------|
| **200**, `active` set, `checkpoint_available: true` (path often `null` for USER) | `checkpointAvailable=true`, label from `active` | Panel: using promoted model; assess may proceed |
| **200**, `active: null` / unavailable | `checkpointAvailable=false` | Panel: missing; assess blocked locally |
| **200**, missing `checkpoint_available`, `checkpoint_path: null` | `Boolean(null)` → **false** | Treated as missing (correct for redacted USER payload when no file) |
| **401** | Throw → catch → clear model state | Same as missing (cannot distinguish auth vs empty registry in UI) |
| **403** | Same catch path | Same as missing |
| Network / parse failure | Same catch path | Same as missing |
| Stale cache | N/A (no persistent cache); stale only until remount | No post-promote refresh without reload |

**Accuracy gap:** 401/403/network are visually identical to “no promoted model.” Users who load the dashboard before a session is ready may also stay blocked until full reload (effect deps `[]`).

---

## 6. Source of `map-ready gravity-pending`

```1163:1171:frontend/app/dashboard/page.tsx
        <div
          data-testid="ssri-map-status"
          ...
          className="sr-only"
        >
          {mapReady ? "map-ready" : "map-loading"}
          {gravityLoaded ? " gravity-loaded" : " gravity-pending"}
        </div>
```

| Token | Meaning |
|-------|---------|
| `map-ready` / `map-loading` | MapLibre init / 2.5s ready timer — **map init state** |
| `gravity-loaded` / `gravity-pending` | Optional WGM gravity GeoJSON overlay loaded or not |

This is an **sr-only test/debug status string**, not assessment status and not API readiness. Ending in `map-ready gravity-pending` only means the map is up and the optional gravity layer has not loaded (or failed)—**orthogonal** to checkpoint promotion.

---

## 7. Frontend defects versus expected backend behaviour

| Topic | Assessment |
|-------|------------|
| Blocking assess without active model | **Intentional client preflight**; aligns with known empty active registry; avoids useless round-trip |
| Backend would still fail closed | **Yes** — same class of message if `/assess` were called without active model |
| Button remains enabled | **UX inconsistency** — copy says assessments cannot run; control still clickable |
| Ordinary users asked for filesystem paths | **No** (advanced details collapsed; empty by default) |
| Refresh after operator promote | **Missing** — must remount/reload to re-read `/models/active` |
| Auth failure vs missing model | **Collapsed** into one amber message |
| `map-ready gravity-pending` | **Not a defect** for assess |
| 13-channel / three hazards / geo separate | Catalogue/`ProductCapabilities` unchanged; not causal here |

---

## 8. Recommended minimal remediation (guidance only — not implemented)

1. **Disable** Run assessment when `!checkpointAvailable && !checkpoint.trim()`, with visible reason (or keep enabled but that is weaker UX).  
2. Optionally still allow click to show the same message (current) **or** disable and skip the confusing “click does nothing on the network” observation.  
3. **Re-fetch** active model when auth session becomes available and after returning from operator promote (focus/visibility or explicit Refresh).  
4. Distinguish **401** (“Sign in to see model status”) from **200 with no active** in the panel.  
5. Do **not** remove backend fail-closed checks; do **not** ask ordinary users for server paths.  
6. Production blocker remains: **promote a real Stage 2.5 13-channel model** on durable storage (separate ops task).

---

## 9. Test results

Executed this session (no new tests added):

| Command | Exit | Result |
|---------|------|--------|
| `npm run typecheck` | **0** | Pass |
| `npm run lint` | **0** | Pass |
| `npm test` | **0** | **46 passed** |

E2E already expects missing-checkpoint / auth / point validation text on Run assessment (`frontend/e2e/dashboard.spec.ts`); not re-run against production Playwright in this audit.

Build not required for this read-only preflight conclusion; typecheck/lint/unit gates suffice for source audit.

---

## 10. Local source evidence vs production observations

| Claim | Class |
|-------|-------|
| Init sequence, guards, button disabled rules, `map-ready gravity-pending` | **Local source** (`dashboard/page.tsx`, `api.ts`, `assessRequest.ts`) |
| No `/assess` when guard #5 trips | **Local source** (confirmed control flow) |
| Production UI shows ready + missing checkpoint + enabled Run assessment | **Production observation** (user report; consistent with source) |
| No assess network request on click | **Consistent with source**; production DevTools not re-captured this session |
| Active registry empty / unpromoted on API | **Prior production audit** (`SSRI_PRODUCTION_CHECKPOINT_DISCOVERY_AND_VERIFICATION_REPORT.md`) — not re-probed with operator credentials here |
| Health/ready unauthenticated success on prod | **Prior + consistent** with “API reachable · ready” label mapping (`apiHealthLabel`) |

---

## Compliance

No files modified. No promote. No deploy. No Git operations. Backend contract unchanged.
