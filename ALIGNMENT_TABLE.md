# ALIGNMENT_TABLE — Frontend ↔ Backend hazard & channel audit

**Branch:** `finish/frontend-align-rc3` · **Local only, no push.**
**Status labels:** VERIFIED (read in source / exercised by a test) · REPORTED (claimed, not re-run here) · UNKNOWN.
**Demo data is SYNTHETIC.** The assumed Abeokuta CRS is UNKNOWN and is never treated as fact.

---

## 1. Headline answer: how many hazards?

**There are exactly 3 hazards**, not 5. Source of truth: the enum `LabelClass`
in [labels.py](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/model/src/ssri_model/ml/labels.py#L8-L13),
consumed by the registry `default_hazard_registry()` in
[hazards.py](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/model/src/ssri_model/release_shell/hazards.py#L21-L26).

| class_id | hazard (VERIFIED) |
|---|---|
| 0 | subsidence |
| 1 | landslide |
| 2 | sinkhole |

The owner's "5 items" = **3 hazards + 2 extra v2 channels**.

`lineament` and `overburden` are **channels in schema v2, not hazards**:

- `overburden_thickness` — schema v2 channel (not a hazard).
- `lineament_density` — schema v2 channel (not a hazard).
- `lineament_distance` — schema v2 channel (not a hazard).

Registry source comment (VERIFIED):
> "This task keeps the three Stage 2.5 hazards. Adding a hazard later is a registry
> entry plus labelled data — not a code fork." — [hazards.py](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/model/src/ssri_model/release_shell/hazards.py#L1-L5)

**Do NOT invent new hazard classes.** No new class was added in this task.

---

## 2. Channel schemas (backend source of truth)

From [channel_schema.py](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/model/src/ssri_model/release_shell/channel_schema.py)
and [constants.py](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/model/src/ssri_model/ml/constants.py#L22-L36).

### Schema v1 — 13 channels (VERIFIED)
`elevation, slope, plan_curvature, profile_curvature, twi, relative_relief,
valley_depth, ndvi, ndwi, clay_mineral_ratio, iron_oxide_index, gravity, magnetics`

### Schema v2 — 16 channels = v1 + 3 (VERIFIED)
v1 + `overburden_thickness, lineament_density, lineament_distance`

Default schema is **v1** (`default_channel_schema`), matching flag-off behaviour.
`depth_to_bedrock` is **never** silently aliased to `overburden_thickness`
([channel_schema.py](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/model/src/ssri_model/release_shell/channel_schema.py#L17-L42)).

---

## 3. Backend registry surface exposed to the frontend

Added this task: the `/api/v1/release-shell/status` settings now carry the hazard
registry and supported schemas so the UI can derive instead of hard-code.
Source: [routes.py](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/model/src/ssri_model/release_shell/routes.py#L105-L145).

| Field | Where | Value |
|---|---|---|
| `settings.hazards[]` | status endpoint | `[{name, class_id, enabled_by_default}]` (VERIFIED) |
| `settings.supported_channel_schemas` | status endpoint | `["v1","v2"]` (VERIFIED) |
| `settings.default_channel_schema` | status endpoint | `"v1"` (VERIFIED) |
| `settings.channel_schemas.{v1,v2}` | status endpoint | `{channel_count, channel_names}` (VERIFIED) |
| `settings.block_size_deg` / `buffer_km` / `minimums` | status endpoint | numbers (VERIFIED) |

Contract test added: `test_status_exposes_hazard_registry` in
[test_release_shell_validator.py](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/model/tests/test_release_shell_validator.py)
— asserts names `["subsidence","landslide","sinkhole"]`, class ids `[0,1,2]`, and
that `overburden_thickness` / `lineament_density` are **not** in the hazard list.
Result: **7 passed** (VERIFIED, re-run this session).

---

## 4. Per-hazard appearance map

| Hazard | Backend | Frontend (after fix) | Mismatch status |
|---|---|---|---|
| subsidence | `LabelClass.SUBSIDENCE`; registry id 0 | dashboard hazard selector (from registry); `/hazards#subsidence`; `lib/report.ts`; `AssessResultModal` | ALIGNED |
| landslide | `LabelClass.LANDSLIDE`; id 1 | dashboard (from registry); `/hazards#landslide`; report; modal | ALIGNED |
| sinkhole | `LabelClass.SINKHOLE`; id 2 | dashboard (from registry); `/hazards#sinkhole`; nav footer; developers example; report; modal | ALIGNED |
| **liquefaction** | **DOES NOT EXIST** | was hard-coded in `/hazards` page, footer nav, developers example | **FOUND & REMOVED** (invented class — see §5) |

### Where hazards are listed in the frontend (post-fix)

| Surface | File | Derives from backend? |
|---|---|---|
| Dashboard hazard selector + channel-schema hint | [dashboard/page.tsx](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/frontend/app/dashboard/page.tsx) | YES — `getShellStatusFull().settings.hazards`; `FALLBACK_HAZARDS` only if the call fails |
| Shell upload settings panel | [shell/page.tsx](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/frontend/app/shell/page.tsx) | YES — `settings.hazards`, `channel_schemas` counts |
| Training operator notes | [operator/page.tsx](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/frontend/app/training/operator/page.tsx) | YES — backend `requirements.hazards` |
| Assessment modal | [AssessResultModal.tsx](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/frontend/components/AssessResultModal.tsx) | YES — renders API `hazard_profiles`, no hard-coded colour map |
| HTML report | [report.ts](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/frontend/lib/report.ts) | YES — from `AssessResponse` |
| Static marketing `/hazards` page | [hazards/page.tsx](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/frontend/app/hazards/page.tsx) | Static copy, but now names only the real 3 hazards |
| Footer nav | [navigation.ts](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/frontend/lib/navigation.ts) | "Sinkholes" → `/hazards#sinkhole` |
| Developers example JSON | [developers/page.tsx](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/frontend/app/developers/page.tsx) | `subsidence/landslide/sinkhole` |

---

## 5. Mismatches found and fixed this task

| # | Mismatch | Location | Fix | Status |
|---|---|---|---|---|
| M1 | Invented hazard `liquefaction` ("Soft, wet ground") presented as a real target | `app/hazards/page.tsx` | Replaced with `sinkhole` (id `sinkhole`, icon `layers`) | FIXED |
| M2 | Footer link "Liquefaction" → `#liquefaction` (dead anchor) | `lib/navigation.ts` | "Sinkholes" → `#sinkhole` | FIXED |
| M3 | Developers sample response key `"liquefaction"` | `app/developers/page.tsx` | `"sinkhole"` | FIXED |
| M4 | Hard-coded `const HAZARDS = [...]` in the dashboard selector | `app/dashboard/page.tsx` | Derives from `/release-shell/status`; `FALLBACK_HAZARDS` list only on error | FIXED |
| M5 | No backend endpoint exposed the hazard registry | backend `routes.py` | `settings.hazards` + `supported_channel_schemas` added; contract test added | FIXED |
| M6 | Channel counts (13/16) hard-coded in shell UI copy | `app/shell/page.tsx` | Reads `settings.channel_schemas.{v1,v2}.channel_count` | FIXED |
| M7 | `hazard_notes` hard-coded 3 names in operator page | `app/training/operator/page.tsx` | Reads backend `requirements.hazards` | FIXED |
| M8 | `AssessResultModal` had a hard-coded `HAZARD_COLORS` map (broke for unknown hazards) | `components/AssessResultModal.tsx` | Deterministic `HAZARD_PALETTE` indexed by position; colour not keyed by name | FIXED |
| M9 | Errors surfaced as raw body / `[object Object]` | `lib/api.ts` | `parseError` + `extractErrorMessage` produce plain language with a next step; shell `no_trained_model` envelope unwrapped | FIXED |
| M10 | No downloadable report | (none existed) | `lib/report.ts` + download button produce a self-contained `.html` | ADDED |

### Remaining static marketing copy (NOT a mismatch — VERIFIED)
Synonyms on the landing pages ("ground settling", "settling concern") map to
`subsidence` and stay consistent with the 3 real hazards:
`Hero.tsx`, `CorePlatform.tsx`, `HowItWorks.tsx`, `BentoGrid.tsx`,
`EverydayUses.tsx`, `UseCases.tsx`, `app/layout.tsx`, `app/dashboard/layout.tsx`.
No invented hazard appears in any of these. **No change required.**

---

## 6. Channels in the frontend

| Channel concept | Backend | Frontend | Status |
|---|---|---|---|
| v1 13 channels | `CHANNEL_NAMES` | shell page reads `channel_schemas.v1.channel_names`; report prints `channel_names` from the assess response | ALIGNED |
| v2 16 channels | `CHANNEL_NAMES_V2` | shell page reads `channel_schemas.v2`; upload description shows count from settings | ALIGNED |
| `overburden_thickness` | v2 channel | never listed as a hazard; appears only in the layer-alias table and v2 channel list | ALIGNED |
| `lineament_density` / `lineament_distance` | v2 channels | never listed as hazards; lineament vectors handled by `/release-shell/lineaments/inspect` | ALIGNED |
| `depth_to_bedrock` | v2 alias (not schema) | not surfaced as a channel; alias normalisation is backend-only | ALIGNED (by design) |

**Verdict:** the UI treats `lineament` and `overburden` correctly — as v2 channels,
never as hazards.

---

## 7. Open items

- Marketing landing copy uses lay synonyms ("ground settling") rather than the
  literal backend term `subsidence`. Intentional (plain-language brand voice),
  consistent with the 3 hazards; **not** a data-bearing surface. No action.
- `FALLBACK_HAZARDS` in the dashboard is a resilience fallback for when the status
  endpoint is unreachable. It is not the primary source and is documented in-code.
