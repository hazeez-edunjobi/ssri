# SSRI — Sheet 260 Scientific Verification & Processing QA

**Dataset:** `geo_be00a34ad6f4` (`sheet_260_Abeokuta.csv`)  
**Status:** `scientific_validation_status=NOT_VALIDATED`  
**Inspect URL:** http://localhost:3000/geological/geo_be00a34ad6f4  
**API:** http://127.0.0.1:8000  

## 1. Files changed

| Path | Change |
|---|---|
| `model/src/ssri_model/geological/magnetic_processing.py` | v1.1.0 — gridding provenance, RTE clip diagnostics, Gaussian modes, units, RAPS chart/detrend, operation catalog |
| `model/src/ssri_model/geological/service.py` | Rich provenance, source/processing lattice reconciliation, checksums, RAPS PNG |
| `model/src/ssri_model/api/routes/geological.py` | `gaussian_mode`, `rte_amplitude_clip` request fields |
| `frontend/lib/geologicalApi.ts` | Extended magnetic product types |
| `frontend/app/geological/[id]/page.tsx` | Gridding reconciliation UI, op descriptions, RAPS chart, pub vs impl params |
| `model/tests/test_magnetic_analytical_qa.py` | Analytical-surface QA suite |
| `SSRI_ABEOKUTA_TMI_INGESTION_COMPLETION.md` | Prior completion note (unchanged roles) |

## 2. Scientific issues discovered

1. **Gridding count mismatch (not a bug once explained):**  
   - Inspect `missing_lattice_cells=7129` = source unique-X×unique-Y − observations (`561×562−308153`).  
   - Processing scatter-bin NoData=`1295` on a 553×554 metre grid in EPSG:32631.  
   - Earlier nearest-neighbour reported **0 NoData** by interpolating every empty cell (fabricating measured-looking TMI).
2. **UTM warp collisions:** 3086 processing cells receive 2 observations; previously last-write-wins.
3. **RTE 10× amplitude clip** was recorded as if part of the method without clip diagnostics; it is **not** a publication parameter. For Sheet 260 with I=11.04°, **0 coefficients exceeded 10×** (clip currently inert; RMSE clipped vs unclipped = 0).
4. **Gaussian response type** (low-pass vs residual) is **ambiguous** in the publication; prior code assumed low-pass without saying so.
5. **FHD** product is THG (total horizontal gradient), not single-axis ∂T/∂x — naming was unclear.
6. **RAPS** lacked detrend/normalisation documentation, chart, and an explicit no-depth-claim.

## 3. Corrections implemented

- Scatter-bin with **observation mean** on collisions; empty cells stay NoData; interpolated cell count exposed (=0 for default).
- Explicit **gridding reconciliation** block (source lattice vs processing NoData).
- RTE: clip diagnostics (count, fraction, RMSE vs unclipped); clip flagged as implementation choice; configurable.
- Gaussian: documented low-pass default + optional `high_pass` residual mode.
- Derivatives/AS/tilt: units, Fourier conventions, atan2 tilt, NoData restore after FFT mean-fill.
- RAPS: mean detrend, power `/ (nx·ny)`, cycles/m + wavelength, chart PNG, depth claim disabled.
- Provenance: algorithm/version, checksums, pub vs impl parameters, timestamps, `NOT_VALIDATED`.

## 4. Gridding reconciliation (live dataset)

| Quantity | Value |
|---|---|
| Original observations | 308,153 |
| Source expected lattice | 315,282 |
| Source empty lattice | **7,129** |
| Processing grid | 553 × 554 = 306,362 |
| Cells from observations | **305,067** |
| Cells from interpolation | **0** |
| Cells remaining NoData | **1,295** |
| Collision cells (mean-aggregated) | 3,086 |

## 5. Before / after

| Topic | Before | After |
|---|---|---|
| Empty cells | NN → 0 NoData (interpolated) | Scatter-bin → 1295 NoData |
| Collisions | Last write wins | Mean of observations |
| RTE clip | Silent 10× | Diagnosed; 0 coeffs clipped on Sheet 260 |
| Gaussian | Implicit LP | LP default + HP residual option |
| RAPS | JSON only | Chart + units + no depth claim |
| Provenance | Thin history | Checksums, pub vs impl, gridding block |

## 6. Test results

```text
27 passed  (test_magnetic_analytical_qa + test_abeokuta_crs_magnetic + test_geological_tmi)
```

Analytical coverage: constant / sinusoid / ramp / Gaussian anomaly / missing cells / RTE clip / filter response / derivatives / RAPS calibration / Abeokuta lattice counts.

## 7. Local app status

- API listening on `http://127.0.0.1:8000` with QA payloads.
- Frontend on `http://localhost:3000`.
- Dataset page: http://localhost:3000/geological/geo_be00a34ad6f4

## 8. Remaining scientific limitations

- Exact reproduction of publication maps is **not** claimed (no original processed grids).
- FFT uses mean-fill of NoData with no zero-padding (documented implementation choice; edge ringing possible).
- Gaussian paper response remains ambiguous; both LP and residual are available.
- THG is used for “first horizontal derivative” product naming.
- RAPS does not estimate source depth.
- Geological interpretations remain comparative themes only — **NOT_VALIDATED**.
