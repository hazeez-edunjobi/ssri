# Feature schema v2 — lineaments & overburden

**Status:** platform contract (NOT scientific validation).  
**Default training/assess schema remains v1 (13 channels)** unless the dataset/checkpoint declares v2.

## Schemas

| Version | Channels | Notes |
|---------|----------|-------|
| **v1** | 13 Stage 2.5 names | Legacy / flag-off default |
| **v2** | v1 + `overburden_thickness`, `lineament_density`, `lineament_distance` | Explicit only |

Order is fixed. Assess rejects mismatched checkpoint/input schemas with a plain-language error — never fills missing channels.

## Overburden

- Quantity for the v2 channel is **thickness** (≥ 0 preferred; negatives → UNIT_SANITY WARN).
- **Depth-to-interface** must use layer name `depth_to_bedrock` / measurement_type `depth_to_interface`.
- SSRI **does not** silently convert depth → thickness.
- Declare **units** (do not assume metres). Abeokuta CRS/units remain unconfirmed until the client answers.

Apply into a dataset: `POST /api/v1/release-shell/datasets/{id}/overburden/apply`.

## Lineaments

- Input: GeoJSON LineString / MultiLineString.
- Method: density = segment length in a square window / window area (`m/m²`); distance = min distance to a segment (m). Default window 500 m.
- CRS must be declared; coordinates must already match tile projected metres.
- Apply: `POST /api/v1/release-shell/datasets/{id}/lineaments/apply` rewrites every `feature_stack.npy` to 16 channels and updates `manifest.json`.

## Uploads

- **No default application byte cap.** Set `SSRI_UPLOAD_MAX_BYTES` only when infrastructure needs an explicit backstop.
- ZIP bombs still blocked via uncompressed size, file count, and compression ratio env vars.
- Large uploads stream to disk before extract.

## Compatibility

- v1 checkpoints load as before.
- v2 checkpoints require 16-channel inputs.
- Existing 13-channel ZIPs remain valid; applying lineaments/overburden promotes them to v2 on disk.
