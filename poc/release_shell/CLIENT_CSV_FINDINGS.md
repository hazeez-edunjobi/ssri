# CLIENT_CSV_FINDINGS — `sheet 260_Abeokuta.csv`

**Status:** VERIFIED from a working copy. Original not modified.  
**Copy:** `poc/release_shell/outputs/client_csv_inspect/260_abeokuta_COPY.csv`  
**Machine JSON:** `poc/release_shell/outputs/client_csv_inspect/findings.json`

## Location

| Path | Size | Notes |
|------|------|-------|
| `sheet 260_Abeokuta.csv` (repo root) | 10 143 316 bytes | **Only copy found** (search by `*abeokuta*` / `*260*`) |

## Observed structure (VERIFIED)

| Property | Value |
|----------|-------|
| Data rows | **308 153** |
| Lines (incl. header) | ~308 154 |
| Delimiter | **comma** `,` (not tab/space) |
| Header | **Present:** `X,Y,Z` |
| Columns | 3 |
| X range | −163 800 … −107 800 |
| Y range | 777 400 … 833 500 |
| Z range | −212.76 … 221.47 |
| Z mean / stdev | ~58.74 / ~32.70 |
| Z p01 / p50 / p99 | ~−42.6 / ~60.9 / ~129.3 |
| Unique X / Y | 561 / 562 |
| Spacing | **100** in X and Y (single spacing each) |
| Regularity | Spacing regular; **not** a full rectangle |
| Expected full grid | 561 × 562 = 315 282 cells |
| Missing cells | **7 129** (gaps; not silently fillable) |
| Duplicate X,Y | **0** |
| Classic nodata (−9999 etc.) | **None observed** |
| Negative Z values | Present (p01 negative) — meaning UNKNOWN |

## Corrections vs first-look notes

Earlier glance suggested headerless tab/space rows. On this file: **header is present** and delimiter is **comma**. Values ~55–57 appear only in the first Y-row; the full Z distribution is much wider.

## CRS / units / meaning

| Field | Status |
|-------|--------|
| CRS | **UNKNOWN** — not in file |
| Units of Z | **UNKNOWN** |
| What Z measures | **UNKNOWN** (thickness vs depth vs elevation vs other) |
| Hypothesis (labelled UNKNOWN) | Coordinates *may* belong to a Nigerian projected grid (possibly Transverse Mercator centred near 4.5°E without false easting). **Not confirmed.** |

## Questions the client must answer

1. What does the **Z / value** column measure?
2. What are the **units** (metres, feet, other)?
3. Is it **overburden thickness**, **depth to bedrock**, elevation, or something else? (If depth-to-bedrock, we will store it under a separate declared name — never silently relabel as thickness.)
4. What is the **CRS** as an EPSG code or full WKT/PROJ definition?
5. Are the **7 129 missing grid cells** intentional (mask/AOI) or data loss?
6. How should **negative Z** values be treated (valid measurements vs sentinel)?
