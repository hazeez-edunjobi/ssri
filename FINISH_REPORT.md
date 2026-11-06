# FINISH_REPORT — SSRI platform "ready for first real upload" (RC2, LOCAL ONLY)

**Branch:** `feature/hazard-factors-v2`
**Verification ran on committed tip:** `8819c814d07e562f4221c6c298d8905895d0c5d2` (all tests/hashes in §5). This report was committed afterwards; for the current tip run `git rev-parse HEAD` (do not pin — it goes stale).
**Identity (intended):** `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>` · no Co-authored-by trailers
**Remote:** **NOT pushed.** No PR opened. No deploy. No money spent.
**Flag:** `SSRI_RELEASE_SHELL` stays default **OFF**; flag-off behaviour unchanged.

**Label key used below:** **VERIFIED** = reproduced locally with the exact command/artefact shown · **REPORTED** = executed but evidence is a summary, not re-runnable here · **UNKNOWN** = not established.

---

## 0. Status at a glance

| Task | Status | Headline evidence |
|------|--------|-------------------|
| 1 Close open verifications | **DONE** | tip line unpinned; Abeokuta negative-Z now surfaces `UNIT_SANITY WARN` through the real validator (overall=WARN, min −212.76, 11 250 negatives); per-seed gates + aggregate from SYNTHETIC v2 log |
| 2 `/shell` UI coverage | **DONE** | 3 new backend routes + "Prepare owner inputs" panel; full UI-vs-API table in §4 |
| 3 Host readiness (read-only) | **DONE** | lockfile ok; `poetry install --with deepslide --dry-run --no-root` EXIT=0; upload/memory guidance measured; `smoke_staging.py` production guard VERIFIED |
| 4 Runbook + tooling | **DONE** | `RUNBOOK_FIRST_REAL_RUN.md`; `check_site_readiness.py`; Abeokuta block ESTIMATE |
| 5 Human-dependent docs | **DONE** | 4 docs under `poc/release_shell/handoff/` |
| 6 Final verification | **DONE** | see §5 (full suites OFF/ON, curated, verify.py, frozen hashes, identity, diffs, clean status) |
| Deliverable `FINISH_REPORT.md` | **DONE** | this file |

Nothing is **NOT DONE**. Two **PARTIAL / REPORTED** caveats are called out in §7 (fresh-venv `poetry install` sandbox limitation; committer-identity mismatch).

---

## 1. Branch, commits, workspace

Commits added for this master task (local only):

| SHA | Subject |
|-----|---------|
| `21c873f` | Route real Abeokuta overburden CSV through validator; unpin stale tip SHA |
| `b2e324d` | Add owner-input surfaces to release-shell UI and API (CRS, labels, lineaments, settings) |
| `e4875ca` | Fix block_id truncation collapsing km-based local blocks into integer-degree buckets |
| `8819c81` | Add host-readiness smoke/measure scripts, first-real-run runbook, handoff docs |

Diff vs local `main` (VERIFIED):

```text
66 files changed, 7579 insertions(+), 231 deletions(-)
```

---

## 2. Task 1 — Close open verifications (DONE)

### 1a — Stale tip line fixed (VERIFIED)
`poc/release_shell/HAZARD_FACTORS_V2_REPORT.md` no longer pins a SHA; it instructs `git rev-parse HEAD`. See [HAZARD_FACTORS_V2_REPORT.md](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/poc/release_shell/HAZARD_FACTORS_V2_REPORT.md#L7-L13).

### 1b — Abeokuta real file through the real validator, negative-Z visible (VERIFIED)
The **real** Abeokuta point-grid file is now routed through `release_shell.validator.validate_point_grid_layer` (not just the CSV parser). Declared as layer `overburden_thickness` with **`EPSG:32631` (ASSUMED-FOR-TEST — not client-confirmed)**.

| Result | Value |
|--------|-------|
| overall | **WARN** |
| status / trainable | FEATURE_LAYER_ONLY / False |
| grid | 561 × 562, spacing 100 × 100 |
| value min / max | **−212.76** … 221.47 |
| negatives | **11 250** |
| readable message | `UNIT_SANITY WARN: 11250 negative value(s) in layer 'overburden_thickness'` |
| gaps | WARN — 7 129 missing cell(s) |

Evidence: `poc/release_shell/outputs/abeokuta_overburden_unit_sanity.txt` / `.json` (VERIFIED). Tests added: `test_layer_validator_surfaces_unit_sanity_warn`, `test_real_abeokuta_overburden_negative_z_warns` (+46 & +16 lines in `model/tests/test_hazard_factors_v2.py`).

### 1c — Per-seed evaluation outputs + aggregate gate from SYNTHETIC v2 e2e (VERIFIED)
Source: `poc/release_shell/outputs/e2e_synthetic_v2/work/service-outputs/training/models/ssri-model-f589fdad75/release_shell_evaluation.json` (log copy: `outputs/e2e_synthetic_v2/e2e_log.json`). Per-seed gates (`42`/`43`/`44`) plus the aggregate gate are recorded in `HAZARD_FACTORS_V2_REPORT.md` §"SYNTHETIC v2 e2e". **SYNTHETIC** data — fabricated labels, not real geology.

---

## 3. Task 3 & 4 — Host readiness, runbook and tooling (DONE)

### Host readiness (read-only; no deploy)
- **Lockfile / optional group (VERIFIED):** `pyproj = "^3.6.1"` in main deps; DeepSlide is an optional group (`optional = true`; `segmentation-models-pytorch`, `h5py`). `poetry install --with deepslide --dry-run --no-root` → **EXIT=0**, resolves `pyproj 3.7.2`.
- **Docker (`model/Dockerfile`):** Python 3.11-slim, `POETRY_VERSION=1.8.5`, CPU-only torch 2.5.1, `poetry export --only main` → DeepSlide intentionally excluded from the image (not needed for release-shell/assess). NOTE: proxy body limit sits above our 1 GiB handler; torch pinned 2.5.1 in-image vs 2.13.0 in dev.
- **Upload-size & memory guidance (VERIFIED, SYNTHETIC, LOCAL CPU):** appended to `poc/release_shell/UPLOAD_CAP_REPORT.md`; raw numbers in `poc/release_shell/outputs/measure_upload_profile/profile.json`.

Measured profile — SYNTHETIC, 9 blocks × 3 tiles × 128×128 = **442 368 cells**, 27 tiles:

| Schema | Ch | ZIP | upload | validate | seed 42 | seed 43 | seed 44 | peak RSS |
|--------|----|-----|--------|----------|---------|---------|---------|----------|
| v1 | 13 | 0.47 MiB | 0.81 s | 1.19 s | 52.68 s | 35.57 s | 33.26 s | **451.9 MB** |
| v2 | 16 | 0.56 MiB | 0.93 s | 1.38 s | 37.31 s | 36.18 s | 37.14 s | **424.2 MB** |

(Each release-shell training job trains all 3 seeds back-to-back; "seed" columns are per-seed wall times inside one job.)

**Why bytes are a weak proxy for memory:** peak RSS tracks *decoded raster + tile tensors*, which scale with cell count and channel count, not ZIP size. A 0.5 MiB ZIP decoded to ~442 k cells × 16 channels already needed ~0.42–0.45 GB.

**Recommended `SSRI_UPLOAD_MAX_BYTES`:**

| Target | Recommended | Rationale |
|--------|-------------|-----------|
| Dev / local | `1073741824` (1 GiB, default) | Matches handler default; no guard needed. |
| Small CPU host (≈2 GB RAM) | `536870912` (512 MiB) | Leaves headroom below measured ≈0.45 GB peak for a 442 k-cell / 16-ch job; cap the request early. |
| Large uploads | raise bytes **and** RAM | Bytes is a weak proxy; size the host by peak RSS (cells × channels), and confirm the proxy body limit is above the cap. |

Oversize → HTTP **413 `UPLOAD_TOO_LARGE`** (`model/src/ssri_model/manual_training/upload_limits.py`).

### Smoke test (VERIFIED)
`poc/release_shell/scripts/smoke_staging.py` — one command: health, `no_trained_model` assess, broken-ZIP FAIL, SYNTHETIC v1 and v2 upload→validate→train→evaluate→assess, `outside_training_region`. Production guard VERIFIED: refuses `https://ssri-api.onrender.com` unless an explicit flag is passed (exit 2).

### Runbook + readiness checker (VERIFIED)
- `poc/release_shell/RUNBOOK_FIRST_REAL_RUN.md` — readiness check, CRS confirm, layer→channel map, labels, lineaments, block-size (**Abeokuta ESTIMATE**), validate, 3-seed train, gates, assess.
- `poc/release_shell/scripts/check_site_readiness.py` — plain-language report of what's missing (CRS, layer meaning/units, labels per hazard, lineament vectors, minimum tiles/blocks); **never trains, never guesses**; always exits 0. Tested OK.
- **Bug fixed here:** `block_id` truncation collapsed km-sized local blocks into integer-degree buckets → fixed in [spatial_split.py](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/model/src/ssri_model/release_shell/spatial_split.py) + regression test (`e4875ca`).

---

## 4. Task 2 — `/shell` UI coverage (DONE)

New backend routes (`b2e324d`, in [routes.py](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/model/src/ssri_model/release_shell/routes.py)): `layers/validate`, `labels/inventory`, `lineaments/inspect`; `status` now returns `settings`. Frontend: [page.tsx](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/frontend/app/shell/page.tsx) "Prepare owner inputs" panel + [api.ts](file:///c:/Users/LENOVO/Documents/MrBusoye/ssri/frontend/lib/api.ts).

| Owner input | UI? | Where / notes |
|-------------|-----|----------------|
| ZIP upload | **UI** | Step 1 "Upload Stage 2.5 ZIP" |
| Validation report | **UI** | Step 2 (checks, hazards, can_train, re-validate) |
| Training progress | **UI** | Step 3 (polled job status/progress) |
| Evaluation report | **UI** | Step 4 (aggregate gates, per-hazard, per-block) |
| Checkpoint selection | **UI** | Step 5 (list + Select/Active) |
| Known limitations panel | **UI** | right aside (server-provided, fallback list) |
| CRS per layer | **UI** | "Check a layer (CRS + units)" — CRS is **required**, never guessed |
| Layer naming / channel mapping | **UI** | layer-name input with schema datalist + "Channel names per schema" details |
| Label inventory upload | **UI** | "Label inventory (per hazard)" — CRS required |
| Lineament vector upload | **UI** | "Lineament vectors (optional)" — GeoJSON inspect |
| Block-size setting | **API-only** | Displayed read-only in "Current settings"; set by operator env (`OWNER_API_GUIDE.md`) |
| Schema version choice | **API-only** | Displayed (default + supported); env-controlled |
| `preview_unevaluated_scores` toggle | **API-only** | Displayed (on/off); env-controlled |

**Fallback retained:** `poc/release_shell/OWNER_API_GUIDE.md` is still the documented manual path, linked in the page's "API fallback" card.

---

## 5. Task 6 — Final verification (DONE, all on committed tip `8819c81`)

| Check | Command (abbrev.) | Result |
|-------|-------------------|--------|
| Full suite FLAG **OFF** | `poetry run pytest tests -q -rs` | **703 passed, 2 skipped** in 331.34 s |
| Full suite FLAG **ON** | `SSRI_RELEASE_SHELL=true pytest tests -q -rs` | **703 passed, 2 skipped** in 241.07 s |
| Curated set | curated file list (below) | **151 passed** in 76.93 s |
| `scripts/verify.py` | `poetry -C model run python …/verify.py` | **`{"pass": true}`** |
| Frozen hashes | temp hash script | v1 `BD2A86BC` **MATCH** · v2 `5F63E362` **MATCH** · v3 `70FE823F` **MATCH** · manifest `E0D31A4F` **MATCH** |
| Diff vs `main` — frozen files | `git diff --stat main..HEAD -- <PROTOCOL*>, manifest.json` | **EMPTY** |
| Diff vs `main` — checkpoints | `git diff --stat main..HEAD -- "*.pt"` | **EMPTY** |
| Authors | `git log main..HEAD --format="%an <%ae>"` | all `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>` |
| Co-authored-by trailers | `git log … \| Select-String Co-authored-by` | **0** |
| Working tree | `git status` — sources | **clean** (only the two new RC2 evidence logs, now committed) |

**Skipped (2) — named** (both in `model/tests/test_infrastructure_integration.py`, `:65` and `:71`):
- `test_readiness_with_real_services`
- `test_postgres_job_lifecycle`

Both skip unless `SSRI_INTEGRATION_TESTS=1` is set. Command message: *"Set SSRI_INTEGRATION_TESTS=1 to run distributed integration tests"*.

**Counts reconciliation**
- Baseline expectation was **143 curated / 695 full**. This branch **adds tests**, so the measured numbers grew:
  - Curated **143 → 151** (+8): `+46` and `+16` lines in `model/tests/test_hazard_factors_v2.py` (overburden unit-sanity + `block_id` regression), `+93` lines in `model/tests/test_release_shell_validator.py` (owner-input surfaces).
  - Full **695 → 703** (+8), same cause.
- `verify.py` internal steps (VERIFIED): `new_tests` 26 passed · `assess_93` 93 passed · `deepslide_9` 9 passed · `no_trained_model` → `200 no_trained_model`.

Curated command (VERIFIED, 151 passed):

```text
pytest tests/test_api_assess.py tests/test_api_assess_audit.py tests/test_demo_mode_assess.py
  tests/test_model_architecture.py tests/test_multitask_model.py tests/test_inference.py
  tests/test_evaluation_metrics.py tests/test_training_metrics.py
  tests/test_release_shell_softmax_contract.py tests/test_release_shell_spatial_split.py
  tests/test_release_shell_assess.py tests/test_release_shell_validator.py
  tests/test_release_shell_assess_contract.py tests/test_release_shell_assess_route.py
  tests/test_release_shell_jobs_result.py tests/test_upload_row_cap.py
  tests/test_hazard_factors_v2.py
  poc/landslide4sense/integration/test_deepslide_engine.py -q --tb=line
```

> Note on the deepslide test path: `poetry -C model run …` changes cwd to `model/`, so the test path must be given absolute or as `../poc/...`. Passing `poc/...` relative fails with "No such file".

---

## 6. Task 5 — Human-dependent artefacts (prepared, not faked)

Under `poc/release_shell/handoff/`:
- `CLIENT_QUESTIONS.md` — what only the client can answer (Z meaning, units, thickness-vs-depth, CRS/EPSG, intentional gaps, negative-Z handling).
- `OWNER_STATUS.md` — owner-facing readiness status.
- `REVIEW_REQUEST.md` — reviewer ask.
- `REMAINING_WORK_REGISTER.md` — 14-row table (owner, blocker, cheapest next step).

Abeokuta block-count **ESTIMATE** (≈56 km × 56 km site; **estimate only**):

| Block size | ≈ blocks (with default 50 km buffer) |
|------------|--------------------------------------|
| 5 km | ≈ 132 |
| 10 km | ≈ 42 |
| 20 km | ≈ 12 |

The default 50 km buffer is **infeasible for a 56 km site** — the buffer is a decision captured in `REMAINING_WORK_REGISTER.md`.

---

## 7. Open items / caveats

1. **Committer-identity mismatch (REPORTED, not fixed).** `user.name`/`user.email` are correct, but the environment exports `GIT_COMMITTER_NAME=trae-solo-agent` / `GIT_COMMITTER_EMAIL=solo-agent@trae.ai`. Result: the 4 newest commits (`21c873f`, `b2e324d`, `e4875ca`, `8819c81`) have **author** `hazeez-edunjobi` but **committer** `trae-solo-agent <solo-agent@trae.ai>` (14 older branch commits have the correct committer). **No Co-authored-by trailers exist (0).** If committer must also be the owner, unset those env vars and `git commit --amend --reset-author` (or rebase), or re-commit before pushing.
2. **Fresh-venv `poetry install` in this sandbox (REPORTED).** A full clean-room `poetry install` could not complete here; evidence used was `poetry … --dry-run` EXIT=0 plus a fresh **pip** venv where `h5py`, `segmentation-models-pytorch`, and `torch` import OK. Full clean-room install should be confirmed on the host.
3. **Frozen Abeokuta CRS is ASSUMED-FOR-TEST** (`EPSG:32631`), not client-confirmed — see `CLIENT_QUESTIONS.md`.
4. **UI API-only surfaces** (block size, schema version, preview toggle) remain env-controlled by design; a UI control is listed in `REMAINING_WORK_REGISTER.md`.
5. **SYNTHETIC only.** All measured/gate data here is SYNTHETIC; no real labels or model skill are claimed. Status stays `NOT_VALIDATED`.

---

## 8. Exact commands for YOU to push and open a PR

This agent did **not** push. When you are ready (from the repo root):

```powershell
cd C:\Users\LENOVO\Documents\MrBusoye\ssri
git checkout feature/hazard-factors-v2
git log --oneline main..HEAD
git status                          # expect clean

# (optional) fix committer identity on the 4 newest commits before pushing:
# Remove-Item Env:GIT_COMMITTER_NAME -ErrorAction SilentlyContinue
# Remove-Item Env:GIT_COMMITTER_EMAIL -ErrorAction SilentlyContinue
# git rebase -i main   # or: git rebase --exec 'git commit --amend --no-edit --reset-author' main

# push your branch
git push -u origin feature/hazard-factors-v2
```

Then open the PR (example, adjust base as needed):

```powershell
gh pr create --base main --head feature/hazard-factors-v2 `
  --title "SSRI RC2: finish release shell, owner inputs, host readiness" `
  --body "Local-only finish of Tasks 1-6. See FINISH_REPORT.md. Flag stays default OFF."
```

If your host requires it, the PR can be opened in the browser instead:

```text
https://github.com/<org>/<repo>/compare/main...feature/hazard-factors-v2
```

---

## 9. Stop conditions observed

- Frozen hash mismatch → **none** (all MATCH).
- Existing tests regress → **none** (full suite 703/2 both OFF and ON; curated 151).
- Anything requiring push / remote / deploy / flag-off behaviour change → **none performed.**
