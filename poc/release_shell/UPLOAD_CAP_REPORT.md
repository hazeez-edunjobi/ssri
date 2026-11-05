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

## Branch tip (VERIFIED)

`9bb643024b318087c4cb528a1cf56fd11a581020` (`origin/fix/upload-line-cap`)

Author/committer: `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>`. No `Co-authored-by` trailers.
