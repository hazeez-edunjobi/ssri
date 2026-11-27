# SSRI — Assessment Auditability and Uncertainty Integrity

**Date:** 2026-11-27  
**Reference assessment:** `assess-63a666e677fff95c`  
**Checkpoint:** `ssri-model-1c8de63cd3` (SHA-256 `d912027e17ed532687f9d2a2c74fd3c18ca8c812ae49107d939ade19dde5d004`)  
**Science posture:** `NOT_VALIDATED` unchanged.  
**Milestone commit:** `dd4caaa` (deployed to `https://ssri-api.onrender.com`).

## 1. Completed implementation

### Objective 1 — Uncertainty integrity
- `count_active_dropout_modules`, `samples_effectively_deterministic`, `resolve_interval_availability` in `ssri_model.uncertainty`.
- When dropout modules are absent or MC variance is ~0, hazard profiles keep **point estimates** and set:
  - `credible_interval_80` / `credible_interval_95` → `null`
  - `uncertainty_intervals_available` → `false`
  - `uncertainty_unavailable_reason` → explicit string
- Assess route wires dropout count into `assess_from_mc_samples` and notes.
- Frontend `presentHazardIntervals` + `AssessResultModal` never render zero-width bands as CIs.
- Checkpoint `ssri-model-1c8de63cd3` was **not** altered; no artificial dropout injected.

### Objective 2 — Durable acquisition evidence
- New `ssri_model.api.assessment_evidence` writes under `assessments/{id}/acquisition/`:
  - `feature_stack.npy` (full 13-channel tensor)
  - `acquisition_evidence.json` (channels/order, query-pixel vector, validity/NoData, provenance, CRS/transform/grid, AOI/pixel, checkpoint id/SHA, artifact checksums)
  - `query_pixel_vector.json`
- Atomic writes + SHA-256 checksums.
- Mirrored to existing R2 bucket via `mirror_assessment_acquisition_evidence` (**no overwrite**; same `ssri-production` bucket).
- Authenticated retrieval:
  - `GET /api/v1/assess/history/{id}/evidence`
  - `GET /api/v1/assess/history/{id}/evidence/tensor`
- History detail rematerializes `assess_response.json` from R2 when local FS is empty; evidence status distinguishes **historical gaps** from future artefacts.

## 2. Tests

| Suite | Result |
|-------|--------|
| `tests/test_uncertainty.py` (zero dropout / zero variance / stochastic / serialization) | Pass |
| `tests/test_assessment_evidence.py` (13-ch serialize, checksum, R2 mirror, recovery after local loss, historical gap) | Pass |
| `tests/test_durable_storage.py` | Pass |
| Frontend `lib/uncertaintyIntervals.test.ts` | Pass (full `npm test`: 98 pass) |

## 3. Production deployment

| Item | Status |
|------|--------|
| Commit | `dd4caaa` on `main` |
| Render API OpenAPI | Evidence routes present |
| Uncertainty honesty on **new** assesses | Live with deployed code |
| Stored historical CIs for `assess-63a666e677fff95c` | Unchanged zero-width in persisted JSON (not rewritten) |

### Objective 3 — Retrieval verification (`assess-63a666e677fff95c`)

Operator JWT refreshed via existing Supabase auth workflow.

| Check | Result |
|-------|--------|
| History response | **200** |
| Point estimates | subsidence 0.588 / landslide 0.525 / sinkhole 0.487 |
| Persisted CIs in stored response | Still zero-width `[x,x]` (historical artefact; not fabricated rewrite) |
| `acquisition_evidence` on history | `available=false`, `historical_gap=true`, explicit non-recoverable detail |
| `GET .../evidence` | **400** with message that historical feature values cannot be fabricated |
| `GET .../evidence/tensor` | Unavailable (same historical gap) |
| `GET .../spatial` | **200** GeoTIFF |
| GeoTIFF | EPSG:32631; 30/−30 m affine; **74×74**; NoData **-9999** |
| Query pixel | row **37**, col **37** |
| Object storage | `persisted=true`; spatial under `assessments/assess-63a666e677fff95c/subsidence_probability.tif` |
| Channel metadata | 13 names in `conditioning_features.channel_names` (not a durable tensor) |

## 4. Historical evidence that cannot be recovered

| Artefact | Recoverable without fabrication? |
|----------|----------------------------------|
| History / assess response | **Yes** |
| Spatial GeoTIFF geometry + NoData | **Yes** |
| Checkpoint SHA-256 | **Yes** — `d912027e…e5d004` |
| 13-channel **names** (metadata) | **Yes** |
| `acquisition_evidence.json` / query-pixel **values** | **No** |
| Durable `feature_stack.npy` in R2 | **No** |
| Invented samples at (37,37) | **Forbidden** |

## 5. Remaining operator check

Run one **new** live assess after this deploy and confirm:
- hazard profiles use `uncertainty_intervals_available=false` with a reason (no zero-width bands in UI)
- `acquisition/` artefacts + R2 mirror under `assessments/{id}/acquisition/`
- `NOT_VALIDATED` unchanged; checkpoint unchanged
