# SSRI — Abeokuta Sheet 260 TMI (Publication-Guided)

**Date:** 2026-11-23  
**Status:** Local CRS correction + magnetic processing implemented and tested

## Authoritative definitions

| Field | Meaning |
|---|---|
| X | Easting (UTM) |
| Y | Northing (UTM) |
| Z | Total Magnetic Intensity (TMI) |

| CRS role | EPSG |
|---|---|
| Source (original CSV) | EPSG:32632 (UTM Zone 32N) |
| Processing | EPSG:32631 (UTM Zone 31N) |
| Display | EPSG:4326 (WGS84) |

Earlier EPSG:4326-as-source declaration is retained in metadata history as **superseded**.

## Verified on `sheet 260_Abeokuta.csv`

| Check | Result |
|---|---|
| Rows | 308,153 |
| Source extent | X ≈ [-163800, -107800], Y ≈ [777400, 833500] |
| → EPSG:32631 | E ≈ [500000, 555219], N ≈ [773750, 829048] |
| → EPSG:4326 | lon ≈ [3.00, 3.50], lat ≈ [7.00, 7.50] |
| Spacing | ~100 m regular lattice |
| Negative TMI | Preserved (min ≈ -212.8) |
| Stage 2.5 injection | Forbidden (`can_train=false`, `NOT_VALIDATED`) |

## Application workflow

1. Upload CSV at `/geological`
2. **Apply Abeokuta TMI metadata** (publication-guided preset)
3. Validate (runs CRS verification 32632→32631→4326)
4. Process TMI grid (metres in EPSG:32631)
5. Run individual magnetic ops: RTE, Gaussian, analytic signal, FVD, FHD, tilt, RAPS
6. Inspect previews, history, CRS roles on the dataset page

## Publication parameters (explicit / configurable)

- Inclination 11.04°
- Declination 3.52°
- Average IGRF 32,576 nT
- Gaussian central wavelength 2,000 m
- Gaussian σ 0.5

## Modules

- `model/src/ssri_model/geological/abeokuta_tmi.py`
- `model/src/ssri_model/geological/abeokuta_crs.py`
- `model/src/ssri_model/geological/magnetic_processing.py`
- API: `GET/POST /api/v1/geological/datasets/{id}/magnetic`, derived file route

## Scientific boundary

TMI products are geophysical conditioning layers for comparison with published qualitative themes (sedimentary / transition / basement; NE–SW trends). They are **not** hazard labels and must not enter the 13-channel Stage 2.5 model. Exact paper-map reproduction is not claimed without original processed grids.

Follow-up scientific QA (gridding reconciliation, RTE clip diagnostics, Gaussian modes, RAPS chart, provenance): see `SSRI_ABEOKUTA_SHEET260_SCIENTIFIC_QA_REPORT.md`.
