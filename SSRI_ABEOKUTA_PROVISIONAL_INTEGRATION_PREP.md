# SSRI — Provisional preparation for `sheet 260_Abeokuta.csv`

**Mode:** Planning / prep only  
**Date:** 2026-11-20  
**Production inference:** **unchanged** (Stage 2.5 **v1 / 13 channels**)  
**Activation:** **disabled** until client confirmations below are answered  

Config sketch (hypotheses only):  
`poc/release_shell/configs/abeokuta_provisional.hypotheses.json`

---

## Hypotheses (NOT confirmed facts)

| # | Hypothesis | Status |
|---|------------|--------|
| H1 | Z is overburden-related **depth or thickness** | Unconfirmed |
| H2 | X/Y are **projected** coordinates | Unconfirmed (plausible from magnitudes) |
| H3 | CRS may be **EPSG:32631** | Unconfirmed (planning candidate only) |
| H4 | 100-unit spacing may be **100 m** | Unconfirmed |

**Do not** hardcode H1–H4 into live assess, worker env defaults, or checkpoint training until the client confirms each item in writing.

---

## 1. Validation workflow (CSV)

Reusable tooling already exists; wire them behind an **explicit** provisional config, never silent defaults in production.

### Steps

1. **Copy, don’t mutate**  
   Source: `sheet 260_Abeokuta.csv`  
   Working copy: `poc/release_shell/outputs/client_csv_inspect/260_abeokuta_COPY.csv`  
   Script: `poc/release_shell/scripts/inspect_client_csv.py`

2. **Structural inspect (fact-finding)**  
   Record: delimiter, header, row count, X/Y/Z ranges, spacing, gaps, duplicates, negative counts, sentinel-like values.  
   Output: `poc/release_shell/outputs/client_csv_inspect/findings.json`

3. **Declared-identity validation (only with explicit labels)**  
   Call release-shell `validate_point_grid_layer` **after** an operator supplies:
   - `layer_name` ∈ {`overburden_thickness`, `depth_to_bedrock`, or other declared name}
   - `crs` (EPSG/WKT)
   - `measurement_type` when overburden-related (`thickness` | `depth_to_interface`)  
   Reference test harness (assumed CRS for test only):  
   `poc/release_shell/scripts/check_abeokuta_overburden_units.py`  
   Production path must **fail closed** if CRS or measurement type is missing (`CRS_REQUIRED` / validator contracts).

4. **Gate report**  
   Emit PASS/WARN/FAIL for: CRS parse, grid regularity, gaps, unit sanity (negatives if thickness), trainable=false until full Stage 2.5 labels+channels exist.

5. **Activation gate**  
   Apply to tiles / live reporting **only if** config `activation` flips from `disabled` → `enabled` **and** all §5 confirmations are recorded. Default remains disabled.

### Pass criteria before any apply

- Client-confirmed CRS  
- Client-confirmed Z meaning + units  
- Explicit policy for negatives and gaps  
- No silent fill of missing cells  

---

## 2. Configurable CRS and units conversion

### Design rules

- CRS and units live in **config / form fields**, not code constants for production assess.  
- Hypotheses JSON may list `candidate_epsg: EPSG:32631` with `"confirmed": false`.  
- Shell already requires declared CRS for layer validate/apply (`release_shell/routes.py`).

### Proposed conversion process (when confirmed)

1. Operator sets `crs` (e.g. confirmed EPSG) and `z_units` (`m` | `ft` | other + scale).  
2. If units ≠ metres, multiply Z by an explicit `z_to_metres` factor from config (never guess).  
3. If XY must be transformed to tile CRS, use declared source CRS → target CRS via the same projected-metre assumptions as shell apply (document both CRS).  
4. If H4 is confirmed (100 m), record `grid_spacing_m=100` in provenance; if spacing is 100 “file units” ≠ metres, do **not** treat as 100 m.  
5. Persist provenance on any future apply: source path, CRS, units, measurement_type, conversion factor, hypothesis flags cleared.

### Forbidden

- Defaulting live AOI acquisition to EPSG:32631 or “Z = thickness” in API env.  
- Auto-alias `depth_to_interface` → `overburden_thickness`.

---

## 3. Missing-cell and negative-value handling strategy

### Observed (facts)

- Missing lattice cells: **7 129** (clustered)  
- Negative Z: **11 250** (min ≈ −212.76)  
- No classic −9999 sentinel observed  

### Provisional policy (for later activation — not applied now)

| Case | Strategy |
|------|----------|
| Missing XY on regular lattice | Map to **FEATURE_NODATA** (`-9999`) on target grid; **never** interpolate or zero-fill unless client documents a method |
| Negative Z + declared **thickness** | **WARN/FAIL** in validation; do not train/apply as thickness until client explains or marks as sentinel → NoData |
| Negative Z + declared **depth** | Allowed only with client confirmation that negatives are physical; else NoData |
| Ambiguous Z | Keep layer **inactive**; report `unavailable` / not used in inference |
| Partial AOI overlap | Outside coverage → unavailable/NoData; inside gaps → NoData |

This matches existing shell honesty: empty/missing science → nodata, not fabrication (`feature_apply.py` contract).

---

## 4. Lineament integration strategy

### Current state

- **No** client lineament GeoJSON/shapefile/GPKG found in-repo.  
- Schema v2 channels `lineament_density` / `lineament_distance` are derived from vectors via shell (`lineaments.py`, `.../lineaments/apply`).  
- Live v1 assess does not acquire lineaments.

### Strategy until client supplies vectors

1. Keep lineament channels **unavailable** in assess responses (already).  
2. When client provides GeoJSON (+ CRS):  
   - Inspect → apply to offline tiles only (shell).  
   - Derive density (window m/m²) and distance (m) per documented method.  
   - Empty segments → nodata rasters, not zeros.  
3. Live AOI: only after (a) mounted regional catalog or per-job upload, and (b) checkpoint/schema policy from the live-v2 plan — **out of scope for this provisional CSV prep**.  
4. Do not invent lineaments from the Abeokuta XYZ sheet (it has no line geometry).

---

## 5. Client confirmations required before activation

Must be answered before enabling any apply that could become a model input:

1. **What does Z measure?** (overburden thickness / depth to bedrock / elevation / other)  
2. **Units of Z?** (metres, feet, other)  
3. If depth: confirm separate name `depth_to_bedrock` — never silent thickness relabel.  
4. **CRS** as EPSG or full WKT/PROJ (confirm or reject EPSG:32631).  
5. Why are **X values negative**? (projection / false easting)  
6. Is spacing **100 metres** or 100 of another unit?  
7. Are **7 129 gaps** intentional mask/AOI or data loss? How should they be treated?  
8. How should **negative Z** be treated (physical vs sentinel)?  
9. Are there **lineament vectors** for the same area? Format + CRS?  
10. Permission to use this layer for **offline training/reporting only** vs any future live AOI?

Until then: `activation=disabled`, production 13-channel inference untouched.

---

## What this prep does **not** do

- No change to `build_feature_stack`, assess inference tensor, or checkpoints.  
- No retrain, deploy, or Git push.  
- No fabricated Z/lineament values.  
- No production hardcoding of EPSG:32631 or thickness.

---

## Suggested next step after client replies

Update `abeokuta_provisional.hypotheses.json`: set each hypothesis `confirmed` true/false from answers; only then run validate → optional shell overburden apply on a **non-production** dataset; keep live v1 assess as-is.
