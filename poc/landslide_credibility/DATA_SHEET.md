# Data sheet — terrain-first CONUS landslide susceptibility corpus

## Provenance

| Item | Detail |
|------|--------|
| Presence labels | USGS Landslide Inventories v3 points (`data/catalogs/usgs_landslide_v3`) |
| Licence | CC0-1.0, DOI 10.5066/P14AJF8I |
| DEM | Copernicus DEM GLO-30 via Planetary Computer STAC (`cop-dem-glo-30`) |
| Features | Static terrain only (see PROTOCOL_v2); spectral/geophysics **dropped** |
| Builder | `scripts/build_corpus.py` + `config.json` |

## Label type and accuracy

- **Presence:** inventory POINT (mixed confidence; low confidence=1/2 excluded). Not scar polygons. Positional accuracy varies by source.
- **Absence (NEAR primary):** pseudo-absence inside inventory footprints, 5–20 km from nearest catalog point. Not field-confirmed.
- **Absence (FAR secondary):** ≥20 km from inventory, still in footprint.

## Construction controls

- Presence thinned to ≥1 km; source share capped ≤25%/block.
- Splits by whole 5° cells; ≥50 km train–test buffer (achieved min NN ≈54.3 km).
- Samples with >40% DEM void dropped.

## Known biases

1. **Mapping-effort bias:** inventories cluster where agencies mapped; absences in footprints mitigate but do not eliminate.
2. **Inventory clustering / storms:** mitigated by 1 km thinning + source cap; residual pseudo-replication possible.
3. **Undated events:** dated fraction reported in manifest (informational); no event-date features used.
4. **Static terrain only:** cannot capture rainfall triggers or land-cover change.

## What the model can learn

Relative ranking of points by **terrain configuration** (slope, curvature, relief, TWI, TPI, …) within mapped CONUS regions.  
Cannot learn spectral signatures, event timing, or scar geometry.

## Freeze

See `corpus/manifest.json` and `outputs/phase2_corpus_freeze.json` for SHA-256 hashes. Do not alter frozen files.
