# Hazard event catalogs (source / target)

Downloaded inventories and derived `catalog.jsonl` files live here.

## Layout

- `usgs_landslide_v3/` — USGS Landslide Inventories US v3 (CC0)
- `bgs/` — placeholder until license/access resolved
- `iffi/` — placeholder until license/access resolved
- `african_target/` — candidate transfer evaluation sets

Raw zips may be large; prefer gitignore for `**/raw/` and large extracts.
Do not commit full `catalog.jsonl` or source CSVs (GitHub rejects files over 100 MB).
Keep `manifest.json` and small provenance files in git; download/build catalogs locally.
Never commit fabricated labels.
