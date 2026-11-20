# SSRI — Scientific Data Readiness Report

**Date:** 2026-11-21  
**Scope:** Source-by-source readiness for Stage 2.5 hazards and schema-v2 geological channels  
**Rule:** No fabricated observations; client unknowns remain blocked  

---

## Executive summary

SSRI can run **research / Stage 2.5 engineering** workflows with existing terrain, remote-sensing, and geophysics pipelines, but **cannot** honestly claim a complete, scientifically activated geological conditioning product for client AOIs until:

1. Client confirms Abeokuta CSV CRS, Z meaning, units, negatives, gaps, and usage permission.  
2. Client provides lineament vectors (or formally waives them).  
3. Production checkpoint identity and evaluation evidence are available outside empty-git `.pt` state.  
4. Schema-v2 training/eval completes a defensible acceptance gate (currently **BLOCKED**).

---

## Hazard label / training data

| Source | Role | Readiness | Limitations |
|--------|------|-----------|-------------|
| USGS landslide feature stacks (`data/datasets/...` per scorecard) | Landslide research stacks | Partial — historical n=240 v3 cited in scorecard | Not Abeokuta-specific; spatial leakage / transfer not re-proven here |
| Pseudo-absence / split audits | Training hygiene | Documented historically | Must be re-audited for any new v2 train |
| Sinkhole / subsidence labels | Stage 2.5 classes | Contract exists (`LabelClass`) | Geographic coverage and label quality must be verified per campaign — not asserted complete in this report |

**Acquisition need:** Campaign-specific labelled inventories with CRS, date, hazard class, and spatial train/holdout plan before any production promotion.

---

## Feature stack channels (v1 = production)

| Channel | Typical source class | Readiness | Notes |
|---------|---------------------|-----------|-------|
| elevation → valley_depth | DEM / derived terrain | Pipeline exists (`build_feature_stack`) | Dependent on OpenTopography/GEE config |
| ndvi, ndwi, clay, iron | Optical RS | Pipeline exists | Temporal window in acquisition |
| gravity | Local geophysics rasters | Partial | Scorecard: EIGEN-6C4 missing; WGM2012 labelled honestly |
| magnetics | Local geophysics | Partial | Path/config dependent |

Live AOI acquisition does **not** pull geological catalogue layers.

---

## Schema-v2 geological channels

| Channel | Client / catalogue status | Activate for science? |
|---------|---------------------------|------------------------|
| `overburden_thickness` | Candidate: `sheet 260_Abeokuta.csv` — **CRS/Z/units unconfirmed** | **No** until client answers |
| `lineament_density` | No client GeoJSON/shp/gpkg found | **No** |
| `lineament_distance` | Same | **No** |
| depth_to_bedrock (not a v2 stack channel) | Must stay distinct; never auto-map to thickness | Enforce in catalogue (implemented) |

Evidence: `SSRI_CLIENT_LINEAMENT_OVERBURDEN_DATA_AUDIT.md`, `SSRI_ABEOKUTA_PROVISIONAL_INTEGRATION_PREP.md`.

### Client confirmation checklist (Abeokuta CSV)

Required before any scientific activation:

1. CRS (EPSG/WKT) — do **not** assume EPSG:32631.  
2. Z measurement: thickness vs depth-to-bedrock vs other.  
3. Z units.  
4. Validity of negative Z.  
5. Coordinate spacing units.  
6. Missing lattice cell policy (NoData — no silent interpolate).  
7. Usage / redistribution permission.

---

## Derived vs measured

| Product | Class |
|---------|--------|
| Terrain indices (slope, TWI, …) | Derived from DEM |
| Lineament density/distance | Derived from vectors via documented window |
| Overburden thickness raster on tile | Resampled from declared point grid (NN within spacing tolerance) |
| Client CSV Z | Measured or interpreted — **unknown until declared** |

---

## Acquisition specification (if data missing)

| Need | Spec |
|------|------|
| Overburden | Regular or declared irregular policy; CRS; thickness (m); NoData sentinels; coverage polygon |
| Lineaments | LineString/MultiLineString; CRS; GeoJSON or GPKG/shp ZIP; empty allowed with WARN |
| Gravity / magnetics | GeoTIFF; CRS; units; nodata; documented product name |
| Labels | Point/polygon inventory; hazard enum matching Stage 2.5; date optional; CRS |

Do **not** download substitute geology and present it as client truth.

---

## Readiness verdict

| Domain | Verdict |
|--------|---------|
| Engineering pipelines for features | Ready for research use (config-dependent) |
| Client geological conditioning | **Not ready** |
| Schema-v2 scientific production | **Not ready** (Phase 6 BLOCKED) |
| Honest product claims | Require “NOT_VALIDATED” and susceptibility framing |
