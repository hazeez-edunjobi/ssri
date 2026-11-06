# UPLOAD_CAP_REPORT — remove 250k CSV row cap

**Branch:** `fix/upload-line-cap` (from `origin/staging/ssri-shell-rc1`)  
**Not merged to main. Not deployed.**

---

## Where the cap was (VERIFIED)

| Item | Detail |
|------|--------|
| Location | `model/src/ssri_model/manual_training/csv_import.py` — former `MAX_CSV_ROWS = 250_000` in `_parse_csv` |
| What it counted | **CSV data rows** (DictReader iterations), not tiles, not zip entries, not bytes |
| Paths affected | **Shared classic / platform CSV import** (`convert_csv_dataset` → platform `/api/v1/platform/datasets/.../versions` and any caller of CSV convert). **Not** an Earth Engine pixel tile limit (`EE_SAMPLE_SAFE_PIXEL_LIMIT` is unrelated). |
| Release shell `/shell` | Uploads **Stage 2.5 zip** via `ingest_zip_bytes` — **no row cap**. Only a **byte** cap applied (was 500 MiB hard-coded). |
| Cause | **Our code**, not Render/nginx/proxy. No infra body-size setting found for this 250k figure. |

---

## What changed

1. **`SSRI_UPLOAD_MAX_ROWS`** (new) — optional positive int; **default unset = no row limit**. Enforced in streaming `iter_csv_rows`.
2. **`SSRI_UPLOAD_MAX_BYTES`** (new) — default **1073741824 (1 GiB)**. Shared helper `reject_if_upload_too_large` used by CSV convert, classic zip ingest, and platform upload. Oversize → **HTTP 413** with a readable message (`UPLOAD_TOO_LARGE`).
3. CSV parse **streams** row-by-row into point maps (no full `list[dict]` of every row).
4. Validator rules, spatial-split logic, minimums, and gates **unchanged**.
5. Legacy flag-off behaviour: row cap removed on the shared CSV path (it was never flag-gated). Byte default raised 500 MiB → **1 GiB** on that shared path.

### Legacy paths whose limits changed

| Path | Before | After |
|------|--------|-------|
| `manual_training/csv_import.py` | Hard `MAX_CSV_ROWS = 250_000`; no byte check | Unlimited rows (optional `SSRI_UPLOAD_MAX_ROWS`); byte check via `reject_if_upload_too_large` |
| `manual_training/ingest.py` | Hard `MAX_UPLOAD_BYTES = 500 MiB` | Shared `upload_max_bytes()` default **1 GiB** |
| `platform/service.py` | Hard `MAX_UPLOAD_BYTES = 500 MiB`; HTTP 400 | Shared default **1 GiB**; HTTP **413** |
| `api/routes/training.py` | Upload errors → 400 | `UPLOAD_TOO_LARGE` → **413** |
| `release_shell/routes.py` | Upload errors → 400 | `UPLOAD_TOO_LARGE` → **413** |

Module: `model/src/ssri_model/manual_training/upload_limits.py`.

---

## Config variables and defaults

| Variable | Default | Meaning |
|----------|---------|---------|
| `SSRI_UPLOAD_MAX_ROWS` | unset / empty → **unlimited** | Optional CSV row ceiling |
| `SSRI_UPLOAD_MAX_BYTES` | `1073741824` (1 GiB) | Upload payload byte ceiling |

---

## Tests (VERIFIED)

| Matrix | Result |
|--------|--------|
| Flag **OFF** | **132 passed** (93 + 9 DeepSlide + 21 shell + **9** new upload-cap tests) |
| Flag **ON** | **132 passed** |
| New coverage | 250 001 and 1 000 000 SYNTHETIC rows process past size check; streaming generator (not a list); byte oversize → **413** on platform and classic training upload |
| `scripts/verify.py` | `{"pass": true, "report": "...\\poc\\release_shell\\outputs\\verify_report.json"}` |

---

## Rehearsal (SYNTHETIC — VERIFIED)

Script: `poc/release_shell/scripts/rehearse_upload_cap.py`  
Output: `poc/release_shell/outputs/upload_cap_rehearsal/rehearsal.json`

| Step | Result |
|------|--------|
| CSV 641×391 = **250 631** rows | Convert **~10.4 s**, status `FEATURE_LAYER_ONLY` (single Z layer — expected) |
| Peak RSS | **~330 MB** |
| `/shell` upload | **200** in ~0.45 s |
| `/shell` validate | **200** in ~0.67 s (`can_train: true`, overall WARN) |
| `/shell` train start | **202** in ~0.21 s |

**Slow?** Neither validation nor training **start** was slow at this SYNTHETIC size. Full 13-channel 250k+ cell grids would use more memory/time (point maps + stack); byte cap and streaming mitigate unbounded row lists. Host/proxy limits above the app may still truncate very large POSTs — check those if 413 appears before our handler.

---

## Risks

- Point/grid structures still scale with cell count (streaming removes the **row-list** blow-up, not the grid itself).
- Default 1 GiB may exceed some reverse-proxy limits; set `SSRI_UPLOAD_MAX_BYTES` down or raise the proxy to match.
- Optional `SSRI_UPLOAD_MAX_ROWS` can re-impose a row ceiling for ops that want one.

---

## Upload size and memory guidance (SYNTHETIC measure, 2026-11-06)

**VERIFIED, LOCAL CPU, SYNTHETIC data — NOT geological truth.**
Script: `poc/release_shell/scripts/measure_upload_profile.py`
Output: `poc/release_shell/outputs/measure_upload_profile/profile.json`

The profile builds a Stage 2.5 dataset of **9 distinct 5° blocks × 3 tiles ×
128 × 128 = 442,368 cells** (≥ the 300,000-cell / ≥8-block requirement), uploads
it as a ZIP, validates, then runs the release-shell training job. **Each
release-shell training job trains all three evaluation seeds (42/43/44)**, so the
`train wall` column is per job; the first job of a schema includes process warm-up.

| Schema | Channels | Cells | Blocks | Tiles | ZIP MiB | Upload s | Validate s | Train wall s (per job, 3 seeds) | Peak RSS MB |
|--------|---------:|------:|-------:|------:|--------:|---------:|-----------:|--------------------------------:|------------:|
| v1 | 13 | 442,368 | 9 | 27 | 0.47 | 0.81 | 1.19 | 52.7 / 35.6 / 33.3 | **451.9** |
| v2 | 16 | 442,368 | 9 | 27 | 0.56 | 0.93 | 1.38 | 37.3 / 36.2 / 37.1 | **424.2** |

- **Validation** is ~1.2–1.4 s at this size (and `can_train: true`, `overall: WARN`
  for the synthetic tiles).
- **Training** is ~33–53 s per job (three seeds) at `epochs=1, batch_size=2` on
  CPU; per seed that is roughly **11–18 s**.
- **Peak RSS** was ~**425–455 MB** for the whole single process (FastAPI
  TestClient + torch + 3-seed train + evaluate). This is a **lower bound** for a
  real host: it excludes container overhead and real-data variance.

### Why bytes are a weak proxy for memory

The synthetic tiles compress extremely well (near-linear gradients), so a
442k-cell dataset is only ~0.5 MiB zipped. **Real 13/16-channel rasters will be
several times larger for the same cell count.** Memory scales with **cell count
and channel count**, not primarily with ZIP bytes:

- 442,368 cells × 16 ch × 4 bytes ≈ 28 MB of raw feature data, but torch + the
  process baseline dominates the measured ~450 MB.
- Treat ~450 MB as the **floor for one training process** at this size; a worker
  container should be sized with headroom above it.

### Recommended `SSRI_UPLOAD_MAX_BYTES`

| Context | Recommendation | Rationale |
|---------|----------------|-----------|
| Local / dev | `1073741824` (1 GiB) — current default | Fine on a laptop; the byte cap is a backstop, memory is the real limit |
| Small CPU host (e.g. 1 GB–2 GB RAM) | **`536870912` (512 MiB)** and cap concurrency at 1 training job | Keeps a too-large ZIP out early; a 512 MiB ZIP of real rasters is far more than the 442k cells that already used ~450 MB |
| Large ZIP uploads expected | Raise `SSRI_UPLOAD_MAX_BYTES`, but first raise worker RAM and check the reverse proxy body limit | Proxy/413 appears **before** our handler if the proxy limit is lower |

The exact number is a **judgement call, not a measured threshold**: what was
measured is ~450 MB peak for ~0.44M cells in one process. Size RAM from cells and
channels, keep concurrency at 1 training job per worker, and use
`SSRI_UPLOAD_MAX_BYTES` only as an early rejection guard.

---

## Branch tip (VERIFIED)

`9bb643024b318087c4cb528a1cf56fd11a581020` (`origin/fix/upload-line-cap`)

Author/committer: `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>`. No `Co-authored-by` trailers.
