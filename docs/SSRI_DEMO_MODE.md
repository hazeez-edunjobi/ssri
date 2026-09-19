# SSRI Demo Mode (presentation / local UI)

**Environment variable:** `SSRI_DEMO_MODE`  
**Default:** `false`  
**Config field:** `APIConfig.demo_mode` (loaded via `APIConfig.from_env()`)

## Purpose

`SSRI_DEMO_MODE=true` is for:

* presentations
* local UI demonstrations
* environments where live geospatial providers are unavailable

When enabled, `POST /api/v1/assess` returns **deterministic** assessment payloads from
`ssri_model.api.demo_assessment` and does **not** call Google Earth Engine,
OpenTopography, Sentinel-2, DEM download, or local geophysics rasters.

`SSRI_DEMO_MODE=false` is required for real assessment (live or offline FeatureStack +
checkpoint inference). The scientific pipeline is unchanged when demo mode is off.

## Accepted values

`true` / `false` / `1` / `0` (also `yes` / `on` for true).

## Safety

* Controlled **only** by the server environment. Clients cannot enable demo mode via
  request body fields (`extra=forbid` on the assess schema).
* Demo values are **presentation placeholders**. They must never be interpreted as
  scientific validation metrics, experiment results, or field-validated probabilities.
* Do not enable in production scientific deployments.

## Operator note

API responses intentionally omit any user-facing “demo” label so the existing UI
renders normally. Server logs may record that the configured demo provider was used.
