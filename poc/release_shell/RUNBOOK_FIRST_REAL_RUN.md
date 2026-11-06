# RUNBOOK — first real run (client data → trained model)

Audience: the owner/operator (non-developer is fine). Everything here is
**local-first**; nothing in this file pushes, deploys, or spends money.

If you prefer clicking to typing, the `/shell` page covers most of this.
`OWNER_API_GUIDE.md` is the API fallback.

**Hard rule:** SSRI outputs are **relative susceptibility rankings** and stay
`NOT_VALIDATED`. Never use them for insurance, engineering, safety, or
emergency decisions.

---

## 0. Put the client files in one folder, then check readiness

```text
python poc/release_shell/scripts/check_site_readiness.py "C:\path\to\client\files" --block-size-km 5
```

This prints which of the five owner inputs are present and what to ask the
client for. It never trains and never guesses (unclear = "CAN'T TELL").

The five owner inputs:

1. CRS (coordinate reference system)
2. Layer meaning + units
3. Labels per hazard (subsidence, landslide, sinkhole)
4. Lineament vectors (optional, for schema v2)
5. Enough tiles/blocks (default minimums: 300 tiles, 8 blocks, 3 held-out blocks)

---

## 1. Confirm the CRS (do not assume)

- Ask the client for the **EPSG code or the full definition**.
- Do not treat a guessed CRS as fact. The current Abeokuta demo file is
  **ASSUMED FOR TEST** only (`EPSG:32631`) and is labelled as such.
- If X values are negative, that is a strong hint the data is in a projected
  (metre) CRS, not lat/long — confirm which.
- Every layer upload requires a CRS. The API refuses a layer with no CRS.

For one layer, check CRS + units before a full upload:

```text
POST /api/v1/release-shell/layers/validate
form: file=<point-grid CSV>, layer_name=overburden_thickness, crs=EPSG:32631
```

A single layer is `FEATURE_LAYER_ONLY` — it never trains. Unit-sanity warnings
(for example negative `overburden_thickness`) are surfaced here.

---

## 2. Map layers to channels

The model reads a fixed channel order. Two schemas exist:

| Schema | Channels | Able to include |
|--------|----------|-----------------|
| **v1** | 13 | the historical Stage 2.5 stack |
| **v2** | 16 | v1 + `overburden_thickness`, `lineament_density`, `lineament_distance` |

- `depth_to_bedrock` is **not** silently treated as `overburden_thickness`.
  Say which one you have; they are different quantities.
- Names are matched through `KNOWN_LAYER_ALIASES` (e.g. `overburden`, `thickness`
  → `overburden_thickness`). Confirm the mapping; do not rely on a guess.
- The channel order must match the schema exactly. A mismatch names the missing
  channels instead of failing silently.

---

## 3. Upload labels

Label inventory (per hazard):

```text
POST /api/v1/release-shell/labels/inventory
form: file=<CSV or GeoJSON>, crs=<EPSG>, date_column=<optional>
```

Labels are class indices: `subsidence=0`, `landslide=1`, `sinkhole=2`,
nodata `-1`. Name label files per hazard so the readiness check can find them.

---

## 4. Lineaments (optional, v2 only)

```text
POST /api/v1/release-shell/lineaments/inspect
form: file=<GeoJSON LineString/MultiLineString>
```

Reports segment count and bounding box. Use it to sanity-check the vectors
before deriving `lineament_density` / `lineament_distance`.

---

## 5. Choose the block size for the site

Blocks are whole, non-overlapping squares used to make the train/validation/test
split **geographically honest** (tiles from the same block never straddle
train/test). A **buffer** then drops training tiles that sit too close to a
held-out block.

- Default block size is **5°** (~550 km). That is meant for continent-scale data.
- A single ~56 km site is much smaller than one 5° block, so you **must** use a
  **local block size in km**: `SSRI_RELEASE_SHELL_BLOCK_SIZE_KM`.
- Local blocks (< 5°) make the model **"local evidence only; not validated
  beyond this site"**. That limitation is carried into the output on purpose.

### Abeokuta site (≈56 km × 56 km) — **ESTIMATE**

Computed by running the real `split_by_blocks` on a synthetic 2 km grid over a
56 km site (≈7.155°N, 3.345°E). Treat as an **estimate**, not a survey.

| Block size | Approx distinct blocks | Works with buffer up to | Note |
|-----------|------------------------|--------------------------|------|
| 5 km | ~132 (≈12 × 11) | ~5 km | most blocks; fails at ≥10 km buffer |
| 10 km | ~42 (≈7 × 6) | ~10 km | 26 train blocks |
| 20 km | ~12 (≈4 × 3) | ~25 km | only 7 train blocks |
| 5° (default) | 1 | — | cannot split; site is inside one block |

Key consequences:

- The **default 50 km buffer cannot be used** on a 56 km site — the split ends up
  with no training tiles. Set a buffer well below the site size.
- Smaller blocks give more blocks but tolerate a smaller buffer. Larger blocks
  tolerate a bigger buffer but leave few training blocks.
- At 5 km the buffer is only ~5 km, so a big share of training tiles near
  holdouts get dropped. Expect fewer training tiles than the raw block count.

Suggested start for a site this size: **5 km blocks, buffer 5 km** (or
**10 km blocks, buffer 10 km** if you need a wider buffer).

---

## 6. Validate

```text
POST /api/v1/training/datasets                 {"name":"abeokuta-1","notes":"..."}
POST /api/v1/release-shell/datasets/{id}/upload   file=<Stage 2.5 ZIP>
POST /api/v1/release-shell/datasets/{id}/validate
```

Read `validation.overall`, each check's PASS/WARN/FAIL, and per-hazard
ENABLED/DISABLED. **If `can_train` is false, stop.**

---

## 7. Train (3 seeds)

```text
POST /api/v1/release-shell/jobs
{"dataset_id":"...","epochs":3,"seeds":[42,43,44],"device":"cpu"}
GET  /api/v1/jobs/{job_id}
```

Training runs three seeds on purpose — one seed is not evidence.

---

## 8. Read the evaluation and the gates

```text
GET /api/v1/release-shell/models/{model_id}/evaluation
```

Per hazard per seed you get ROC/AUC and the gap over the slope baseline
(ΔAUC). Then an **aggregate gate**:

| Gate string | Meaning |
|-------------|---------|
| `evaluated` | demonstrated skill above the slope baseline, confirmed across seeds |
| `trained, no demonstrated skill beyond slope` | model trained but did not beat the baseline |
| `trained, unconfirmed across seeds` | mixed across seeds; not trustworthy yet |
| `insufficient labelled data` | not enough positive pixels on held-out blocks |
| `no_trained_model` | nothing trained yet (assess returns this before any train) |

**Gate needs ≥ 2 of 3 seeds `evaluated`** to be considered evaluated.

---

## Interpreting "trained, no demonstrated skill beyond slope"

This is the **honest, likely** first result. It means:

- the pipeline ran end to end and produced a model;
- that model did **not** rank hazard locations better than a simple slope
  baseline on held-out geography.

It is **not** a code failure. It usually means the features/labels are too thin
or too few to learn from. Do not lower the gate to make it pass.

---

## 9. What to do next (in order of what usually helps most)

1. **More area** — one 56 km site is small; add neighbouring sites so the split
   has more blocks and the "local evidence only" caveat can be lifted.
2. **More labels** — especially more positive pixels per hazard, spread across
   blocks. `insufficient labelled data` is a labels problem, not a model problem.
3. **Simpler model** — try schema v1 (13 channels) first; only add v2 channels
   once v1 has demonstrated some skill.
4. **Bigger buffer / different block size** — re-check the estimate table above.

---

## 10. Assess (after a checkpoint exists)

```text
POST /api/v1/training/models/activate   {"model_id":"..."}
POST /api/v1/assess   {"checkpoint":"...","features":"...","point":{"latitude":..,"longitude":..}}
```

- `score` is **null unless** the gate is `evaluated` **and** the point is inside
  the training region. Otherwise you get a reason string
  (`no_trained_model`, `outside_training_region`, the gate string, …).
- Outside the trained area → `outside_training_region`. Do not read a score
  there, because there is none.
