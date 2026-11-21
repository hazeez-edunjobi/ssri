# SSRI Demo Mode (presentation / local UI)

**Environment variable:** `SSRI_DEMO_MODE`  
**Default:** `false`  
**Config field:** `APIConfig.demo_mode` (loaded via `APIConfig.from_env()`)

## Purpose

`SSRI_DEMO_MODE=true` is for **development / presentation walkthroughs only**:

* local UI demonstrations
* environments where live geospatial providers are unavailable

When enabled (and the API environment is **not** production/staging),
`POST /api/v1/assess` returns **deterministic** assessment payloads from
`ssri_model.api.demo_assessment` and does **not** call Google Earth Engine,
OpenTopography, Sentinel-2, DEM download, or local geophysics rasters.

`SSRI_DEMO_MODE=false` is required for real assessment (live or offline FeatureStack +
checkpoint inference). The scientific pipeline is unchanged when demo mode is off.

## Production / staging hard-disable

If `SSRI_API_ENVIRONMENT` is `production` or `staging`, `APIConfig` **forces**
`demo_mode=false` even when `SSRI_DEMO_MODE=true` is set. There is no silent
production path that returns catalogue scores.

## Frontend production integrity

Production Next.js builds never activate Assessment Preview UI, even if
`GET /api/v1/ready` reports `demo_mode: true` (misconfigured API). Local
walkthroughs require **both**:

1. Server `SSRI_DEMO_MODE=true` (development environment)
2. `NEXT_PUBLIC_SSRI_ALLOW_PRESENTATION_DEMO=true` on the frontend

## Accepted values

`true` / `false` / `1` / `0` (also `yes` / `on` for true).

## Safety

* Controlled **only** by the server environment (plus the production hard-disable).
  Clients cannot enable demo mode via request body fields (`extra=forbid` on the
  assess schema).
* Demo values are **presentation placeholders**. They must never be interpreted as
  scientific validation metrics, experiment results, or field-validated probabilities.
* Demo payloads are **not persisted** as production assessments.
* Failed live inference must not fall back to catalogue scores.
* Catalogue scenarios: `GET /api/v1/demo/scenarios` (404 when demo mode is off).

## Operator note

Set `SSRI_DEMO_MODE=false` and restart the API after any local presentation.
Confirm `GET /api/v1/ready` → `demo_mode: false` before client-facing use.
