# EIGEN-6C4 Gravity Acquisition

**Status:** Provider interface ready; **raster not yet on disk** in this environment.  
**Do not relabel WGM2012 as EIGEN-6C4.**

## PRD requirement

The SSRI FeatureStack gravity channel should use **EIGEN-6C4** (GFZ/GRGS combined
global gravity field model) when available.

Current production/default path remains **WGM2012 Complete Spherical Bouguer**
via `GRAVITY_DATA_PATH`, explicitly labelled `wgm2012_bouguer` in manifests.

## Environment contract

| Variable | Purpose |
|----------|---------|
| `SSRI_GRAVITY_SOURCE` | `wgm2012_bouguer` (default) or `eigen6c4` |
| `GRAVITY_DATA_PATH` | Local GeoTIFF for the default/WGM path |
| `EIGEN6C4_DATA_PATH` | Local GeoTIFF derived from EIGEN-6C4 (required when source=`eigen6c4`) |
| `SSRI_REPO_ROOT` | Optional; relative paths resolve here (not process CWD) |

If `SSRI_GRAVITY_SOURCE=eigen6c4` and `EIGEN6C4_DATA_PATH` is missing or the file
does not exist, loading **fails closed** with `GeophysicsConfigError` /
`GeophysicsDataError`. There is **no silent fallback** that keeps the EIGEN label.

See also: `docs/GEOPHYSICS_CONFIGURATION.md` (live Docker paths, Lagos vs CONUS rasters).

**Acquisition status (2026-09-09):** EIGEN-6C4 raster still **not present** under
`data/geophysics/`. Live Lagos assessments use WGM2012 Lagos clips with
`gravity_provider=wgm2012_bouguer`.

## How to acquire a real EIGEN-6C4 grid

1. Open the ICGEM calculation service: https://icgem.gfz.de/calcgrid  
2. Select model **EIGEN-6C4**.  
3. Choose a gravity functional appropriate for SSRI (e.g. **simple Bouguer gravity anomaly** or gravity anomaly — document which functional you export).  
4. Set a geographic grid covering the intended training/inference domain (at minimum CONUS and/or African AOIs) at a documented resolution (e.g. 0.05°–0.1°).  
5. Download the grid; convert to a single-band EPSG:4326 GeoTIFF (`float32`, nodata documented).  
6. Place under e.g. `data/geophysics/processed/eigen6c4_bouguer_<region>.tif`.  
7. Set:
   ```text
   SSRI_GRAVITY_SOURCE=eigen6c4
   EIGEN6C4_DATA_PATH=<absolute path to that GeoTIFF>
   ```
8. Rebuild FeatureStacks so sample manifests record `gravity_provider=eigen6c4`.

**Note (2026-09):** ICGEM calcgrid may refuse new calculations under high load.
Coefficients/metadata: https://dataservices.gfz-potsdam.de/icgem/showshort.php?id=escidoc:1119897

## Code entry points

- `ssri_model.data.geophysics.LocalGeoTIFFProvider.load_gravity`
- `ssri_model.data.geophysics.resolve_gravity_source_label`
- FeatureStack manifest field `sources.gravity_provider` via `resolve_gravity_source_label()`

## Scientific honesty

Until an EIGEN-6C4 raster is acquired and configured, FeatureStacks must continue
to report **WGM2012** (or whatever path `GRAVITY_DATA_PATH` actually contains).
WGM2012 is a related but **not identical** gravity product to EIGEN-6C4.
