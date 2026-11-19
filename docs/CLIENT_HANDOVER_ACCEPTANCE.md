# SSRI client handover acceptance

Status: local acceptance exercise for coordinate accuracy and client-owned CSV training.
Scientific model validation remains separate. Deployment is out of scope for this document.

## Gate A — Coordinate accuracy

### Lifecycle (authoritative paths)

1. MapLibre `/dashboard` click → WGS84 `event.lngLat` (`frontend/app/dashboard/page.tsx`).
2. State: `{ latitude, longitude }` via named fields (`frontend/lib/coordinates.ts`).
3. Request: `POST /api/v1/assess` with `point.latitude` / `point.longitude` (`frontend/lib/api.ts`).
4. Backend validates ranges (`ssri_model.api.routes.assess.GeoPoint`).
5. Live AOI: `point_bbox` (±0.01°) → UTM grid via `build_grid_spec_from_aoi` (zone from bbox centre; Lagos ≈ EPSG:32631 by formula).
6. Response includes `location_provenance` (submitted WGS84, acquisition bbox, model-grid CRS, pixel row/col).

### CRS contract

| Surface | CRS |
|---------|-----|
| Map display | Web Mercator |
| Assess request point | EPSG:4326 named lat/lon |
| Live feature stack | Computed UTM |
| Offline `.npy` | Point used for region gating only; tensor is not re-sampled from the click |

### Acceptance notes

- Demo mode still ignores real rasters; provenance is geometric only.
- Live acquisition requires `SSRI_LIVE_ACQUISITION_ENABLED` and configured DEM/GEE/geophysics.
- A ±0.01° window is acquired, not a single pixel sample of the click centre alone.

## Gate B — Client-owned CSV training → assessment

### Supported training CSV (account `/training`)

- All 13 Stage 2.5 channels + label column (or zip of per-layer `X,Y,Z` + `labels.csv`).
- Declared CRS required (no guessing).
- Labels: `subsidence` / `landslide` / `sinkhole` / ints `0|1|2` / nodata `-1`.
- Feature-only CSV (e.g. Abeokuta `X,Y,Z`) → `FEATURE_LAYER_ONLY`; **labels are never invented**.
- Manifest stamps `channel_schema_version=v1` and `channel_names`.

### Product flow

1. Upload labelled CSV under `/training` with CRS.
2. Validate → start training (platform job; epochs from payload, default 5).
3. Open `/models/{id}` → **Promote for assessment**.
4. `/dashboard` prefills the active registry checkpoint → assess.

### Release shell

- Training datasets remain Stage 2.5 ZIP.
- Point-grid CSV = feature layer / overburden apply.
- Label inventory can be summarised and applied onto tiles via  
  `POST /api/v1/release-shell/datasets/{id}/labels/apply` (no fabricated labels).

## Known limitations

- Interactive column-mapping UI is still limited (aliases + exact `x/y/z/label`).
- Classic live acquisition remains 13-channel; schema v2 is shell/apply path.
- Abeokuta CRS/units remain client-owned unknowns until confirmed.
- Training success ≠ scientific validation (`NOT_VALIDATED`).
