# SSRI — Live lineament & overburden integration plan

**Date:** 2026-11-20  
**Scope:** Make lineament density/distance and overburden thickness **real live-assessment inputs**, without removing subsidence / landslide / sinkhole.  
**Status:** **Audit + plan only.** No breaking model, acquisition, or checkpoint changes in this pass.  
**Git tip at audit:** local `main` aligned with `origin/main` (worker prep / readiness commits already on remote when audited).

---

## Verdict (gate before science changes)

**Do not ship “live v2 inference” against today’s production Stage 2.5 checkpoints.**

| Finding | Evidence |
|---------|----------|
| Live AOI acquires **13 channels only** | `build_feature_stack` stacks terrain + spectral + gravity + magnetics; no lineament/overburden calls |
| Schema v2 (16 channels) exists for **offline/shell** only | `CHANNEL_NAMES_V2` = v1 + `overburden_thickness`, `lineament_density`, `lineament_distance` |
| Shell can **apply** owner vectors/grids onto tiles | `release_shell/feature_apply.py`, `/lineaments/apply`, `/overburden/apply` |
| Assess already **reports** conditioning honestly | `assess_conditioning.sample_conditioning_features` → unavailable on v1 stacks |
| Default `SSRIModel` expects **`in_channels=13`** | `architecture/config.py` default `CHANNEL_COUNT` |
| Inference safety hard-codes **13** | `inference/safety.py`: `model.in_channels != CHANNEL_COUNT` → error |
| No repo lineament/overburden global rasters | No `data/**/lineament*`; geophysics docs cover WGM/EMAG only |
| Depth ≠ thickness | Shell rejects auto-convert of `depth_to_interface` into `overburden_thickness` |

**Scientific rule (non-negotiable):** Additional factors must not be claimed to influence scores until a checkpoint is trained (or otherwise validated) with those channels. UI may show acquired values earlier; scores must not imply use when the loaded model is v1.

---

## 1. Current architecture (relevant files)

### Live acquisition (v1)

| Piece | Path |
|-------|------|
| Flag | `api/acquisition.py` → `live_acquisition_enabled()` / `SSRI_LIVE_ACQUISITION_ENABLED` |
| Stack builder | `data/feature_engineering.py` → `build_feature_stack` |
| Assess wiring | `api/routes/assess.py` → `acquire_feature_array_for_bbox` |
| Channel order | `ml/constants.py` → `CHANNEL_NAMES` (13) |

Live sources today: DEM (OpenTopo/GEE), Sentinel-2 indices (GEE), local gravity/magnetics GeoTIFFs.

### Schema v2 + offline apply

| Piece | Path |
|-------|------|
| Schema | `release_shell/channel_schema.py` |
| Lineament math | `release_shell/lineaments.py` (density window m/m²; distance m) |
| Apply to tiles | `release_shell/feature_apply.py` |
| Shell API | `release_shell/routes.py` apply/inspect endpoints |
| Conditioning response | `api/assess_conditioning.py` |
| Frontend panels | `frontend/lib/conditioning.ts`, `AssessResultModal` |

### Model / checkpoint

| Piece | Path |
|-------|------|
| Model | `architecture/model.py` (`SSRIModel`) |
| Config default | `architecture/config.py` `in_channels=CHANNEL_COUNT` (13) |
| Load | `inference/checkpoint.py` → `load_evaluation_model` |
| Safety | `inference/safety.py` enforces 13 channels |

---

## 2. Data-source audit

### Lineaments

| Source class | In-repo? | Live AOI ready? | Notes |
|--------------|----------|-----------------|-------|
| Owner GeoJSON via `/shell` | Yes (pipeline) | No (not auto for map AOI) | Proven method; CRS must be declared |
| Packaged global/regional lineament catalog | **No** | **No** | Nothing under `data/` |
| External APIs (e.g. published fault traces) | Not wired | Unknown coverage | Would need license, CRS, AOI intersection, cost |

**Gap:** Live map assess has **no automatic lineament provider**. Integration requires either (A) registered regional catalogs with coverage metadata, or (B) per-assessment upload, or (C) org-configured path env (similar to `GRAVITY_DATA_PATH`).

### Overburden thickness

| Source class | In-repo? | Live AOI ready? | Notes |
|--------------|----------|-----------------|-------|
| Owner point-grid CSV via `/shell` | Yes | No for live map | Thickness only; depth-to-interface not aliased |
| Packaged overburden/sediment-thickness raster | **No** | **No** | |
| “Depth” products | Rejected as thickness | N/A | Keep separate channel/name if ever supported |

**Gap:** Same as lineaments — no live provider. Any chosen raster must declare units (m thickness), nodata, CRS, and AOI coverage.

### Coverage / provenance requirements (any new provider)

For each AOI assessment, record:

1. Dataset id + version + license  
2. CRS + transform used for resampling onto the AOI grid  
3. Resolution vs model grid (30 m typical)  
4. Nodata policy (`FEATURE_NODATA = -9999`, never zero-fill)  
5. `available` / `nodata` / `unavailable` / `out_of_coverage` per channel at sample cell  
6. Whether the **loaded checkpoint** consumed the channel (`used_in_inference`)

---

## 3. Checkpoint compatibility (blocking)

```text
Live AOI v1 tensor (13,H,W)  +  checkpoint in_channels=13   → OK today
Live AOI v2 tensor (16,H,W)  +  checkpoint in_channels=13   → FORBIDDEN (silent pad/trim would fabricate or drop science)
Offline v2 tensor (16,H,W)   +  checkpoint trained v2 (16)  → Required path for “inputs affect scores”
```

**Rules already consistent with product intent:**

- Do not append three channels and run a 13-channel `best.pt`.  
- Do not zero-fill missing v2 channels to “make shapes match.”  
- Pad-with-nodata is only valid for **training dataset preparation** / shell apply before a **v2 training run**, not for scoring with a v1 checkpoint.

---

## 4. Recommended implementation phases (smallest defensible path)

### Phase 0 — Contracts only (non-breaking) ✅ partially done

- Keep three hazards.  
- Keep v1 live assess working.  
- Conditioning panels already distinguish unavailable vs NoData vs available.  
- Extend response fields if needed: `acquired`, `available_at_cell`, `used_in_inference`, `checkpoint_schema_version`.

**No model retrain required.**

### Phase 1 — Live acquisition adapters (optional inputs, still v1 scores)

Goal: when configured datasets exist and AOI intersects coverage, **sample/resample** lineament + overburden onto the AOI grid for **reporting** (and for future v2 training dumps)—but **inference still uses the 13-channel tensor** until a v2 checkpoint is active.

Work:

1. New modules under `data/` or `api/` e.g. `acquire_lineament_layers`, `acquire_overburden_layer`.  
2. Reuse `derive_lineament_rasters` / overburden resample from shell with AOI `grid_spec`.  
3. Config via env paths (mirror geophysics): e.g. `SSRI_LINEAMENT_VECTOR_PATH`, `SSRI_OVERBURDEN_RASTER_PATH`, plus CRS declarations.  
4. If path unset or AOI outside coverage → `unavailable` (not zero).  
5. Assess response attaches conditioning from either stack channels (if present) or side-car acquisition metadata—**without** changing the tensor passed to a v1 model.

**Tests:** coverage miss, CRS mismatch, nodata cell, happy-path sample; regression that v1 logits path unchanged.

**Cost:** storage for regional catalogs; no new paid API required if owner supplies files. External catalog APIs TBD (license/cost).

### Phase 2 — Schema-v2 training & evaluation (required before “inputs affect predictions”)

1. Build/apply v2 datasets (shell already supports apply).  
2. Train `SSRIModel` with `in_channels=16`, persist `channel_schema_version=v2` + `channel_names` in checkpoint `model_config` / release_shell meta.  
3. Held-out evaluation vs v1 baseline (AUC / block policy already in shell)—report delta honestly; status stays `NOT_VALIDATED` until external review.  
4. Promote v2 checkpoint explicitly; dashboard/active model must advertise schema v2.

**Do not** auto-promote over v1 without operator action.

### Phase 3 — Live assess consumes v2 when checkpoint is v2

1. After live v1 stack build, if active checkpoint schema is v2 **and** acquisition succeeded for the three channels, concatenate channels in `CHANNEL_NAMES_V2` order (nodata where missing—**only if training used the same nodata policy**).  
2. If checkpoint is v2 but a required channel is fully unavailable for AOI → **fail closed** or refuse live assess with plain-language error (prefer fail closed over silent nodata-only inference unless training explicitly used that pattern).  
3. If checkpoint is v1 → never pass 16 channels.  
4. Relax/generalize `inference/safety.py` to accept checkpoint-declared `in_channels` ∈ {13,16}, not hard-coded 13 only.  
5. Frontend: `used_in_inference` true only when checkpoint schema includes the channel **and** cell status is `available` (or documented training-equivalent nodata handling).

### Phase 4 — Deploy

- Mount lineament/overburden assets on API **and** worker (same paths).  
- Document size/license.  
- No Redis/worker changes required for sync assess; async/training still needs worker (separate blocker).

---

## 5. API / frontend contract updates (only as needed)

| Field / UI | Now | After Phase 1–3 |
|------------|-----|-----------------|
| `conditioning_features.layers.*.status` | available/nodata/unavailable | Keep; add `out_of_coverage` if useful |
| `used_in_inference` | Implied weakly | **Explicit boolean per layer** |
| `checkpoint_schema_version` / `channel_names` | Partially echoed | Always echo; drive UI copy |
| Hazard list | 3 hazards | Unchanged |
| Live copy | “v1 does not acquire…” | “Acquired for reporting” vs “Used in this model” |

Do not invent map overlays for lineaments/overburden until a real vector/raster product is mounted (same honesty rule as gravity).

---

## 6. Required tests (before claiming live v2)

1. Unit: lineament/overburden resample CRS + nodata.  
2. Unit: refuse v2 tensor + v1 checkpoint.  
3. Unit: accept v2 tensor + v2 checkpoint.  
4. API: assess response flags acquired / at-cell / used.  
5. Regression: live v1 assess path + three hazards unchanged.  
6. Training smoke: v2 channel count in `feature_stack.npy` + checkpoint `in_channels=16`.  
7. FE: panels show “used in this assessment: no” for v1 checkpoint even if side-car values exist (Phase 1).

---

## 7. Infrastructure / cost implications

| Item | Need |
|------|------|
| Regional lineament GeoJSON / overburden GeoTIFF | Owner-supplied or newly licensed data (size may exceed Git; mount like geophysics) |
| Disk on Render API (+ worker if async) | Persistent volume for catalogs |
| Paid external geology APIs | **None identified as already integrated**; any new vendor needs owner approval |
| Retraining compute | Local/Compose or approved worker; not free if cloud GPU needed |
| Celery worker | Still required for async/training jobs (orthogonal to this feature) |

---

## 8. Smallest scientifically defensible retrain plan

1. Freeze label geography and split policy (existing shell blocks).  
2. Apply lineaments + overburden thickness to training tiles (shell).  
3. Validate manifests `channel_schema_version=v2`, no negative thickness without warning, nodata not zero.  
4. Train Stage 2.5 `SSRIModel` with `in_channels=16`, same three heads (subsidence/landslide/sinkhole).  
5. Evaluate held-out blocks; compare to v1 checkpoint on overlapping geography.  
6. Record `NOT_VALIDATED`; promote only via existing activate/promote flows.  
7. Only then enable Phase 3 live v2 assess against that checkpoint.

---

## 9. What we will not do in the first implementation PR

- Change production weights without a v2 training run.  
- Append channels to a 13-channel forward pass.  
- Zero-fill missing geology.  
- Alias depth-to-bedrock as overburden thickness.  
- Remove or rename sinkhole / other hazards.  
- Claim live scores “use lineaments/overburden” under a v1 checkpoint.  
- Push to GitHub from this agent (owner handles push).

---

## 10. Proposed next execution step (after you approve)

**Phase 1 only:** live acquisition adapters + response/`used_in_inference` clarity, keeping v1 inference intact—**or** skip straight to Phase 2 dataset/retrain if you already have lineament/overburden training coverage and want scores to change first.

Please confirm:

1. Preferred data source for lineaments (path/catalog vs per-job upload).  
2. Preferred overburden thickness product (path + units proof).  
3. Whether Phase 1 (report-only acquisition) is acceptable before retrain, or retrain-first is mandatory.
