# Consolidation log — `integration/ssri-shell-rc1`

## Branch tips archived (VERIFIED)

| Branch / tag | Commit |
|--------------|--------|
| `origin/main` (integration base) | `9a1a44cbc9b9012e1f960a9fc9d37eb4c823e29d` |
| `poc/release-shell` / `archive/release-shell-final` | `35e817bc3fb5b594e63f60ffa86904e8682ed79d` |
| `poc/landslide-credibility-v3` / `archive/credibility-v3-final` | `374f2bd90fb2d7cfc5fff99ae7a999e6c6406b4e` |
| `poc/landslide-due-diligence` / `archive/due-diligence-final` | `6e5f1687082e491eb78d98c5f32196028a71df8a` |

## Merge order

1. Created `integration/ssri-shell-rc1` from `origin/main`.
2. Merged `origin/poc/release-shell` (no conflicts) → merge commit `fde4eb4…`.
3. Merged `origin/poc/landslide-credibility-v3` (no conflicts) → merge commit `fffb1c2…`.

## What came from which branch

### From `poc/release-shell`

- `model/src/ssri_model/release_shell/**` (validator, spatial split, evaluate, gates, assess contract, routes, flags)
- Assess / uncertainty / job_workers flag-gated wiring
- `model/tests/test_release_shell_*.py` (original 16)
- `poc/release_shell/**` docs, scripts, SYNTHETIC template, rehearsal outputs
- Operator page limitations panel touch

### From `poc/landslide-credibility-v3` (includes due-diligence + credibility history)

- `poc/landslide_credibility_v3/**` (PROTOCOL_v3, FINAL_REPORT, slope index, scripts, outputs)
- `poc/landslide_credibility/**` (PROTOCOL_v2, corpus)
- `poc/landslide_due_diligence/**` (PROTOCOL v1, reports)
- `poc/landslide4sense/**` including isolated DeepSlide engine + `integration/test_deepslide_engine.py` (9 tests)
- Research docs / self-test reports at repo root

## Conflicts

**None.** Both merges used the `ort` strategy with clean trees. Frozen protocol files were **not** edited during consolidation.

## Duplicate / superseded patch files

**Removals: none.**

Proposed patches under:

- `poc/landslide_due_diligence/proposed_patches/`
- `poc/landslide_credibility/proposed_patches/`
- `poc/landslide_credibility_v3/proposed_patches/`

are **kept as research archives**. The release shell already implements the equivalent softmax + assess-contract behaviour under `model/src/ssri_model/release_shell/` behind `SSRI_RELEASE_SHELL` (default OFF). Deleting the archives would erase cycle evidence.

## DeepSlide wiring check (VERIFIED)

- Engine tests live at `poc/landslide4sense/integration/test_deepslide_engine.py`.
- No imports of DeepSlide from `model/src/ssri_model/api/` or the production assess path.
- One research gate script imports `ssri_model.ml.constants.CHANNEL_NAMES` only (constants), not the production model path.

## Frozen hashes (VERIFIED via git blob / CRLF-normalized)

| Artifact | Expected prefix | Result |
|----------|-----------------|--------|
| PROTOCOL v1 | `BD2A86BC…` | MATCH (git blob) |
| PROTOCOL v2 | `5F63E362…` | MATCH (git blob) |
| PROTOCOL v3 | `70FE823F…` | MATCH (git blob) |
| v2 corpus manifest | `E0D31A4F…` | MATCH (CRLF working-tree form as originally recorded; LF blob differs by newlines only) |

Windows `core.autocrlf` makes working-tree PROTOCOL hashes differ; canonical git blobs match expected PROTOCOL hashes. Content is unchanged.
