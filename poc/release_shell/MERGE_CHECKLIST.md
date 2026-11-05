# Merge checklist (owner only — agent does not merge)

## Archive tags (do not delete)

| Tag | Tip commit | Source branch |
|-----|------------|---------------|
| `archive/release-shell-final` | `35e817bc3fb5b594e63f60ffa86904e8682ed79d` | `poc/release-shell` |
| `archive/credibility-v3-final` | `374f2bd90fb2d7cfc5fff99ae7a999e6c6406b4e` | `poc/landslide-credibility-v3` |
| `archive/due-diligence-final` | `6e5f1687082e491eb78d98c5f32196028a71df8a` | `poc/landslide-due-diligence` |

Integration branch: **`integration/ssri-shell-rc1`** (see `CONSOLIDATION_LOG.md` / `INTEGRATION_RC1_REPORT.md` for tip hash).

## Staging-first merge order (exact)

```powershell
git fetch origin
git checkout main
git pull origin main
# optional staging branch
git checkout -b staging/ssri-shell-rc1
git merge --no-ff origin/integration/ssri-shell-rc1
# Confirm flag default OFF
rg "SSRI_RELEASE_SHELL" model/src/ssri_model/release_shell/flags.py
# Run verify with flag OFF then ON (see INTEGRATION_RC1_REPORT)
poetry -C model run python poc/release_shell/scripts/verify.py
# Only after owner approval:
# git checkout main
# git merge --no-ff staging/ssri-shell-rc1
# git push origin main
```

## Before merge

1. `poetry -C model run python poc/release_shell/scripts/verify.py` → pass  
2. Assess suite **93** + DeepSlide **9** (now on integration via credibility merge)  
3. `tests/test_release_shell_*.py` pass (16 original + new route/jobs tests)  
4. `SSRI_RELEASE_SHELL` default **off** — full existing suite unchanged  
5. No weights committed; SYNTHETIC only for demos  
6. Copy audit (`COPY_AUDIT.md`)  
7. Owner UI at `/shell`; API fallback `OWNER_API_GUIDE.md`

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
