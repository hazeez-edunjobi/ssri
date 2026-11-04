# DATA_SHEET — landslide credibility v3 corpus

## Provenance

| Item | Detail |
|------|--------|
| Presence labels | USGS Landslide Inventories (compiled catalog `data/catalogs/usgs_landslide_v3/catalog.jsonl`) |
| DEM / terrain | Copernicus DEM GLO-30 via Microsoft Planetary Computer STAC (same pipeline as v2 `build_corpus.py`) |
| Base samples | Extended from v2 corpus (`samples_near.jsonl`, `samples_far.jsonl`); v2 manifest SHA-256 `E0D31A4F…` unchanged |
| Slope-matched absences | Resampled from already-enriched NEAR+FAR absences so slope-bin frequencies match LOBO presence slope distribution (quantile bins). No new DEM fetch. Source tag `pseudo_slope_matched_resample`. |
| Sealed fresh | Catalog points in pre-registered blocks + NEAR absences; DEM-enriched |

## Licence

| Source | Licence (as used) |
|--------|-------------------|
| USGS landslide inventories | Public domain / CC0 (USGS) |
| Copernicus DEM GLO-30 | Free access via Planetary Computer; Copernicus DEM licence applies to redistribution of DEM tiles (features derived for research PoC) |

## Label type

Point inventory presence (mapped landslide locations). **Not** mapped absence of landslides. Absences are pseudo-absences under NEAR / FAR / SLOPE-MATCHED schemes.

## Positional accuracy

Inventory coordinates inherit source-specific uncertainty (often tens to hundreds of metres; some inventories coarser). DEM features use a ~1 km half-window around the point. 1 km presence thinning reduces but does not remove spatial clustering.

## Known biases

- **Mapping effort:** denser inventories where agencies mapped; sparse elsewhere → geographic coverage bias.
- **Inventory clustering:** multiple points per complex / corridor; thinning (1 km) and per-inventory caps mitigate but do not eliminate pseudo-replication.
- **Undated events:** many records lack event dates; only static predictors used (no date features).
- **Pseudo-absence:** NEAR (5–20 km) and FAR (≥20 km) are design choices, not field-verified non-landslides. SLOPE-MATCHED removes easy slope separation for the “beyond slope” test.
- **CONUS-centric:** sealed AK/HI/PR blocks largely empty in this catalog build.

## Scheme files (see `corpus/manifest.json` for SHA-256)

- `lobo_near.jsonl` — LOBO NEAR (excludes spent v2 test blocks)
- `lobo_far.jsonl` — LOBO FAR
- `lobo_slope_matched.jsonl` — LOBO presence + slope-matched absences
- `spent_v2_near.jsonl` — exploratory second look only
- `sealed_fresh.jsonl` — sealed holdout (opened once after `phase3_freeze.json`)

## Fresh holdout shortfall (VERIFIED)

Requested 7 blocks; populated 2 (`35_-105`, `40_-115`) with n=14 total after DEM. **Does not** meet Tier B minimum (≥3 blocks, ≥150 samples). Tier B path unavailable; LOBO-only decisions apply.

## Environment layers

Not attached at corpus build. Pre-registered order: land cover → precip climatology → lithology → soils. Attachment attempted only if free STAC/local files succeed; otherwise layer steps marked BLOCKED with exact error in run log / FINAL_REPORT.
