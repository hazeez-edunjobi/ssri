# Gate A — Independent inventory candidates

Evaluated for constructing a DeepSlide-compatible (14-band) labelled georeferenced evaluation set **outside** Landslide4Sense study areas (Iburi JP, Kodagu IN, Gorkha NP, Taiwan).

Independence is geographic, not filename-based: a different download of L4S-family chips is **not** independent.

| Candidate | Provenance / access | Coverage vs L4S | Labels | Licence | Independent spatial-block eval? | Decision |
|-----------|---------------------|-----------------|--------|---------|-----------------------------------|----------|
| Landslide4Sense validation HDF5 | IARAI competition pack under `poc/landslide4sense/data/validation` | Same Asia study-area family as train | Raster scars in chips | Competition terms | No CRS; not geo-independent | Reject |
| SSRI `usgs_landslide_featurestacks/v3` | Project build from USGS points + SSRI stacker | CONUS — outside L4S Asia | Point / pseudo-absence | USGS public + project | Geography OK; **13-ch SSRI** contract | Reject as-is; reuse **points only** |
| USGS Landslide Inventories v3 | [USGS data release](https://www.usgs.gov/data/landslide-inventories-across-united-states-ver-30-february-2025); local `data/catalogs/usgs_landslide_v3/catalog.jsonl` | CONUS / US territories | Vector points (and polygons in source); dates and confidence flags vary | USGS public domain | Yes if rasterized + STAC stacks built | **Selected** (points + 40 m buffer) |
| Hokkaido / Iburi (karstCand) | GitHub open dataset | **Iburi = L4S AOI** | Scar labels | Open (repo) | Leakage vs L4S | Reject |
| Nepal U-Net scars (Zenodo 3688363) | Zenodo | Nepal; Gorkha L4S risk | Scar GeoTIFFs | CC (Zenodo) | Geography risky; **RGB only** | Reject |
| Sen12Landslides (HF) | Hugging Face `paulhoehn/Sen12Landslides` | Multi-region | Labels + S2/DEM | Dataset card | Partial; **10 S2 bands**, no native slope; multi-100GB | Reject (band invent / cost) |

## Selected construction path

**USGS v3 inventory points (CONUS)** + **Planetary Computer STAC** Sentinel-2 L2A (B01–B12) + Copernicus DEM GLO-30 → slope, 128×128 @ 10 m chips.

- Presence: confidence-filtered catalog points, event year ≥2017 when dated, buffered **40 m**.
- Absence: catalog pseudo-absences **in the same 5° block** when available; otherwise **synthesized** uniform samples in-block ≥5 km from any USGS presence point.
- Split: entire 5° blocks held for evaluation only; threshold fixed at **0.5** (not tuned here).

### Documented limitations (not silently ignored)

1. Point + buffer ≠ scar polygons — chip-level detection is primary; pixel metrics vs buffers are secondary.
2. Sentinel-2 L2A often lacks B10 → **zero-filled** and flagged per chip.
3. Terrain is **Copernicus DEM**, not ALOS PALSAR used in L4S training.
4. Imagery is nearest low-cloud scene in a temporal window around inventory date, not guaranteed event-day.
5. Synthesized absences are inventory-gap proxies, not field-verified non-landslides.
