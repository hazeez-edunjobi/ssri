# SSRI — Stage 2.5 Checkpoint and Model Artifact Discovery Report

**Date:** 2026-11-21  
**Mode:** STRICT READ-ONLY  
**Repo tip (reference):** `b855cdb` / engineering tag `ssri-completed` → `5d2e0cb`  
**Production API:** `https://ssri-api.onrender.com`  
**No train / register / promote / Git / deploy / env mutation performed**

---

## 1. Executive verdict

```text
CHECKPOINT FOUND (local Stage 2.5 assess-format artifacts with in_channels=13)
PRODUCTION PROMOTED CHECKPOINT: NOT FOUND / NOT_VERIFIED
GENUINE NON-SYNTHETIC PRODUCTION MODEL: NOT IDENTIFIED
INCOMPATIBLE ARTIFACTS ALSO PRESENT (foundation multitask; schema-v2 16-channel)
```

| Claim | Status |
|-------|--------|
| Real `.pt` files exist on this workstation under ignored output trees | **Verified** |
| At least one Stage 2.5 `best.pt` with `model_config.in_channels=13` and `model_state_dict` | **Verified** |
| Those 13-channel local models are synthetic / rehearsal / handover (not scientific production) | **Verified** (dataset names / paths) |
| Schema-v2 16-channel Stage 2.5-format checkpoints exist | **Verified** — **reject for production assess** |
| Git-tracked `models/ssri-foundation-v*.pt` are assess-loadable Stage 2.5 | **False** — `SSRIMultiTaskModel` / different payload keys |
| Render production has a promoted active Stage 2.5 checkpoint | **Not verified**; prior probes imply none usable |
| Persistent `/data/outputs` on Render Free | **Not verified** (config intent only) |

**Do not claim a production go-live checkpoint exists.** Local synthetic 13-channel weights must not be treated as scientifically validated or client-grade production models (`NOT_VALIDATED` remains).

---

## 2. Candidate artifact inventory

### 2.1 Git-tracked weights

| Path | Size | Notes | Production Stage 2.5 assess? |
|------|------|-------|------------------------------|
| `models/ssri-foundation-v1.pt` | 9 205 701 | `SSRIMultiTaskModel`, `state_dict` + `config`, `in_channels=13` | **No** — wrong architecture / loader contract |
| `models/ssri-foundation-v2.pt` | 9 205 701 | Same foundation payload family (`version` still labelled `ssri-foundation-v1` in metadata) | **No** |
| `poc/landslide4sense/weights/mobilenetv2.pth` | ~26.8 MB | External PoC backbone | **No** |

`git ls-files` shows only these three weight files tracked. **No Git LFS pointers** observed (`git lfs ls-files` empty).

### 2.2 Local Stage 2.5 assess-format `best.pt` (representative)

Ignored paths (`model/outputs/`, `poc/release_shell/outputs/**`) contain many near-duplicate rehearsal copies (~27 MB each). Metadata inspected via `torch.load(..., map_location="cpu")` reading **only** config/manifest fields (pickle inherent to `.pt`; no model forward pass).

| Relative path | Size | SHA-256 | `in_channels` | Dataset name in checkpoint | Classification |
|---------------|------|---------|---------------|----------------------------|----------------|
| `model/_handover_tmp/best.pt` | 158 065 | `3556db1df083dd0a29ef9a474ad415b43d9c91917f392193737387e6c324501a` | **13** | `handover` | Stage 2.5 format; **atypically small**; epoch 1 |
| `model/outputs/rehearsal_300k_shell/.../ssri-model-153f09d946/best.pt` | 27 022 703 | `d912027e17ed532687f9d2a2c74fd3c18ca8c812ae49107d939ade19dde5d004` | **13** | `SYNTHETIC-300k-rehearsal` | Stage 2.5; **synthetic** |
| `model/outputs/upload_cap_shell/.../ssri-model-2e91993348/best.pt` | 27 022 703 | `c474958ffb41d38987f111f72b95b22a7c68730d5936f3e4eceab9230d0937f3` | **13** | `SYNTHETIC shell rehearsal` | Stage 2.5; **synthetic** |
| `poc/release_shell/outputs/acceptance_tmp/.../ssri-model-4c809fca35/best.pt` | 27 022 703 | `9100bc26a31f3f7b8fbd0e99e9b11a025b8f227fdd6c82c668220ccd797a3200` | **13** | `SYNTHETIC_stage25_template` | Stage 2.5; **synthetic** |
| `poc/release_shell/outputs/e2e_synthetic_v2/.../ssri-model-1d8b7235a4/best.pt` | 27 033 135 | (prefix `7F3545F5…`) | **16** | `SYNTHETIC_stage25_v2_template` | Stage 2.5-format; **reject for production** |
| `poc/release_shell/outputs/frontend_rehearsal/.../ssri-model-b6b516015f/best.pt` | 27 026 437 | (prefix `3DDF7133…`) | **16** | `SYNTHETIC_stage25_v2_template` | Stage 2.5-format; **reject for production** |

Feature stacks sampled:

| Tree | Sample `feature_stack.npy` shape |
|------|----------------------------------|
| `rehearsal_300k_shell` | `(13, 128, 128)` |
| `e2e_synthetic_v2` | `(16, 16, 16)` |
| `frontend_rehearsal` | `(16, 16, 16)` |

Also present (not production Stage 2.5): `api/.../site-packages/ssri_api.pth` (46 bytes — packaging path file).

### 2.3 Local registries

| Path | Role |
|------|------|
| Several `.../training/models/registry.json` under `model/outputs/*` and `poc/release_shell/outputs/*` | Local rehearsal registries |
| `poc/release_shell/outputs/frontend_rehearsal/.../active.json` | Points at **16-channel** `ssri-model-b6b516015f` locally |

These registries are **local ignored artifacts**, not evidence of Render production state.

---

## 3. Stage 2.5 training pipeline and output paths

### Authoritative flow (code)

1. **API:** `POST /api/v1/training/jobs` → job worker → `run_manual_training` (`manual_training/runner.py`).  
2. **Model:** `create_ssri_model(SSRIModelConfig(in_channels=schema.channel_count))` — **13** for v1 manifests, **16** if schema-v2 declared.  
3. **Trainer:** `Trainer.fit` writes `{experiment_dir}/best.pt` and `latest.pt` via `save_checkpoint` (`BEST_CHECKPOINT_NAME = "best.pt"`).  
4. **Payload:** `model_state_dict`, `model_config`, training history, optional `dataset_manifest`.  
5. **Registry:** `ModelRegistry.register_from_training` copies `best.pt` to `{output_root}/training/models/{model_id}/best.pt` and appends `registry.json`.  
6. **Promote:** `POST /api/v1/training/models/activate` writes `active.json` (not executed this audit).

Default API output root from env: `SSRI_API_OUTPUT_ROOT` (Compose/example: `/data/outputs`). Local default if unset: `outputs/service` under API config prefix.

CLI research foundation train (`python -m ssri_model.scripts.train_foundation_multitask`) produces **multitask** checkpoints — **not** assess Stage 2.5.

Training **has** completed successfully in local rehearsal shells (registry notes + metrics), but those runs are **synthetic**.

---

## 4. Architecture and 13-channel compatibility evidence

| Requirement | Evidence |
|-------------|----------|
| Assess loads Stage 2.5 via `model_state_dict` + `model_config` | `inference/checkpoint.py` → `load_evaluation_model` |
| Production live contract | `CHANNEL_COUNT == 13` (`ml/constants.py`) |
| Local synthetic 13-ch `best.pt` | Metadata **verified** (`in_channels=13`, `num_classes=3`) |
| Local schema-v2 `best.pt` | Metadata **verified** (`in_channels=16`) — **incompatible** with production live assess |
| Foundation `.pt` | `SSRIMultiTaskModel` + `state_dict` — **not** assess Stage 2.5 loader contract |
| Full `SSRIModel` forward load of local 13-ch files | **Not executed** this audit (metadata-only inspect); format matches Stage 2.5 |

---

## 5. Registry and active-model status

| Environment | Finding |
|-------------|---------|
| **Local** frontend_rehearsal | `active.json` promotes a **16-channel** synthetic model id |
| **Local** rehearsal trees | Registries exist; multiple synthetic model ids |
| **Production** `GET /api/v1/training/models/active` | Previously **401** without credentials; assess fail-closed with no usable active model (**not re-authenticated this audit**) |
| Production registry contents | **Unknown** without operator credentials / Render disk |

---

## 6. Git / cloud artifact findings

| Item | Finding |
|------|---------|
| `.gitignore` | Ignores `model/outputs/`, `poc/release_shell/outputs/frontend_rehearsal/`, many shell output trees — checkpoints **not** in Git |
| Tracked weights | Foundation + landslide4sense only |
| Git LFS | No tracked LFS weight objects observed |
| GitHub Actions | No workflow found that uploads production `best.pt` artifacts for deploy |
| Docs | Reference fixture `/data/outputs/e2e-job/checkpoint.pt` as **fixture** (`dataset_manifest.name=e2e`) — must not be promoted |
| Secrets | Not printed |

---

## 7. Production storage findings

| Topic | Class | Finding |
|-------|-------|---------|
| Intended root | Config/docs | `SSRI_API_OUTPUT_ROOT=/data/outputs`; training under `{output_root}/training/` |
| Render Free disk | **Unknown** | Persistent volume **not verified**; free instances are often ephemeral unless a disk is attached |
| API vs worker FS | Docs | Must share the same output root; worker deploy notes require matching volume |
| Object store | Config optional | S3/MinIO/R2 supported for objects; **not** confirmed as the checkpoint registry backend in production |
| Production checkpoint presence | Prior + this audit | **NOT_VERIFIED** — do not assume local files are on Render |

---

## 8. Exact next action

**Recommended path (owner-approved, not performed here):**

1. **Do not promote** synthetic 16-channel, foundation multitask, or fixture/e2e checkpoints to production.  
2. **Search owner archives / other machines** for any non-synthetic Stage 2.5 13-channel `best.pt` trained on real labelled Stage 2.5 data. If found: verify `model_config.in_channels == 13`, register under production `{SSRI_API_OUTPUT_ROOT}/training/`, then `POST .../models/activate`.  
3. If no genuine artifact exists: **plan a new Stage 2.5 training run** on a **persistent** production (or staging) volume using a real Stage 2.5 dataset (`feature_stack.npy` shape `(13,H,W)`), then register + promote.  
4. Confirm Render attaches durable storage at `SSRI_API_OUTPUT_ROOT` shared by API and worker before relying on promote across restarts.  
5. Optional engineering-only smoke: local 13-channel synthetic weights can exercise assess plumbing — they remain **NOT_VALIDATED** and are **not** a production release candidate.

### Assumptions vs unknowns

| Assumptions (not proven) | Unknowns |
|--------------------------|----------|
| Render service env name matches Compose examples | Whether any non-synthetic checkpoint exists offline outside this repo tree |
| Free Render disk may wipe artifacts without a paid/persistent disk | Exact production `registry.json` / `active.json` contents |
| | Whether object storage already holds a checkpoint blob |

---

## Compliance

- No training, registration, promotion, deploy, Git ops, or secret disclosure.  
- Temporary read-only probe scripts under `poc/_tmp_*` used for inspection only.  
- Scientific status unchanged: **`NOT_VALIDATED`**; Phase 6 / 16-channel live assess remains **blocked**.
