# Merge checklist (owner only — agent does not merge to main)

## Pinned integration tip (VERIFIED from GitHub)

| Ref | Full SHA |
|-----|----------|
| `origin/integration/ssri-shell-rc1` | `fc4c0771ad4e1fe030de0761015432784bc59c75` |

Identity on that tip: `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>` (author + committer). No `Co-authored-by` trailers.

## Archive tags (post identity rewrite — see COMMIT_MAP.md)

| Tag | Tip commit | Source branch |
|-----|------------|---------------|
| `archive/release-shell-final` | `29d00c22795d29262c3552d3f372d85e60a9606a` | `poc/release-shell` |
| `archive/credibility-v3-final` | `2876fe2788ee5caae2719e478c95fddeee7ecaa2` | `poc/landslide-credibility-v3` |
| `archive/due-diligence-final` | `151409e4a8070860caba01195d13e6c925023587` | `poc/landslide-due-diligence` |
| `archive/ssri-shell-rc1` | `fc4c0771ad4e1fe030de0761015432784bc59c75` | `integration/ssri-shell-rc1` |

Original→final SHA map: `COMMIT_MAP.md` (repo root / identity-rewrite artifacts).

## Staging-first merge order (exact)

```powershell
git fetch origin
git checkout -B staging/ssri-shell-rc1 origin/main
git merge --no-ff fc4c0771ad4e1fe030de0761015432784bc59c75 -m "Merge integration/ssri-shell-rc1 (fc4c0771) into staging."
git push -u origin staging/ssri-shell-rc1
# Confirm flag default OFF
rg "SSRI_RELEASE_SHELL" model/src/ssri_model/release_shell/flags.py
poetry -C model run python poc/release_shell/scripts/verify.py
# Only after owner approval — merge staging to main (do not run until approved):
# git checkout main
# git pull origin main
# git merge --no-ff origin/staging/ssri-shell-rc1 -m "Merge staging/ssri-shell-rc1 into main."
# git push origin main
```

## Before merge to main

1. `poetry -C model run python poc/release_shell/scripts/verify.py` → pass  
2. Assess suite **93** + DeepSlide **9** (optional Poetry group `deepslide`; see CI note)  
3. `tests/test_release_shell_*.py` pass (21 tests)  
4. Combined matrix **123** pass with flag OFF and ON  
5. `SSRI_RELEASE_SHELL` default **off**  
6. No weights committed; SYNTHETIC only for demos  
7. Copy audit (`COPY_AUDIT.md`)  
8. Owner UI at `/shell`; API fallback `OWNER_API_GUIDE.md`

## Flag-off confirmation

```powershell
Remove-Item Env:SSRI_RELEASE_SHELL -ErrorAction SilentlyContinue
Remove-Item Env:SSRI_ASSESS_SOFTMAX -ErrorAction SilentlyContinue
poetry -C model run pytest tests/test_api_assess.py tests/test_api_assess_audit.py tests/test_demo_mode_assess.py tests/test_release_shell_assess.py -q
# assess without checkpoint must still 400/422 (legacy), not no_trained_model
```

## Rollback

```powershell
git revert -m 1 <merge-commit-sha>
# or unset flags only:
Remove-Item Env:SSRI_RELEASE_SHELL -ErrorAction SilentlyContinue
Remove-Item Env:SSRI_ASSESS_SOFTMAX -ErrorAction SilentlyContinue
```

Classic `/training` and sigmoid assess remain. Restore research-only tips from archive tags if needed.

## Do not

Deploy without approval; promote SYNTHETIC or FeatureStacks-v3-with-sentinel checkpoints; wire DeepSlide into API/assess; claim validated; force-push `main`.
