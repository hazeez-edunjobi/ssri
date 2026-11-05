# FINAL_STAGING_REPORT — `staging/ssri-shell-rc1`

**Not merged to main. Not deployed.**

Identity on all commits: `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>`. No `Co-authored-by` trailers.

---

## 1. Fix SHA explanation (VERIFIED)

| Ref | Full SHA |
|-----|----------|
| `origin/fix/upload-line-cap` | `0b35dc901530228b2cae08377aede57a1b047773` |
| Code commit (tested) | `9bb643024b318087c4cb528a1cf56fd11a581020` |
| Docs-only follow-up | `0b35dc901530228b2cae08377aede57a1b047773` |

```text
git log --oneline 9bb64302..0b35dc90
0b35dc9 Record fix/upload-line-cap tip SHA in UPLOAD_CAP_REPORT.

git diff --stat 9bb64302 0b35dc90
 poc/release_shell/UPLOAD_CAP_REPORT.md | 8 +++-----
 1 file changed, 3 insertions(+), 5 deletions(-)
```

**Difference:** docs-only tip pin in `UPLOAD_CAP_REPORT.md`. **No code change** after the tested commit → matrix re-run on final **staging** tip (includes 1 GiB default commit).

---

## 2. Pinned staging tip (VERIFIED)

| Ref | Full SHA |
|-----|----------|
| `origin/staging/ssri-shell-rc1` | `6578c0eb2e7a8d709bab5025ee2586e118aadaba` |
| Matrix / verify tip | `ee3317b88782f9e1a19f356af7802a01494f2ebc` (code + 1 GiB default; docs-only commits follow) |

History:

1. `eff5219…` — merge `--no-ff` of `0b35dc90…` (`fix/upload-line-cap`)
2. `ee3317b…` — default `SSRI_UPLOAD_MAX_BYTES` **1 GiB** + legacy path inventory
3. `92864cd…` — `FINAL_STAGING_REPORT.md` + `rehearse_stage25_300k.py`
4. `6578c0e…` — tip pin in this report

Confirm live tip: `git rev-parse origin/staging/ssri-shell-rc1`

---

## 3. Config after staging consolidate

| Variable | Default |
|----------|---------|
| `SSRI_UPLOAD_MAX_ROWS` | unset → **unlimited** |
| `SSRI_UPLOAD_MAX_BYTES` | **1073741824 (1 GiB)** |

### Legacy paths whose limits changed

| Path | Before | After |
|------|--------|-------|
| `manual_training/csv_import.py` | Hard `MAX_CSV_ROWS = 250_000`; no byte check | Unlimited rows (optional env); byte check via shared helper |
| `manual_training/ingest.py` | Hard `MAX_UPLOAD_BYTES = 500 MiB` | Shared default **1 GiB** |
| `platform/service.py` | Hard `500 MiB`; HTTP 400 | Shared **1 GiB**; HTTP **413** |
| `api/routes/training.py` | Upload errors → 400 | `UPLOAD_TOO_LARGE` → **413** |
| `release_shell/routes.py` | Upload errors → 400 | `UPLOAD_TOO_LARGE` → **413** |

---

## 4. Tests on staging tip (VERIFIED)

| Check | Result |
|-------|--------|
| Flag **OFF** | **132 passed** (93 + 9 DeepSlide + 21 shell + 9 upload-cap) |
| Flag **ON** | **132 passed** |
| DeepSlide | **9 passed** (not skipped; `poetry install --with deepslide`) |
| `scripts/verify.py` | see paste below |
| Flag-unset assess w/o checkpoint | **400** `INVALID_REQUEST` / “Assessment requires 'checkpoint'.” |

### `scripts/verify.py` output

```text
{
  "pass": true,
  "report": "C:\\Users\\LENOVO\\Documents\\MrBusoye\\ssri\\poc\\release_shell\\outputs\\verify_report.json"
}
```

### Frozen hashes (VERIFIED — content SHA-256)

| Artifact | Expected prefix | Result |
|----------|-----------------|--------|
| PROTOCOL v1 (`poc/landslide_due_diligence/PROTOCOL.md`) | `BD2A86BC` | **MATCH** (git content / LF-normalized) |
| PROTOCOL v2 (`poc/landslide_credibility/PROTOCOL_v2.md`) | `5F63E362` | **MATCH** |
| PROTOCOL v3 (`poc/landslide_credibility_v3/PROTOCOL_v3.md`) | `70FE823F` | **MATCH** |
| v2 manifest (`poc/landslide_credibility/corpus/manifest.json`) | `E0D31A4F` | **MATCH** (working-tree CRLF form) |

Frozen protocol files were **not edited**.

---

## 5. Realistic SYNTHETIC rehearsal (VERIFIED)

Script: `poc/release_shell/scripts/rehearse_stage25_300k.py`  
Artifact: `poc/release_shell/outputs/rehearsal_300k/rehearsal.json`

| Metric | Value |
|--------|------:|
| Label | **SYNTHETIC** (not geological truth) |
| Channels | 13 |
| Total cells | **442 368** (≥300 000) |
| Distinct 5° blocks | **9** (≥8) |
| Tiles | 27 |
| Validate time | **~2.16 s** |
| Peak RSS | **~444 MB** |
| Memory failure | **No** |
| Train start | **202** (~0.37 s) |
| Short run complete | **Yes** (~43 s for 1 epoch) |

Gate mins for this short run: `MIN_TILES=8`, `MIN_BLOCKS=8`, `MIN_HELD_OUT=2` (defaults would require 300 tiles).

---

## 6. Binary slim variant (local only — not pushed to main)

Prepared clone: `C:\Users\LENOVO\Documents\MrBusoye\ssri-staging-slim`  
Branch: `staging/ssri-shell-rc1-slim-no-l4s-data` @ `ebf20a4e6accdbe405af1bb6c61a774aed024b23`

Excluded from that variant:

- `poc/landslide4sense/data/ValidData.zip`
- `poc/landslide4sense/data/validation/images/*.h5` (40 files)

Kept: `poc/landslide4sense/weights/mobilenetv2.pth`

| Check | Result |
|-------|--------|
| DeepSlide 9 on slim tree | **9 passed** without ValidData.zip / validation `.h5` |

**Recommendation:** keep ValidData.zip and validation `.h5` out of `main` (LFS or archive tags). Do not squash-push this slim history to main without an explicit owner decision.

---

## 7. Exact commands to merge staging → main later (owner only)

```powershell
git fetch origin
git checkout main
git pull origin main
git merge --no-ff origin/staging/ssri-shell-rc1 -m "Merge staging/ssri-shell-rc1 into main."
git log -1 --format='%an <%ae>%n%B'   # confirm identity; no Co-authored-by
git push origin main
```

Rollback:

```powershell
git revert -m 1 <merge-commit-sha>
git push origin main
```

---

## Open risks

- Large `landslide4sense` binaries still on staging history (slim variant is local-only).
- Default 1 GiB may still exceed some reverse proxies.
- Grid memory still scales with cell count after streaming removes the row-list blow-up.
