# SSRI — Final Engineering Release Report

**Date:** 2026-11-25  
**Authorization:** Explicit user approval to stage, commit, push `main`, and verify GitHub Actions  
**Pre-commit review:** `SSRI_PRE_COMMIT_REVIEW_REPORT.md` — **APPROVE COMMIT**

---

## Final milestone decision

# ENGINEERING RELEASE PUSHED — CI BLOCKED *(pending follow-up CI)*

Engineering release `49ce31d` is on `origin/main`. Initial CI failed on model **Ruff** (frontend succeeded; docker skipped). A follow-up commit with Ruff fixes + this report is included in the same release track; re-check CI on the new HEAD before upgrading to **ENGINEERING RELEASE COMPLETE**.

---

## 1. Starting HEAD and remote state

| Item | Value |
|---|---|
| Repo | `https://github.com/hazeez-edunjobi/ssri.git` |
| Branch | `main` |
| Starting local HEAD | `44558779ffe93a0f2a3d151e8f0a9d309f7e8753` (ahead of origin by 1) |
| Starting `origin/main` | `d8ac1bc257a435cf22cc3b2bb14aa9b24e9832f1` |
| Pre-flight | Matches approved review inventory; no unexpected secrets in candidate set |

---

## 2. Commit SHA and message

| Item | Value |
|---|---|
| Release commit | `49ce31d43b62e6851bcc2ac8f3f13bb5ae33bf1b` |
| Subject | `Complete SSRI engineering release and geological tooling` |
| Body | Ships assessment history UI/API, staging gate subset, lease-recovery defaults, safer checkpoint loads, candidate lineament / subsidence tooling, FE remediation, and completion reports. **Does not claim scientific validation or production readiness.** |
| Also pushed | `4455877` (prior local-only catalogue-overlay commit) |

---

## 3. Exact committed file scope

**54 files**, +5701 / −80 — matching the approved pre-commit inventory:

- 22 previously modified tracked files (FE gates/marketing/history wiring, API history/geological routes, production_gate, lease config, compose, `safe_torch` paths, etc.)
- Untracked FE assessments UI, auth gates, history/marketing/operator helpers + tests
- New model modules: magnetic lineament extraction, conditioning inventory, subsidence validation + tests
- Approved small `poc/` evidence JSON/TXT/py
- SSRI completion / audit / acceptance / pre-commit reports

---

## 4. Excluded files (preserved locally, not in Git)

| Exclusion | Status |
|---|---|
| `.env` / credentials / secrets | Not committed |
| `data/outputs/**` (checkpoints, assessments, lineament GeoTIFFs/GeoJSON) | gitignored; **preserved on disk** |
| `best.pt` / active registry weights | Not committed; SHA verified |
| `node_modules`, `.next`, `__pycache__`, `poc/_tmp_*` | Not committed |

---

## 5. Push confirmation and branch alignment

| Item | Value |
|---|---|
| Push | **Succeeded** (HTTPS + Git Credential Manager after account selection) |
| Range | `d8ac1bc..49ce31d` → `main` |
| Local `HEAD` | `49ce31d43b62e6851bcc2ac8f3f13bb5ae33bf1b` |
| `origin/main` | `49ce31d43b62e6851bcc2ac8f3f13bb5ae33bf1b` |
| Alignment | **Local `main` == `origin/main`** |

SSH push attempts failed (authenticated identities lacked write permission to `hazeez-edunjobi/ssri`); HTTPS succeeded. No force-push.

---

## 6. `ssri-completed` tag

| When | Target |
|---|---|
| Before | Annotated tag `427f57841382b09de50a65b549a974c1e68d0fbf` → peeled `5d2e0cb18de77b2494a79719e06b32b20a3a2704` |
| After | **Unchanged** `427f57841382b09de50a65b549a974c1e68d0fbf` (not moved/rewritten) |

---

## 7. GitHub Actions results

Workflow: **CI** (`.github/workflows/ci.yml`) — push-triggered on `main`.

| Field | Value |
|---|---|
| Run ID | `45390339630` |
| URL | https://github.com/hazeez-edunjobi/ssri/actions/runs/45390339630 |
| Commit tested | `49ce31d43b62e6851bcc2ac8f3f13bb5ae33bf1b` |
| Overall | **failure** |

| Job | Conclusion | Notes |
|---|---|---|
| `frontend` | **success** | typecheck + build |
| `model` | **failure** | **Ruff** failed (5 lint findings) |
| `docker` | **skipped** | depends on `model` |

### Ruff failures (blocking)

1. `geological.py` — unused `InvalidServiceConfigError` (F401)  
2. `magnetic_lineament_extraction.py` — unused `mask` (F841)  
3. `magnetic_processing.py` — ambiguous name `I` (E741) *(pre-existing on prior failing main runs)*  
4. `service.py` — unused `shutil` (F401)  
5. `test_geological_tmi.py` — unused `exc` (F841) *(pre-existing)*  

**Local follow-up (not yet committed):** the five Ruff issues above have been fixed in the working tree; `poetry -C model run ruff check src tests` should be re-verified clean before any follow-up commit. Per release instructions, that follow-up commit/push awaits explicit approval.

---

## 8. Checkpoint SHA and 13-channel contract

| Item | Value |
|---|---|
| Active model | `ssri-model-e7af3afcd0` |
| Checkpoint SHA-256 | `d912027e17ed532687f9d2a2c74fd3c18ca8c812ae49107d939ade19dde5d004` |
| Stage 2.5 channels | **13** (`CHANNEL_NAMES` unchanged; no retrain/promote) |

---

## 9. Scientific and production limitations (preserved)

- Scientific validation: **NOT_VALIDATED**
- Subsidence validation: **blocked by missing independent ground truth**
- Abeokuta **72** lineaments remain **candidate magnetic lineaments**, not confirmed faults/fractures
- Catalogue overlays remain **`used_in_inference=false`**
- No Vercel/Render/production deploy, Supabase changes, env changes, or training performed

---

## 10. Working tree after release

Uncommitted local changes (awaiting review before any further commit):

- Ruff CI fixes in the five files listed above  
- `SSRI_FINAL_ENGINEERING_RELEASE_REPORT.md` (this file)  
- Restored typo in `SSRI_PRE_COMMIT_REVIEW_REPORT.md` (accidental backtick; not on remote)

---

## Next action for human approval

1. Approve a follow-up commit containing only the Ruff fixes (+ this release report / pre-commit typo restore if desired).  
2. Push to `origin/main` (non-force).  
3. Confirm CI run on the new SHA: model + frontend + docker all green → upgrade decision to **ENGINEERING RELEASE COMPLETE**.
