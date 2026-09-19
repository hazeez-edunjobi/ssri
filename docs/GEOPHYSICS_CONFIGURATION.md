# SSRI Geophysics Configuration

**Authority:** `docs/SSRI_MASTER_COMPLETION_PROMPT.md`  
**Last verified:** 2026-09-09

## Provider contract

| Role | Env | Live / engineering default |
|------|-----|----------------------------|
| Gravity source selector | `SSRI_GRAVITY_SOURCE` | `wgm2012_bouguer` (engineering) |
| WGM2012 Bouguer GeoTIFF | `GRAVITY_DATA_PATH` | Required when source is WGM |
| EIGEN-6C4 GeoTIFF | `EIGEN6C4_DATA_PATH` | Required when source is `eigen6c4` |
| Magnetics (EMAG2v3 UC4km) | `MAGNETIC_DATA_PATH` | Always required for live stacks |
| Path root (optional) | `SSRI_REPO_ROOT` / `SSRI_DATA_ROOT` | Relative path resolution |

**PRD gravity provider:** EIGEN-6C4  
**Engineering / current live Lagos path:** WGM2012 (`gravity_provider = wgm2012_bouguer`)  
**Never** silently substitute WGM2012 when EIGEN-6C4 is requested.  
**Never** relabel WGM2012 as EIGEN-6C4.

## Path resolution

1. Absolute paths are used as configured.
2. Relative paths resolve against `SSRI_REPO_ROOT` / `SSRI_CONFIG_ROOT`, else the discovered repository root, else `SSRI_DATA_ROOT` / `/data` — **not** the process CWD alone (`/app` in containers).
3. Missing files raise `GeophysicsDataError` with provider, resolved path, env var, expected format, and whether fallback is allowed (`false`).

## Docker Compose (live API / worker)

Compose **hardcodes** container paths (host `GRAVITY_DATA_PATH` must not leak Windows paths into Linux containers):

- `GRAVITY_DATA_PATH=/data/geophysics/processed/lagos_gravity_wgm2012_bouguer.tif`
- `MAGNETIC_DATA_PATH=/data/geophysics/processed/lagos_magnetic_emag2v3_uc4km.tif`
- `SSRI_GRAVITY_SOURCE=wgm2012_bouguer` (overridable)
- Volume: `../data/geophysics` → `/data/geophysics:ro`

Lagos AOI live assessments require the **Lagos clips** (CONUS rasters do not cover Lagos).

## Datasets on disk (this checkout)

| File | Product | Coverage |
|------|---------|----------|
| `data/geophysics/processed/lagos_gravity_wgm2012_bouguer.tif` | WGM2012 Bouguer | Lagos clip ~2.5–4.5°E, 5.5–7.5°N |
| `data/geophysics/processed/lagos_magnetic_emag2v3_uc4km.tif` | EMAG2v3 UC 4 km | Same Lagos clip |
| `data/geophysics/processed/wgm2012_bouguer_conus.tif` | WGM2012 Bouguer | CONUS (USGS training) |
| `data/geophysics/processed/emag2v3_conus.tif` | EMAG2v3 | CONUS |
| EIGEN-6C4 | — | **Not acquired** |

Provenance for Lagos clips: `data/geophysics/provenance/lagos_geophysics_provenance.json`.

## DEM fallback (separate from geophysics)

1. OpenTopography success → `opentopo_<product>`
2. OpenTopography rate-limit / auth / missing-key (when `SSRI_DEM_PROVIDER=auto`) → GEE COP30
3. GEE failure → explicit failure

Compose note: do **not** put `OPENTOPOGRAPHY_API_KEY: ${OPENTOPOGRAPHY_API_KEY:-}` in the
`environment:` block — empty Compose interpolation overrides `env_file: ../.env` and blanks
the key. The secret must come from `env_file`.

Geophysics has **no** automatic product fallback.

## FeatureStack provenance

Manifest `sources` records the **actual** providers used:

- `dem` — from last successful DEM acquisition
- `gravity_provider` — `wgm2012_bouguer` or `eigen6c4` (never invented)
- `magnetic_provider` — `emag2v3_uc4km`

## Acquisition status

| Provider | Status |
|----------|--------|
| WGM2012 (Lagos + CONUS) | Available locally |
| EMAG2v3 | Available locally |
| EIGEN-6C4 | **Blocked** — see `docs/EIGEN6C4_ACQUISITION.md` |
