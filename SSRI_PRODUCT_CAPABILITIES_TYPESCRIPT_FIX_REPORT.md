# SSRI — Product Capabilities TypeScript Fix Report

**Date:** 2026-11-21  
**Scope:** Frontend TypeScript only  
**HEAD preserved:** `d06878699f398a3b364a3ce48498c9cc0149786d`  
**Git / deploy:** no stage, commit, push, deploy, reset, rebase, amend, or clean

---


## 1. Root cause

Strict TypeScript rejected two patterns in the capability catalogue:

1. **`PRODUCT_GEOLOGICAL_IDS.includes(hazard)`** in the test — `includes` on a `readonly GeologicalCapabilityId[]` only accepts that geological union, so passing a `HazardId` was a type error.
2. **`mergeHazardNames`** built `ordered` from `PRODUCT_HAZARD_IDS` (literal union) and then called `ordered.includes(name)` / `ordered.push(name)` with a general `string`, which is incompatible with a narrowed `HazardId[]`.

The catalogues themselves were correct; the typing around merge/`includes` was not.

---

## 2. Exact files changed

| File | Change |
|------|--------|
| `frontend/lib/productCapabilities.ts` | Explicit `HazardId` / `GeologicalCapabilityId` types; typed catalogues; type guards; typed `mergeHazardNames` that rejects geological IDs |
| `frontend/lib/productCapabilities.test.ts` | Fixed type-safe assertions; added duplicate / unknown / geological / immutability cases |

No other product files were modified for this fix. Availability labels and live-inference-pending copy are unchanged.

---

## 3. Type design

```text
HazardId =
  "subsidence" | "landslide" | "sinkhole"

GeologicalCapabilityId =
  "overburden_thickness" | "lineament_density" |
  "lineament_distance" | "geological_ingestion"

HazardCatalogueEntry { id: HazardId; name; detail }
GeologicalCatalogueEntry { id: GeologicalCapabilityId; name; status }

isHazardId(value: string): value is HazardId
isGeologicalCapabilityId(value: string): value is GeologicalCapabilityId

mergeHazardNames(names: readonly string[]): string[]
```

`mergeHazardNames` contract:

- Always includes the three Stage 2.5 hazards.
- Deduplicates without mutating the input array.
- Skips geological conditioning identifiers.
- Appends unknown non-geological registry names after the canonical set (existing extensibility behaviour).

No `any`, no `as unknown as`, no `tsconfig` weakening.

---

## 4. Tests and results

### Verification commands (all exit 0)

| Command | Result |
|---------|--------|
| `npm run typecheck` | **PASS** (`TSC_EXIT=0`) |
| `npm run lint` | **PASS** (`LINT_EXIT=0`) |
| `npm test` | **46 passed**, 0 failed (`TEST_EXIT=0`) |
| `npm run build` | **PASS** (`BUILD_EXIT=0`) — Next.js 16.3.7 production build completed |

### Capability-focused coverage

- All three hazards present (`subsidence`, `landslide`, `sinkhole`)
- Geological IDs listed separately and not treated as hazards
- Truncated registry restores sinkhole
- Duplicate hazard names deduplicated
- Unknown non-geological names appended after canonical set
- Geological identifiers rejected from hazard merge
- Input array not mutated

---

## 5. Preservation confirmation

| Item | Status |
|------|--------|
| HEAD `d068786` | Unchanged |
| Three hazards | Preserved |
| Geological capabilities (incl. overburden + lineaments) | Preserved |
| Client-facing availability / live-pending labels | Preserved |
| Stage / commit / push / deploy | Not performed |

---

## Closing

The release-blocking TypeScript errors in the product-capabilities catalogue are resolved. Frontend typecheck, lint, unit tests, and production build all pass locally; changes remain uncommitted pending owner approval.
