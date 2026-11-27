# SSRI — Assessment Auditability and Uncertainty Integrity

**Date:** 2026-11-27  
**Reference assessment:** `assess-63a666e677fff95c`  
**Checkpoint:** `ssri-model-1c8de63cd3` (SHA-256 `d912027e17ed532687f9d2a2c74fd3c18ca8c812ae49107d939ade19dde5d004`)  
**Science posture:** `NOT_VALIDATED` unchanged.

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
- Authenticated retrieval (after deploy):
  - `GET /api/v1/assess/history/{id}/evidence`
  - `GET /api/v1/assess/history/{id}/evidence/tensor`
- History detail rematerializes `assess_response.json` from R2 when local FS is empty; evidence status distinguishes **historical gaps** from future artefacts.

### Objective 3 — Historical assessment retrieval (executed)
Operator JWT refreshed via existing Supabase auth workflow; production calls succeeded.

| Check | Result |
|-------|--------|
| `GET /api/v1/assess/history/assess-63a666e677fff95c` | **200** — response recovered |
| Point estimates | subsidence 0.588 / landslide 0.525 / sinkhole 0.487 |
| CIs on live prod (pre-deploy code) | Zero-width bands still present (`[x,x]`); `uncertainty_intervals_available` absent |
| Acquisition evidence JSON/tensor | **404 Not Found** on prod (routes not deployed yet); historically never persisted |
| `GET .../history/.../spatial` | **200** GeoTIFF 19 521 bytes |
| GeoTIFF CRS / transform / size / NoData | EPSG:32631; affine 30/−30 m; **74×74**; NoData **-9999** |
| Query pixel | row **37**, col **37** (matches model_grid) |
| Object storage | Summary `persisted=true`; spatial object under `assessments/assess-63a666e677fff95c/subsidence_probability.tif` in existing R2 bucket |
| Channel contract in response | 13 names present under `conditioning_features.channel_names` (metadata only — not a durable tensor) |

Local audit artefacts (not committed): `data/outputs/audit_assess-63a666e677fff95c/`.

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
| Working-tree implementation | Complete |
| Commit / push of this milestone | In progress with this report |
| Render API image including uncertainty + evidence routes | **Pending** until deploy finishes after push |
| New live assesses writing `acquisition/` + R2 mirror | Requires deployed API |
| Prod CI honesty (`null` + reason instead of zero-width) | Requires deployed API |

Until that deploy lands, production continues to emit zero-width CIs for `dropout=0.0` and returns 404 for evidence routes.

## 4. Historical evidence that cannot be recovered

For `assess-63a666e677fff95c` specifically:

| Artefact | Recoverable without fabrication? |
|----------|----------------------------------|
| `assess_response.json` / history detail | **Yes** — retrieved 200 after auth refresh |
| Spatial GeoTIFF (CRS, transform, 74×74, NoData −9999) | **Yes** — retrieved via authenticated `/spatial` |
| Checkpoint SHA-256 | **Yes** — `d912027e…e5d004` |
| 13-channel names (metadata) | **Yes** — in response `conditioning_features` |
| `acquisition_evidence.json` / query-pixel sample values | **No** — feature did not exist at creation time |
| Durable `feature_stack.npy` in R2 | **No** — full tensor was not mirrored historically |
| Invented channel values at (37,37) | **Forbidden** — not fabricated |

Pixel (37,37) is geometry-only confirmation on the live 30 m grid — not reconstructed feature samples.

## 5. Operator follow-ups after deploy

1. Confirm Render API is on the commit that includes this milestone.
2. Re-check history for `assess-63a666e677fff95c`: evidence endpoints should return an explicit **historical unavailable** payload (not fabricated tensor).
3. Run one new live assess; confirm `acquisition_evidence` in the response, R2 keys under `assessments/{id}/acquisition/`, and UI copy “Confidence intervals unavailable…”.
4. Keep `NOT_VALIDATED`; do not promote or retrain `ssri-model-1c8de63cd3` for this work.
