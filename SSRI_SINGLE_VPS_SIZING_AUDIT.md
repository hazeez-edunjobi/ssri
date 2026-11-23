# SSRI — Single-VPS Sizing Audit (Read-Only)

**Date:** 2026-11-23  
**Mode:** Investigate and report only. No code, config, Git, deploy, promotion, or billing changes.  
**Target architecture:** One VPS running FastAPI API + Celery worker on shared `/data/outputs`; Supabase Postgres; Upstash Redis; Vercel frontend. Firebase/R2 out of scope.

**Legend:** **Measured** = executed locally this audit. **Cited** = from source/docs. **Inferred** = reasoned from evidence, not measured. **Unknown** = cannot determine from repo alone.

---

## Summary table

| # | Question | Answer | Evidence | Confidence |
|---|---|---|---|---|
| 1a | Frameworks | PyTorch (prod). Optional deepslide SMP. No TF. sklearn only in PoC scripts | `model/pyproject.toml` L9–47; `poetry.lock` torch 2.13.0; Docker pins CPU `torch==2.5.1` | High |
| 1b | GPU hard requirement | No path requires GPU for Stage 2.5 assess. Training/inference support CUDA optionally; AMP only if CUDA | `assess.py` L455 `device=cpu`; `device.py` L11–22; `trainer.py` L123–125 | High |
| 1c | Inference on CPU | **Yes.** Live assess forces CPU. Local load+forward of 13-ch `best.pt` succeeded | Measured forward; `assess.py` L452–456 | High |
| 1d | Training GPU | **Optional.** Defaults `device="auto"` → CPU if no CUDA. Synthetic CPU epoch ~0.5–9 s (tiny data) | `TrainingConfig.device` L53; measured `epoch_seconds` in ckpt history | Med (real dataset size unknown) |
| 1e | Verdict inference | **CPU sufficient** | Assess hardcodes CPU; Docker CPU torch | High |
| 1f | Verdict training | **GPU optional** (CPU works, slower on real data) | `resolve_device("auto")`; CUDA AMP gated | High |
| 2a | Model size | **2,246,659** params (~8.6 MB fp32 weights); Stage 2.5 `best.pt` ≈ **27.0 MB** on disk (includes optimizer etc.) | Measured `count_parameters`; file size | High |
| 2b | Peak inference RAM | Process RSS rose to **~1.9 GB** at 1024×1024 single forward (model already loaded). Smaller tiles ≪1 GB | Measured fwd RSS table below | Med–High (host already had torch imported) |
| 2c | Peak training RAM | **Unknown** for production datasets. Defaults `batch_size=4`, `num_workers=0`. Synthetic trains used bs=1–2 on CPU | `TrainingConfig` L45–46; ckpt `training_config` | Low for peak |
| 2d | API + worker together | **Inferred ≥8 GB** usable; **16 GB** comfortable if assess 512–1024 tiles overlap training | Inference RSS + two Python/torch processes | Med |
| 3 | CPU | ML work is CPU-bound on this stack. Celery default concurrency **1** (keep at 1 on small VPS) | `celery_app.py` L11–20, L34–35; `num_workers=0` in manual training | High |
| 4 | Disk | Local artifact trees ~**5 GB** + `data/` ~**1.2 GB** (geophysics ~461 MB). Upload uncompressed ZIP default cap **50 GiB**. Recommend **100 GB min / 200 GB** | Measured dir sizes; `upload_limits.py` L27 | Med (prod growth client-dependent) |
| 5 | Genuine Stage 2.5 prod ckpt | **Missing in production.** Local 13-ch synthetics exist and **load**; foundation `.pt` not assess Stage 2.5. `NOT_VALIDATED` unchanged; no promote this audit | Live `/ready`; load test; registry JSON | High |
| 6 | Celery | One task `ssri.execute_job` → inference / batch / training. Retries via job `max_attempts` (default 3). Worker death: late ack + reject_on_worker_lost; optional lease recovery | `tasks.py`; `celery_app.py` L32–33; `JobRecord.max_attempts` | High |
| 7 | OS deps | Python **3.11**; Docker runtime: curl, libexpat, sqlite, libcurl, ssl, zlib + WhiteboxTools binary; rasterio/pyproj wheels; **no CUDA** in image | `Dockerfile`; `pyproject.toml` | High |
| 8 | VPS spec | **Min:** 4 vCPU / 8 GB RAM / 100 GB SSD / **no GPU**. **Rec:** 4–8 vCPU / **16 GB** / **200 GB** / no GPU. Train heavy jobs off-box GPU optional | This audit | Med–High |

---

## 1. GPU requirement

### Frameworks and versions (cited + measured)

| Package | Role | Version evidence |
|---|---|---|
| **PyTorch** | Stage 2.5 train/infer/assess | `pyproject.toml` `torch = "^2.0"`; lock **2.13.0**; local venv measured `2.13.0+cpu`; **Docker installs CPU `torch==2.5.1`** (`Dockerfile` L31–32) — image ≠ lock |
| numpy, scipy, rasterio, whitebox, matplotlib | Geospatial / DEM | `pyproject.toml` L12–19 |
| segmentation-models-pytorch | **Optional** deepslide PoC group only | `pyproject.toml` L39–47 |
| TensorFlow | Not a dependency | No match in `model/pyproject.toml` |
| scikit-learn | PoC scripts only, not production package | e.g. `poc/landslide_credibility/...` |

### CUDA / GPU call sites

| Location | Behavior |
|---|---|
| `training/device.py` `resolve_device` | `auto` → cuda if available else cpu; explicit `cuda` errors if missing |
| `training/trainer.py` L123–125, L446, L509 | `GradScaler` / `autocast` **only when** `mixed_precision and device.type == "cuda"`; default `mixed_precision=False` (`TrainingConfig` L54) |
| `inference/runner.py` L116–117, L229–231 | AMP only on CUDA; forbidden on CPU |
| **`api/routes/assess.py` L455** | **`device=torch.device("cpu")`** — production assess path is CPU-only |
| `platform/service.py` L191 | `device="cpu"` |
| `scripts/train_foundation_multitask.py` L316–319 | Research multitask: cuda if available (not assess Stage 2.5) |
| `api/dependencies.py` L245 | Some executor paths pass `device="auto"` (async inference) — still CPU if no GPU |

**No GPU-only library is required for the Stage 2.5 production path.** Docker comment explicitly filters CUDA wheels (`Dockerfile` L3–4, L31–34).

### CPU inference proof (measured)

Checkpoint: `model/outputs/rehearsal_300k_shell/.../ssri-model-153f09d946/best.pt` (13-ch Stage 2.5 format, synthetic).

| Step | Result |
|---|---|
| `torch.load(..., map_location="cpu")` | Keys include `model_state_dict`, `model_config` |
| `model_config` | `in_channels=13`, `num_classes=3`, `base_channels=32`, `num_encoder_stages=3` |
| `load_state_dict` | missing=0, unexpected=0 |
| Forward `(1,13,128,128)` | output `(1,3,128,128)`, ~0.09–0.19 s on this workstation CPU |

### Training CPU vs GPU

- Defaults: `device="auto"`, `epochs=20`, `batch_size=4`, `num_workers=0` (`training/config.py` L45–54).
- Measured synthetic Stage 2.5 checkpoints were trained with **`device=cpu`**, often **1 epoch**, `batch_size` 1–2; `epoch_seconds` **0.45–9.2 s** (tiny tile counts: e.g. train_count=18).
- **Unknown:** wall time for a real multi-GB client dataset on CPU vs GPU.  
  **How to measure:** run one full `POST /training/jobs` (or `Trainer.fit`) on the candidate VPS with the real zip; record `training_history[].epoch_seconds` and total wall clock; optionally repeat on a rented GPU with `device=cuda`.

### Verdict

| Workload | Verdict |
|---|---|
| **(a) Inference / assess** | **CPU sufficient** (required path is CPU) |
| **(b) Training** | **GPU optional** — CPU works; GPU speeds large runs |

---

## 2. Memory (RAM)

### Model size (measured)

| Metric | Value |
|---|---|
| Parameters (`SSRIModelConfig` defaults) | **2,246,659** total = trainable |
| fp32 weight bytes (params×4) | ≈ **8.99 MB** |
| Typical Stage 2.5 `best.pt` on disk | **27,022,703** bytes (~25.8 MiB) — includes optimizer/scheduler/history |

### Peak RAM — inference (measured on this host)

Baseline process already had PyTorch imported (~270–320 MB RSS before large tensors).

| Input | Forward time | Approx process RSS |
|---|---|---|
| 128×128 | ~0.09 s | ~321 MB |
| 256×256 | ~0.35 s | ~386 MB |
| 512×512 | ~1.36 s | ~738 MB |
| **1024×1024** | ~5.5 s | **~1.92 GB** |

**Inferred for production assess:** live AOI rasters can exceed 128²; budget **2–4 GB** for a single API process under large tiles, plus OS and acquisition buffers (Whitebox/DEM). Exact AOI peak **unknown** without a production AOI replay.  
**How to measure:** `GET`/`POST` assess with target AOI under `/usr/bin/time -v` or `psutil` while sampling RSS; or `tracemalloc` around forward.

### Peak RAM — training / dataset processing

**Unknown** for real datasets. Defaults keep DataLoader `num_workers=0` (`manual_training/runner.py` L78–81), so no extra loader processes by default. Checkpoint files ~27 MB each; feature stacks are full `.npy` on disk (e.g. prior discovery noted `(13,128,128)` for rehearsal).

**How to measure:** train with production zip; sample RSS of Celery child throughout `Trainer.fit`; note batch_size.

### API + Celery simultaneously (inferred)

| Component | Rough RAM |
|---|---|
| API idle + torch import | ~0.5–1.5 GB |
| API large assess | +1–2 GB transient |
| Worker + train/infer | ~1–3+ GB |
| OS / buffers | ~1 GB |

**Minimum practical:** **8 GB** RAM (tight if 1024² assess coincides with training).  
**Recommended:** **16 GB**.

---

## 3. CPU

- Work is **CPU-bound** on the Docker CPU torch image (convolutions, DEM/Whitebox, rasterio).
- Manual training: `num_workers=0` (no parallel DataLoader workers).
- Celery: `SSRI_CELERY_CONCURRENCY` default **1**; `worker_prefetch_multiplier=1` (`celery_app.py`).
- **Keep concurrency at 1** on an 8 GB box so API and one train/infer job do not multiply torch copies. Raise only after measuring headroom (e.g. 2 on 16 GB if jobs are light).

---

## 4. Disk

### Measured local trees (this workstation — not production `/data/outputs`)

| Path | Size |
|---|---|
| `model/outputs/` | ~643 MB |
| `poc/release_shell/outputs/` | ~3.2 GB |
| `models/` (foundation weights) | ~18 MB |
| `data/` | ~1.16 GB |
| `data/geophysics/` | ~461 MB (7 files) |
| `best.pt` count under outputs trees | **71** files |

Production Render `/data/outputs` size: **unknown** (no SSH). Live registry empty (`checkpoint_available=false`).

### Growth bounds (cited)

- App default uncompressed ZIP guard: **50 GiB** (`upload_limits.py` L27). Compressed byte cap unset by default (infra may still limit).
- One Stage 2.5 registry model ≈ **~27 MB** `best.pt` (+ run experiment dirs can duplicate).
- Geological + training datasets: client-dependent; can dominate disk.

### Recommendation

| Tier | Disk | Reasoning |
|---|---|---|
| **Minimum** | **100 GB** SSD | OS + Docker images (~5–10 GB) + geophysics + several uploads + checkpoints + logs + snapshot room |
| **Recommended** | **200 GB** SSD | Headroom for multi-dataset ZIPs, assessment rasters, backups/snapshots |
| If holding near upload max | Size to **≥ 2× largest expected uncompressed dataset** + 50 GB system | Per 50 GiB ZIP guard |

---

## 5. Checkpoints

### Key files (measured size, mtime, SHA-256)

| Path | Bytes | Modified (local) | SHA-256 | Stage 2.5 assess? |
|---|---|---|---|---|
| `models/ssri-foundation-v1.pt` | 9,205,701 | 2026-09-09 01:28 | `927404169EA2362FAF41184B03C7CE3E1FCCD062732404245B5805DEBE1BAAC7` | **No** — foundation multitask |
| `models/ssri-foundation-v2.pt` | 9,205,701 | 2026-09-09 04:17 | `39B41634B75CD31E9CB85F981FA6FBA33321B4EA8B0E7B74F485362DB140E0B6` | **No** |
| `model/_handover_tmp/best.pt` | 158,065 | 2026-11-19 08:42 | `3556DB1DF083DD0A29EF9A474AD415B43D9C91917F392193737387E6C324501A` | Format 13-ch; **tiny**; handover |
| `.../ssri-model-153f09d946/best.pt` (rehearsal) | 27,022,703 | 2026-11-05 08:35 | `D912027E17ED532687F9D2A2C74FD3C18CA8C812AE49107D939ADE19DDE5D004` | **Yes format**; **synthetic** |
| `.../ssri-model-2e91993348/best.pt` (upload_cap) | 27,022,703 | 2026-11-05 08:19 | `C474958FFB41D38987F111F72B95B22A7C68730D5936F3E4ECEAB9230D0937F3` | Synthetic 13-ch |
| `.../ssri-model-4c809fca35/best.pt` (acceptance) | 27,022,703 | 2026-11-04 23:32 | `9100BC26A31F3F7B8FBD0E99E9B11A025B8F227FDD6C82C668220CCD797A3200` | Synthetic 13-ch |
| `.../ssri-model-1d8b7235a4/best.pt` (e2e v2) | 27,033,135 | 2026-11-05 09:47 | `7F3545F5C3690A7C94BF57ECDD42CDB09F88C52F0A949FA1A0EFFEEF5E110439` | **16-ch — reject** for prod assess |
| `.../ssri-model-b6b516015f/best.pt` (frontend) | 27,026,437 | 2026-11-08 16:53 | `3DDF71338657E4CD4DD4B78E2C5F0ADB3D997188817D694FE1A2C313D13911F8` | **16-ch — reject** |
| `poc/landslide4sense/weights/mobilenetv2.pth` | 26,813,172 | 2026-11-05 08:54 | `A743E627DD68A1409DDDA4AD43B70B53EE92C0D504D16C890E128BA04DC9AB4F` | PoC only |

71 local `best.pt` files exist under rehearsal trees; registry-model hashes are mostly unique copies. Full dump of all 71 hashes omitted for length; method: `Get-FileHash -Algorithm SHA256` on each path.

### Genuine Stage 2.5 production checkpoint?

| Claim | Status |
|---|---|
| Compatible **format** locally (13-ch `model_state_dict` + `model_config`) | **Yes** (synthetics) |
| Scientifically / client genuine production weights | **Not identified** |
| Present on production API registry | **No** — live ready: `active_model_id=null`, `checkpoint_available=false` |

### Compatibility proof (measured, not assumed)

Loaded `ssri-model-153f09d946/best.pt` into `create_ssri_model(SSRIModelConfig(**model_config))` with **strict-compatible** `load_state_dict` (0 missing / 0 unexpected) and CPU forward OK. Matches Stage 2.5 contract `CHANNEL_COUNT=13` (`ml/constants.py` L22–38).

16-channel checkpoints are Stage 2.5-*format* but **incompatible** with live 13-channel assess (`assess.py` L460–468).

### NOT_VALIDATED / promotion

- Local rehearsal `registry.json`: `"scientific_validation_status": "NOT_VALIDATED"`, `"active": false` for listed models.
- Code defaults registration to `NOT_VALIDATED` (`manual_training/registry.py` L126; `runner.py` L164).
- This audit **did not** call activate/promote.
- Production ready still shows no active model.

---

## 6. Background jobs

### Celery surface

| Item | Value | Evidence |
|---|---|---|
| Registered task | **`ssri.execute_job`** only | `tasks.py` L271–274 |
| Queue | `ssri_jobs` | `celery_app.py` L36 |
| Job types handled | `inference`, `training`, `batch` | `tasks.py` L140–204; `JobType` enum |
| Celery `max_retries` | **0** (app-level retry via job store) | `tasks.py` L271 |
| Job `max_attempts` | default **3** | `JobRecord` L50; `.env.example` `SSRI_MAX_ATTEMPTS` |
| Prefetch / concurrency | prefetch 1; concurrency env default 1 | `celery_app.py` |
| Late ack / worker lost | `task_acks_late=True`, `task_reject_on_worker_lost=True` | `celery_app.py` L32–33 |

### Runtime

| Job | Typical (evidence) | Maximum |
|---|---|---|
| Training (synthetic) | **&lt;10 s / epoch** for tiny sets | **Unknown** for real data / 20 epochs |
| Sync assess | Sub-second–few seconds for 128–256; ~5 s forward alone at 1024² CPU | AOI acquisition (GEE/OpenTopo/Whitebox) can dominate — **unknown** without live AOI timing |
| Batch inference | Scales with tile count | Unknown |

**How to measure max runtime:** instrument job `started_at`/`completed_at` in Postgres job store for real workloads; set worker time limits only after measurement.

### Retry and worker death

1. Failure classified retryable → `mark_failed` → if attempts remain → requeue + `send_task` (`tasks.py` L210–247; `retry.py`).
2. Non-retryable → ack and stop.
3. Process kill: Celery late-ack + `reject_on_worker_lost` returns message to queue.
4. Stale RUNNING leases: `LeaseRecoveryService` requeues when `SSRI_LEASE_RECOVERY_ENABLED` (`infrastructure/recovery/service.py`) — **must be scheduled**; default often false in `.env.example`.

Partial filesystem writes mid-job are possible; recovery re-runs the job (idempotency depends on job type). **No promote/side-effect** from this audit.

---

## 7. Dependencies and OS

| Requirement | Detail |
|---|---|
| Python | **3.11** (`pyproject.toml` L10; Docker `python:3.11-slim-bookworm`) |
| Runtime apt (Dockerfile) | `curl`, `libexpat1`, `libsqlite3-0`, `libcurl4`, `libssl3`, `zlib1g` |
| Build apt | `build-essential`, `curl`, `git` |
| WhiteboxTools | Downloaded into site-packages at image build (`Dockerfile` L67–70) |
| CUDA / drivers | **Not required** for CPU image |
| GDAL system package | Not installed in Dockerfile; **rasterio** wheels typically bundle GDAL — verify on bare Ubuntu with `python -c "import rasterio"` |
| Extra native risk on bare metal | `netcdf4`, `pyproj` may need system libs if wheels fail; prefer **same Docker image** on the VPS |

**Simplest VPS install path:** Docker Engine + Compose (or two containers/`docker-entrypoint.sh` roles `api` and `worker`) sharing a host volume mounted at `/data/outputs`.

---

## 8. Recommendation

### Specs

| | Minimum | Recommended |
|---|---|---|
| vCPU | **4** | **4–8** |
| RAM | **8 GB** | **16 GB** |
| Disk | **100 GB** SSD | **200 GB** SSD |
| GPU | **No** | **No** on the VPS |

**Reasoning:** Assess is CPU-forced; Docker ships CPU torch; 1024² forward approached ~2 GB RSS alone; API+worker need headroom; disk must absorb multi-GB geospatial uploads (50 GiB uncompressed guard).

### If GPU is wanted

| Part | On VPS? | Alternative |
|---|---|---|
| Inference / assess | Stay **CPU on VPS** | N/A |
| Large training runs | Optional | Rent a **GPU instance** for training, copy `best.pt` to VPS `/data/outputs/training/models/...`, then activate on VPS |

### Engineering work before single-VPS go-live (not done here)

1. Provision VPS; mount durable `/data/outputs`; run **api** + **worker** from `model/Dockerfile` with shared volume.  
2. Point env at Supabase `SSRI_DATABASE_URL` and Upstash Redis (`SSRI_REDIS_URL` / Celery URLs); `SSRI_EXECUTION_MODE=distributed`.  
3. Copy geophysics / credentials as needed; set live acquisition flags if AOI assess is required.  
4. Place a **13-channel Stage 2.5** `best.pt` under training registry and **activate** (ops step — preserves `NOT_VALIDATED` unless science says otherwise).  
5. Enable lease recovery process if you want stale-job healing (`recovery` entrypoint).  
6. Confirm process supervisor (systemd/Docker restart), reverse proxy/TLS, and disk monitoring.  
7. Do **not** activate 16-channel schema-v2 checkpoints for production assess.

---

## Measured vs inferred (honesty box)

| Item | Class |
|---|---|
| Param count, ckpt load, forward shapes/times, RSS by tile, SHA-256 of key files, dir sizes, live `/ready` | **Measured** |
| Assess device=cpu, Celery settings, upload 50 GiB, Docker apt list, NOT_VALIDATED defaults | **Cited** |
| 8/16 GB VPS sizing, 100/200 GB disk, concurrent API+worker peaks, real training duration | **Inferred** / partially unknown |
| Production `/data/outputs` contents, real client upload sizes, GPU speedup factor | **Unknown** — measure on VPS / with client data |

---

## Bottom line

A **CPU-only VPS with 4+ vCPU, 16 GB RAM, 200 GB disk** is the evidence-backed default for API+worker on a shared filesystem. **GPU is not required** for production assess and is optional for training. There is still **no promoted production Stage 2.5 checkpoint** on the live API; local 13-ch synthetics prove CPU load compatibility only.
