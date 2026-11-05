# STAGING_REPORT — `staging/ssri-shell-rc1`

**Not merged to main. Not deployed.**

---

## Pinned integration SHA (VERIFIED)

`fc4c0771ad4e1fe030de0761015432784bc59c75` (`origin/integration/ssri-shell-rc1`)

## Staging branch tip (VERIFIED)

Report publish tip: **`3a8a83dbf9ab28e8b5524c843e85c963af4e444f`**

Confirm live tip: `git rev-parse origin/staging/ssri-shell-rc1` (may be ahead by checklist/docs pins only).

Tests / `verify.py` were run on **`7c20acf6ada362704a0e0f7098cd0849133c049f`**. Docs-only commits on top do not change behaviour under test.

History on staging:

1. `2b44a8c…` — merge `--no-ff` of pinned `fc4c0771…` into `origin/main` (`514c7a1b…`)
2. `8b89e23…` — optional Poetry `deepslide` group + pinned `MERGE_CHECKLIST.md` + verify skip behaviour + `CI_DEEPSLIDE_NOTE.md`
3. `7c20acf…` — `poetry.lock` for the optional group
4. `3a8a83d…` — `STAGING_REPORT.md`

Author/committer on these commits: `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>`. No `Co-authored-by` trailers.

---

## Step 1 — fresh-clone checks (VERIFIED)

Clone: `C:\Users\LENOVO\Documents\MrBusoye\ssri-staging-check`

| Check | Result |
|-------|--------|
| `Co-authored-by` count | **0** |
| Identities | only `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>` (28 unique commits on fetched refs) |
| PROTOCOL v1 | `BD2A86BC…` MATCH (git blob) |
| PROTOCOL v2 | `5F63E362…` MATCH |
| PROTOCOL v3 | `70FE823F…` MATCH |
| v2 manifest | `E0D31A4F…` MATCH (CRLF working-tree form) |

---

## Tests on staging (VERIFIED)

| Matrix | Result |
|--------|--------|
| Flag **OFF** | **123 passed** (`poc/release_shell/outputs/staging_pytest_flag_off.txt`) |
| Flag **ON** | **123 passed** (`poc/release_shell/outputs/staging_pytest_flag_on.txt`) |
| DeepSlide | **9 passed** (not skipped; `poetry install --with deepslide`) |
| Flag unset assess w/o checkpoint | **400** `INVALID_REQUEST` / “Assessment requires 'checkpoint'.” — **LEGACY_OK** |

### `scripts/verify.py` output (VERIFIED)

Stdout:

```text
{
  "pass": true,
  "report": "C:\\Users\\LENOVO\\Documents\\MrBusoye\\ssri\\poc\\release_shell\\outputs\\verify_report.json"
}
```

Step tails from `verify_report.json`:

| Step | Result |
|------|--------|
| `git` | `staging/ssri-shell-rc1` |
| `commit` | `7c20acf6ada362704a0e0f7098cd0849133c049f` |
| `new_tests` | **21 passed** |
| `assess_93` | **93 passed** |
| `deepslide_9` | **9 passed** |
| `no_trained_model` (flag ON) | `200 no_trained_model` |
| overall | `"pass": true` |

---

## Dependency fix (VERIFIED)

**Choice:** optional Poetry group `deepslide` (not production deps).

- `model/pyproject.toml` — `[tool.poetry.group.deepslide]` with `segmentation-models-pytorch`, `h5py`
- Install: `poetry -C model install --with deepslide`
- `verify.py` probes imports; if missing → `DeepSlide skipped: optional deps` with rc 0 (does not fail verify)
- Note: `poc/release_shell/CI_DEEPSLIDE_NOTE.md`

---

## Size check (VERIFIED)

| Metric | Value |
|--------|------:|
| Working tree (excl. `.git`) | ~**6124 MB** |
| `git count-objects` size-pack | **347.79 MiB** |
| `poc/landslide4sense` total | **240.6 MB** |

Largest under `landslide4sense`:

| Size | Path |
|-----:|------|
| 77.61 MB | `poc/landslide4sense/data/ValidData.zip` |
| 25.57 MB | `poc/landslide4sense/weights/mobilenetv2.pth` |
| ~1.75 MB × N | `data/validation/images/image_*.h5` |

**Recommendation:** keep these out of `main` via Git LFS or archive-tag-only research packs. **Nothing removed** (awaiting your approval).

---

## Open risks

- Large `landslide4sense` binaries inflate clone/push (GitHub warned on ValidData.zip).
- Staging tip is **ahead** of the pinned integration SHA by two dep/docs commits; merge-to-main should use **`origin/staging/ssri-shell-rc1`**, not the older pin alone.
- DeepSlide remains unwired; optional group must be installed for the 9-test path in CI if you require it green.
- Stale SHAs still appear in older reports (not edited); use `COMMIT_MAP.md` / this report for current tips.

---

## Exact commands to merge staging → main later (owner only)

```powershell
git fetch origin
git checkout main
git pull origin main
git merge --no-ff origin/staging/ssri-shell-rc1 -m "Merge staging/ssri-shell-rc1 into main."
# Confirm identity / no Co-authored-by on the merge commit message before push
git log -1 --format='%an <%ae>%n%B'
git push origin main
```

Rollback if needed:

```powershell
git revert -m 1 <merge-commit-sha>
git push origin main
```
