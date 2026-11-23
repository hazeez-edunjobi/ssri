# SSRI — Client lineament & overburden data audit (read-only)

**Date:** 2026-11-20  
**Mode:** READ-ONLY — no inference, checkpoint, acquisition, or git push changes.  
**Question:** Do we already have client-supplied data for lineaments / overburden usable as live AOI inputs?

---

## Executive finding

| Need | Client-supplied file found? | Live AOI ready? |
|------|----------------------------|-----------------|
| Lineament vectors (for density/distance) | **No** | **No** |
| Precomputed `lineament_density` raster | **No** | **No** |
| Precomputed `lineament_distance` raster | **No** | **No** |
| Overburden thickness / depth grid | **One candidate CSV** — meaning/CRS **unconfirmed** | **Not without client answers** |

**Only material client geology candidate in-repo:** `sheet 260_Abeokuta.csv` (single-layer X,Y,Z point grid). Prior SSRI inspection treated it as a **possible** overburden layer but explicitly left Z meaning, units, CRS, negatives, and gaps as **client-owned unknowns**. No lineament GeoJSON/shapefile/GPKG from the client was found in the repository or under `Documents\MrBusoye` name search.

Do **not** replace this with external catalogs until the client confirms (or supplies) the missing answers/files.

---

## Search scope (evidence)

Searched:

- Repo root and `data/` (`catalogs`, `datasets`, `geophysics`, `outputs_demo`)
- `poc/release_shell/` (client inspect outputs, handoff docs, synthetic templates)
- Filename patterns: `*lineament*`, `*overburden*`, `*abeokuta*`, `*260*`, `*fault*`, `*.geojson`, `*.gpkg`, `*.shp`
- Docs/handover: `CLIENT_CSV_FINDINGS.md`, `CLIENT_QUESTIONS.md`, `CLIENT_HANDOVER_ACCEPTANCE.md`, feature-integration report
- Parent folder name match under `Documents\MrBusoye` for lineament/overburden/abeokuta/260_/fault

Not searched as authoritative client deposits: opaque cloud buckets, email attachments outside disk, production Render volumes (not mounted here).

---

## Dataset inventory

### A. `sheet 260_Abeokuta.csv` — **CLIENT CANDIDATE (overburden? UNKNOWN)**

| Field | Evidence |
|-------|----------|
| **1. Filename / location** | `c:\Users\LENOVO\Documents\MrBusoye\ssri\sheet 260_Abeokuta.csv` (~10 143 316 bytes). Working copy: `poc/release_shell/outputs/client_csv_inspect/260_abeokuta_COPY.csv`. Audit docs: `poc/release_shell/CLIENT_CSV_FINDINGS.md`, `poc/release_shell/outputs/client_csv_inspect/findings.json`, `poc/release_shell/handoff/CLIENT_QUESTIONS.md`. |
| **2. Format** | CSV, comma-delimited, header `X,Y,Z`. **308 153** data rows. |
| **3. What it measures** | **UNKNOWN.** Header does not name the quantity. Client questions file asks whether Z is overburden thickness, depth to bedrock, elevation, or other. |
| **4. Geographic coverage** | Projected X∈[−163 800, −107 800], Y∈[777 400, 833 500] (map units). Named “Abeokuta” in filename only — not a verified geographic footprint in WGS84. Regular 100-unit spacing; **not** a full rectangle (**7 129** missing cells of 561×562). Gaps clustered (4 components). |
| **5. CRS / resolution** | **CRS UNKNOWN** (not in file). Prior unit-sanity run **assumed** `EPSG:32631` for a shell check only — that assumption is **not** client-confirmed (`abeokuta_overburden_unit_sanity.json`). Spacing **100** (same units as X/Y). |
| **6. Nodata / missing** | No classic −9999 sentinel observed. **7 129** lattice gaps (not filled). **11 250** negative Z values (min ≈ −212.76, max ≈ 221.47) — meaning UNKNOWN (valid vs sentinel). |
| **7. Schema support** | Can be fed to shell **overburden apply only if** client declares thickness (m) and CRS. **Does not** provide `lineament_density` or `lineament_distance`. If Z is depth-to-interface, it must **not** be stored as `overburden_thickness`. |
| **8. Live AOI acquisition** | **Not as-is.** Needs CRS + measurement type + units + gap/negative policy. Even then, coverage is a local projected grid around Abeokuta-scale extents — not a global live catalog. Outside that grid → unavailable. |
| **9. Conversion / preprocessing** | Declare CRS; confirm thickness vs depth; decide negatives; treat gaps as NoData (do not interpolate unless client instructs); resample onto AOI/model grid via existing `overburden/apply` path for offline tiles. |

Unit-sanity when *hypothetically* labelled `overburden_thickness` + EPSG:32631: overall **WARN**, `can_train: false` (feature layer only), negative-value and gap warnings — see `poc/release_shell/outputs/abeokuta_overburden_unit_sanity.json`.

---

### B. Lineament client data — **NOT FOUND**

| Field | Evidence |
|-------|----------|
| **1. Filename / location** | None. Client handoff explicitly asks whether lineament vectors exist (`CLIENT_QUESTIONS.md` §5). Feature integration report: “Abeokuta / client CRS-units still client-owned”; GeoJSON apply exists in code, but **no client GeoJSON on disk**. |
| **2–9** | N/A — cannot audit format/coverage/CRS. Cannot support density/distance until vectors (or precomputed rasters) are supplied. |

Repo vector search for `*.geojson` / `*.gpkg` / `*.shp` under the project (excluding tooling) returned **no client lineament files** in the completed portion of the scan; catalogs under `data/catalogs` are **USGS landslide** inventories, not lineaments/overburden.

---

### C. `SYNTHETIC_overburden.csv` — **NOT CLIENT DATA**

| Field | Evidence |
|-------|----------|
| **Location** | `poc/release_shell/outputs/hazard_factors_v2_rehearsal/SYNTHETIC_overburden.csv` |
| **Format** | Synthetic X,Y,Z rehearsal grid (filename prefix `SYNTHETIC_`) |
| **Use** | Test/rehearsal only — **do not** treat as client geology or live AOI source |

Related: `poc/release_shell/templates/SYNTHETIC_stage25_v2_template.zip` — synthetic Stage 2.5 v2 template, not client supply.

---

### D. USGS / geophysics holdings — **NOT client lineament/overburden**

| Asset | Why excluded from this audit’s “client geology” claim |
|-------|------------------------------------------------------|
| `data/catalogs/usgs_landslide_v3/*` | Landslide point/polygon catalogs for training geography — not lineament density/distance or overburden |
| `data/datasets/usgs_landslide_featurestacks/**` | Stage stacks / labels for landslide research — not client Abeokuta conditioning |
| `data/geophysics/processed/*.tif` | Gravity/magnetics (WGM/EMAG) — already Stage 2.5 v1 channels |

These are useful SSRI inputs but **do not** satisfy the lineament/overburden client-data question.

---

## Mapping to schema-v2 channels

| Channel | Client asset capable of populating it? |
|---------|----------------------------------------|
| `lineament_density` | **No** client file found (needs vectors → derive, or a density raster) |
| `lineament_distance` | **No** client file found |
| `overburden_thickness` | **Maybe** `sheet 260_Abeokuta.csv` **if** client confirms thickness in metres + CRS; currently blocked by UNKNOWN semantics |

---

## Implications for live AOI (no implementation in this pass)

1. **Cannot** enable automatic live acquisition of lineaments from existing client deposits — none present.  
2. **Cannot** safely wire Abeokuta CSV into live assess until CRS/units/measurement/negatives/gaps are answered.  
3. Existing 13-channel checkpoints and live v1 inference must remain unchanged (per gate).  
4. Next step after answers: offline shell apply for Abeokuta AOI training/reporting; lineaments still require a new client file or approved catalog.

---

## Open client questions (still blocking)

From `poc/release_shell/handoff/CLIENT_QUESTIONS.md` (unchanged, still valid):

1. What does Z measure? Units? Thickness vs depth?  
2. CRS (EPSG/WKT)? Why are X values negative?  
3. Are 7 129 gaps intentional?  
4. How to treat negative Z?  
5. Is there lineament vector data (GeoJSON/shp/gpkg) + CRS?

---

## Conclusion

Client-supplied geology currently available on disk is **one unconfirmed single-layer CSV** (`sheet 260_Abeokuta.csv`), suitable for investigation as overburden **only after confirmation**. **No** client lineament density/distance source was located. Do not source external replacements until these gaps are closed or the client states the data will not be provided.
