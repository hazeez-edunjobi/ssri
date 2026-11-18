# STAGING DEPLOY CHECKLIST — SSRI release shell + frontend (Task 6)

Branch: `finish/frontend-align-rc3` · tip: `git rev-parse HEAD` · identity: `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>`
**Posture: LOCAL / READ-ONLY. This checklist documents *how* to deploy to staging; it does not deploy, push, or change any remote.**

Labels used below: **VERIFIED** (evidence in-repo), **REPORTED** (stated by a system/human, not re-checked here), **UNKNOWN** (cannot be confirmed locally).

---

## 1. What this session actually verified (evidence)

| Check | Result | Evidence |
|---|---|---|
| Production guard on the smoke test | **VERIFIED** — exit `2`, refuses an `onrender.com`/`prod` host without `--allow-production` | `poc/release_shell/scripts/smoke_staging.py:316-322`, run this session |
| Local end-to-end owner flow (upload → validate → train 3 seeds → evaluate → promote → assess → report → out-of-region) | **VERIFIED** — `2 passed (3.5m)` | `poc/release_shell/outputs/frontend_rehearsal/` |
| Assess error contracts (no checkpoint → 200 `no_trained_model`; v2 + 13-channel → 400 naming missing channels, no traceback) | **VERIFIED** | `.../frontend_rehearsal/assess-error-contracts.json` |
| Every seed checkpoint carries release-shell meta (declared CRS) | **VERIFIED** | `.../frontend_rehearsal/work/.../models/*/release_shell_meta.json` (3 seeds) |
| Production frontend build | **VERIFIED** — `next build` exit 0 | this session |
| Live staging URL + API key + Supabase project + GEE credentials | **UNKNOWN** — none configured in this workspace | — |

---

## 2. Configuration surface (gather before deploying)

### Backend (`model/`, FastAPI) — env vars actually read
| Var | Default | Staging guidance |
|---|---|---|
| `SSRI_RELEASE_SHELL` | **OFF** (unset) | Set `true` only on the shell-enabled staging service. **Must stay default OFF** in code; flag-off behaviour is unchanged. |
| `SSRI_ASSESS_SOFTMAX` | OFF | Leave OFF unless the rehearsal profile is intended. |
| `SSRI_RELEASE_SHELL_MIN_TILES` | `300` | Rehearsal overrides to `1`; staging should use the real minimum. |
| `SSRI_RELEASE_SHELL_MIN_BLOCKS` | `8` | Rehearsal overrides to `4`. |
| `SSRI_RELEASE_SHELL_MIN_HELD_OUT` | `3` | Rehearsal overrides to `1`. |
| `SSRI_RELEASE_SHELL_BUFFER_KM` | `50` | Rehearsal overrides to `0`. |
| `SSRI_RELEASE_SHELL_BLOCK_SIZE_DEG` / `_KM` | unset | Optional explicit block size. |
| `SSRI_PREVIEW_UNEVALUATED_SCORES` | OFF | Keep OFF for honourable score withholding. |

### Frontend (`frontend/`, Next.js) — public vars (build-time)
| Var | Example | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` locally; the staging API origin otherwise | Wins when set; otherwise a production build falls back to the documented default (`lib/env.ts`, `.env.local.example`). |
| `NEXT_PUBLIC_SSRI_API_KEY` | *(secret)* | Used on the three authenticated calls in `lib/api.ts`. Never commit. |
| `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` | *(from Supabase project)* | Required for authenticated sessions; the UI shows a plain-language setup message when missing. |
| `NEXT_PUBLIC_MAP_STYLE_URL` | *(optional)* | Map style for the dashboard. |

> All `NEXT_PUBLIC_*` values are inlined at **build** time — set them before `next build`, not only at runtime.

---

## 3. Pre-deploy gates (must all pass on the exact commit)

- [ ] Working tree **clean** (`git status --porcelain` empty).
- [ ] Frozen data hashes match: v1 `BD2A86BC`, v2 `5F63E362`, v3 `70FE823F`, manifest `E0D31A4F` (see Task 7 evidence).
- [ ] No trained weights/checkpoints staged (`**/*.pt` ignored; diff vs `main` adds none).
- [ ] Backend suite green **flag OFF and ON** — counts not below the RC2 baseline (**703 full / 151 curated**).
- [ ] `scripts/verify.py` reports `{"pass": true}`.
- [ ] Frontend `typecheck` / `lint` / **unit tests** / `build` all green.
- [ ] Author **and** committer are `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>` on every new commit; no `Co-authored-by` trailers.

---

## 4. Deploy sequence (staging)

1. Provision the backend with the env block in §2 (`SSRI_RELEASE_SHELL=true` for the shell service).
2. Build the frontend **after** exporting the `NEXT_PUBLIC_*` values for staging, then deploy the static/Next server.
3. Confirm the shell routes are reachable only where the flag is ON; confirm flag-OFF clients do not see `/api/v1/release-shell/*`.

## 5. Post-deploy smoke (run against the staging URL)

```bash
python poc/release_shell/scripts/smoke_staging.py \
    --base-url https://<staging-api-host> \
    --api-key "$SSRI_API_KEY" \
    --out poc/release_shell/outputs/smoke_staging.json
```

- Exit `0` = every executed step PASS (SKIPs are reported, not failed).
- The script **refuses** a production-looking host unless `--allow-production` is passed (VERIFIED).
- If AOI acquisition (Earth Engine) is not configured on staging, the in-region assess steps report **SKIP**, not FAIL — treat SKIP as **UNKNOWN** until GEE is confirmed.

Owner-file readiness (advisory, read-only, never guesses):

```bash
python poc/release_shell/scripts/check_site_readiness.py <owner-folder> --json poc/release_shell/outputs/site_readiness.json
```

## 6. Off-switch / rollback

- Unset `SSRI_RELEASE_SHELL` (→ OFF) and restart the backend; shell routes disappear and assess behaves exactly as before (flag-off contract).
- The frontend `/shell` page degrades to its flag-off state; the dashboard hides shell-only affordances.

## 7. Open items

- **UNKNOWN:** the real staging base URL, staging API key, Supabase project, and Earth Engine credentials. Until these are supplied, only the local rehearsal and the production-guard check are VERIFIED.
- **Open:** point-assessment latency measured at **13.97 s** in the synthetic 3-seed CPU rehearsal (target 10 s). Re-measure on staging hardware with the intended `mc_samples`.
