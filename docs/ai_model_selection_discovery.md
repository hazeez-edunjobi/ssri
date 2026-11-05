# SSRI — Open-Source AI Model Selection: Technical Discovery

**Report date:** 2026-11-02  
**Scope:** Discovery and technical reporting only. No model download, install, fine-tune, or deployment was performed.  
**Scientific status:** NOT_VALIDATED — research-ready engineering pipeline; not production-qualified hazard advice.

---

## 1. Executive summary

SSRI already has a dedicated geospatial hazard model (`SSRIModel`, ~2.25M parameters, 13-channel U-Net) wired into assess, inference, and Manual Training. The largest product gaps today are **data quality and scientific validation**, **deployment/auth/CORS configuration**, and **probability-contract consistency**—not the absence of a large language model.

OpenAI’s open-weight models (`gpt-oss-20b`, `gpt-oss-120b`) are real, Apache-2.0-licensed language/reasoning models. They **cannot** replace the 13-channel segmentation model. They also exceed practical CPU-only Render hosting for always-on inference (`gpt-oss-20b` is documented around **16 GB** memory for the quantized weights alone).

**Recommendation: Option 4 — Hybrid architecture**, executed in this order:

1. **Retain and repair** the existing geospatial stack (data, Stage 2.5 checkpoint, softmax contract, production auth/CORS, readiness).
2. **Do not replace** hazard scores with an LLM.
3. **Optionally add** a small open-weight language model later for explanations/reports only, grounded on SSRI’s structured assessment JSON—prefer a **≤3B** class model if hosting on CPU, or OpenAI `gpt-oss-20b` only if a **≥16 GB** GPU/host is budgeted.
4. Treat EO foundation models (Prithvi, Clay) as a **separate research track** for feature encoding / transfer, not as a drop-in assess replacement.

Smallest next step before any model integration: fix production CORS (`https://ssri-gamma.vercel.app`), obtain a legitimate assess API key, verify one authenticated live inference, and correct assess-path sigmoid vs runner softmax.

---

## 2. Current SSRI architecture and verified status

### 2.1 What SSRI does (user → result)

**Verified path (account product):**

1. User signs in (Supabase) → `/workspace`, `/dashboard`, `/training`, `/datasets`, `/models`.
2. Assessment (`/dashboard`): point/polygon (and optional features/checkpoint paths) → `POST /api/v1/assess` with **API key** (`NEXT_PUBLIC_SSRI_API_KEY`), not the Supabase session (`frontend/lib/api.ts`).
3. API (`model/src/ssri_model/api/routes/assess.py`):
   - Auth → optional **demo** short-circuit if `SSRI_DEMO_MODE` → else load checkpoint → MC-dropout / attribution → hazard profiles + template explanation → response.
4. Live acquisition (when enabled): GEE spectral + OpenTopography/GEE DEM + local gravity/magnetics → FeatureStack (13 channels) → model.
5. Offline: prepared `.npy` / paths.
6. Manual Training: Stage 2.5 ZIP or platform CSV → validate → `Trainer` → checkpoint (`NOT_VALIDATED`).

**Authoritative code:** `model/` (`ssri_model`). Deprecated: root `api/`, `worker/`. Frontend: `frontend/`. Compose: `infra/docker-compose.yml`.

### 2.2 Feature status (evidence-based)

| Area | Status | Evidence |
|------|--------|----------|
| Marketing site | Implemented | `frontend/app` marketing routes |
| Auth UI + Supabase accounts | Implemented | `frontend/app/login`, platform routes |
| Assessment map UI | Implemented | `frontend/app/dashboard` |
| Assess API software path | Implemented | `api/routes/assess.py` |
| Live FeatureStack acquisition | Implemented, gated | `SSRI_LIVE_ACQUISITION_ENABLED` default false (`.env.example`) |
| Demo assessment | Implemented, gated | `SSRI_DEMO_MODE` → `api/demo_assessment.py` |
| Manual Training (account + operator) | Implemented | `/training`, `/training/operator`, `manual_training/` |
| Deployed API health | Verified previously | `GET /api/v1/health` 200 on Render |
| Deployed ready | Often 503 | Infra deps; readiness ≠ model loaded (`api/routes/health.py`) |
| Authenticated production inference | **BLOCKED** historically | No legitimate API key in local env; CORS blocks browser |
| Scientific validation gates | **Failed / incomplete** | `docs/SCIENTIFIC_VALIDATION_REPORT.md`, scorecard |
| Public SDK / `/v1/hazard` marketing | Not shipped as claimed | `About.md` |

### 2.3 Genuine prediction vs demo vs fixture

| Mode | What it returns | When |
|------|-----------------|------|
| Demo | Hardcoded Lagos-style presentation scores | `SSRI_DEMO_MODE=true` after auth |
| Live / offline assess | Model forward pass on FeatureStack or files | Checkpoint loadable as Stage 2.5 |
| Prior Lagos qualification | **Fixture checkpoint** tagged for engineering | Documented in `docs/production_qualification.md` — not scientific validation |

**Inference:** Software can produce genuine model outputs. Scientific accuracy of those outputs is **not** established. Fixture/demo must not be sold as validated geology.

### 2.4 Problems by layer (not all “model”)

| Layer | Issues |
|-------|--------|
| **Model / science** | No production Stage 2.5 three-class checkpoint proven in deploy; foundation multitask checkpoint is a different contract; source AUC 0.750 &lt; 0.88; ECE 0.094 &gt; 0.08; African transfer not measured; spectral channels all-nodata in USGS v3 stacks (prior audit) |
| **Probability contract** | Assess / MC-dropout uses `torch.sigmoid`; geospatial runner uses softmax (`uncertainty/__init__.py`, `evaluation/predictions.py`) |
| **Uncertainty** | Default `dropout=0.0` → MC std often zero |
| **API / auth** | Assess needs API key; platform needs Supabase; CORS must allow frontend origin |
| **Infra** | Render cold start; `/ready` 503 when Postgres/Redis unhealthy; CPU-only Docker image |
| **Frontend** | Connection errors when CORS/preflight fails; API key env may be absent on Vercel |
| **Config** | Live acquisition off by default; gravity still WGM2012 not EIGEN-6C4 |

### 2.5 What a working client version should enable

Without claiming scientific validation, a working engineering product should let a client:

1. Sign in and manage datasets/runs.
2. Upload a valid Stage 2.5 / trainable CSV package and train (status remains NOT_VALIDATED).
3. Run an authenticated assessment for a chosen AOI when data + checkpoint exist.
4. See scores, drivers, and an explicit research disclaimer.
5. Optionally promote an operator checkpoint for assess paths that read the active path.

---

## 3. Current model and prediction-pipeline audit

### 3.1 Architecture

| Item | Value | Source |
|------|-------|--------|
| Class | `SSRIModel` | `architecture/model.py` |
| Type | Lightweight U-Net (encoder / decoder / segmentation head) | same |
| Parameters | **2,246,659** total/trainable | `count_parameters(create_ssri_model())` this session |
| Config defaults | `in_channels=13`, `num_classes=3`, `base_channels=32`, `num_encoder_stages=3`, `dropout=0.0`, group norm, ReLU | `architecture/config.py` |
| Research sibling | `SSRIMultiTaskModel` (landslide / subsidence / **liquefaction**) | `architecture/multitask.py` — **not** assess-loadable |

### 3.2 Inputs

| Item | Contract |
|------|----------|
| Shape | `(B, 13, H, W)` float tensor |
| Channels | `CHANNEL_NAMES` in `ml/constants.py` (elevation → magnetics) |
| Nodata | `FEATURE_NODATA = -9999.0` |
| Validation | Rank + channel count only; no semantic channel identity check |
| Normalization | Via statistics when provided (`normalize_feature_stack`) |
| CRS / resolution | Typically 30 m UTM in FeatureStack / manifests; CSV requires explicit CRS |

### 3.3 Outputs / post-processing

| Path | Activation | Notes |
|------|------------|-------|
| Geospatial runner | Softmax over classes | Mutually exclusive 3-class contract |
| Assess / MC-dropout / geotiff branch | Sigmoid | **Inconsistent** with MaskedCrossEntropy training |
| Labels | 0 subsidence, 1 landslide, 2 sinkhole; label nodata −1 | `LABEL_NODATA` |
| Explanation | Template from drivers + tiers | `build_template_explanation` — not an LLM |

### 3.4 Training data and checkpoints

| Asset | Role | Provenance / status |
|-------|------|---------------------|
| Stage 2.5 dataset layout | Assess + Manual Training | `manifest.json`, `statistics.json`, train/validation tiles |
| USGS landslide FeatureStacks v3 | Foundation pilot | n=240; landslide presence/pseudo-absence; **not** three-class sinkhole GT |
| `models/ssri-foundation-v2.pt` | Multitask research | Loadable by multitask; **rejected** by assess loader (`model_config` / key layout) |
| Manual Training `best.pt` | Stage 2.5 assessable | Produced per run; scientific_status NOT_VALIDATED |
| E2E fixture checkpoint | Prior live Lagos qualify | Explicit fixture flag — engineering only |

**Ground truth for three hazards:** suitable labelled three-class production GT is **absent** from the research scorecard for African/target use. USGS stacks are landslide-oriented. Reliable multi-hazard ground truth must be treated as missing for scientific claims.

### 3.5 Metrics (existing)

From `docs/SCIENTIFIC_VALIDATION_REPORT.md` (foundation experiment `20260909T025912Z`):

- Test tile ROC-AUC **0.750** (gate ≥0.88 **failed**)
- ECE **0.094** (gate ≤0.08 **failed**)
- Spatial split audited; pseudo-absence methodology documented

Unit/integration tests validate software behaviour; they do **not** establish geological accuracy.

### 3.6 Can the current architecture support required hazards without replacement?

**Yes, as software.** `SSRIModel` is designed for the three mutually exclusive classes. What is missing is **defensible labelled data**, a **promoted Stage 2.5 checkpoint**, consistent **softmax** post-processing on assess, and **scientific gates**. Replacing it with a language model would not close those gaps.

---

## 4. Product requirements and required AI capabilities

| Cap | Need now? | Needs | LLM value? | Evidence of correctness |
|-----|-----------|-------|------------|-------------------------|
| **A. Geospatial prediction** | **Required** | Geospatial model + data | No — LLM must not invent scores | Spatially held-out metrics vs labelled rasters; gates in scorecard |
| **B. Geospatial data interpretation** | Partial (drivers) | Attribution software; optional LLM phrasing | Low–medium if grounded | Attribution matches channel ablations; no invented geology |
| **C. NL explanations** | Nice-to-have (templates exist) | Templates today; LLM optional | Medium for fluency | Grounded on JSON only; refusal of unverified claims |
| **D. Conversational UI** | Proposed / not core | LLM + tool calling | Medium later | Answer only from returned assess/training records |
| **E. Report generation** | Nice-to-have | Templates or LLM | Medium | Same grounding rules |
| **F. Data preparation assist** | Useful | Conventional validators + optional LLM | Low–medium | Validation suite already in `manual_training/validation.py` |
| **G. Model training** | Required (existing) | `Trainer` / Stage 2.5 | No LLM | Job completes; checkpoint loads; metrics logged; still NOT_VALIDATED |
| **H. Software assistance** | Internal | Any LLM offline | High for ops | Correct diagnosis of logs (CORS, ready 503, etc.) |

**Do not use one model for everything.** A and G stay with `SSRIModel` + trainer. C/D/E/H are the only places an open-weight LLM is a fit.

---

## 5. Confirmed hardware and deployment constraints

### Confirmed

| Fact | Evidence |
|------|----------|
| Frontend host | Vercel — observed origin `https://ssri-gamma.vercel.app` |
| API host | Render — `https://ssri-api.onrender.com` (service ssri-inference) |
| Worker | Railway / Celery in distributed mode (prior ops; Compose defines worker) |
| API image | `model/Dockerfile`: **Python 3.11**, **CPU-only torch** (`torch==2.5.1` CPU wheel) |
| Framework | PyTorch ^2.0 in `pyproject.toml`; Poetry package `ssri-model` |
| Local Compose | Postgres 16, Redis 7, API+worker, no GPU service |
| Training | Local executor and/or Celery worker; Manual Training uses Stage 2.5 `Trainer` |
| Assess explanations | Server-side templates; no LLM dependency today |
| CORS | Production requires explicit `SSRI_CORS_ORIGINS` / `CORS_ORIGINS` (`api/app.py`) |

### Unknown — must be checked before LLM hosting decisions

| Item | Why it matters |
|------|----------------|
| Render plan CPU count and RAM | Whether any LLM fits beside FastAPI |
| Whether Render instance has a GPU | Official Docker path is CPU-only |
| Railway worker RAM/GPU | Training/inference offload capacity |
| Disk quotas for multi‑GB weights | gpt-oss / Prithvi / Clay sizes |
| Production latency SLO | LLM would dominate response time |
| Developer PC RAM/GPU | Local PoC feasibility |

**Do not assume** the developer laptop matches Render.

### Practical implication

Hosting **gpt-oss-20b** (documented ~16 GB memory for MXFP4 MoE weights) on the current CPU Render API image is **not practical** without a new GPU-capable service. Smaller ≤3B instruct models are the only realistic co-located LLM class if staying on modest CPU RAM—and even then RAM must be measured, not assumed.

---

## 6. What “free and open source” means here

| Category | Meaning for SSRI |
|----------|------------------|
| 1. Free-to-download open weights | Weights obtainable without paid download; e.g. Hugging Face |
| 2. Truly open-source / permissive | License allows commercial use with clear terms (e.g. Apache-2.0). “Open-weight” ≠ always OSI “open source” for all artifacts |
| 3. Free hosted API tiers | Quotas; data leaves SSRI; not preferred for client geospatial data |
| 4. Paid hosted inference | Ongoing cost; not “free” |
| 5. Local / private inference | Weights on SSRI infra; no third-party send of FeatureStacks |

**SSRI preference for client geospatial data:** category **1+2+5**. Avoid sending AOI feature stacks to third-party LLM APIs unless contractually approved.

OpenAI Help Center explicitly: gpt-oss weights are free to download under Apache 2.0 + usage policy; **you pay compute**; models are **not** on the OpenAI ChatGPT/API product surface.

---

## 7. OpenAI open-weight model assessment

Verification date: **2026-11-02**. Sources: [OpenAI Introducing gpt-oss](https://openai.com/index/introducing-gpt-oss/), [OpenAI Help: gpt-oss](https://help.openai.com/en/articles/11870455-openai-open-weight-models-gpt-oss), [GitHub openai/gpt-oss](https://github.com/openai/gpt-oss), [HF openai/gpt-oss-20b](https://huggingface.co/openai/gpt-oss-20b).

| Criterion | gpt-oss-20b | gpt-oss-120b |
|-----------|-------------|--------------|
| Exact name | `openai/gpt-oss-20b` | `openai/gpt-oss-120b` |
| Primary capability | Text reasoning, tools, structured outputs | Same, larger |
| SSRI role | **Language only**: explanations, reports, ops Q&A grounded on SSRI JSON | Same if GPU budget allows |
| License | Apache 2.0 (+ gpt-oss usage policy) — commercial use permitted per OpenAI docs | Same |
| Size | ~21B total / 3.6B active (MoE) | ~117B / 5.1B active |
| Runtime memory (official) | “within **16GB**” (MXFP4) | “within **80GB**” (single H100-class) |
| CPU inference | Possible via Ollama/llama.cpp stacks but **heavy**; not suitable for shared free Render CPU beside assess | Not practical on CPU API |
| GPU | Strongly preferred | Required class: ~80 GB |
| Fine-tuning | Documented; 20b on “consumer hardware” per HF card | H100-node class |
| Integration effort | **High** on current Render CPU API | **Very high** |
| Scientific suitability for hazards | **Unsuitable** as score generator | Same |
| Main risks | Hallucinated hazard claims; memory; harmony format requirement; cold-start | Cost; overkill |

**Verdict:** Investigate first as requested — **fit for language layer only**, and only with dedicated hardware. **Not** a replacement for `SSRIModel`.

---

## 8. Alternative model comparison

### Language models (explanations / reports)

| Criterion | Llama-3.2-3B-Instruct | Notes |
|-----------|----------------------|-------|
| Exact name | `meta-llama/Llama-3.2-3B-Instruct` | HF gated |
| Role | Grounded NL explanations | Same SSRI role as gpt-oss but smaller |
| License | Llama 3.2 Community License — commercial with conditions (attribution, AUP, 700M MAU clause) | **Not** Apache-2.0; legal review advised |
| Disk / RAM (published HF blog) | BF16 ~6.5 GB; INT4 ~1.75 GB weights | Still need headroom for KV cache |
| CPU | More plausible than gpt-oss-20b | Measure on target host |
| Scientific hazard use | Unsuitable as predictor | |

Other small instruct models (Qwen2.5-3B, etc.) may be evaluated similarly; license must be re-checked at selection time.

### Geospatial / EO foundation (augmentation research — not drop-in assess)

| Criterion | Prithvi-EO-2.0 | Clay v1.5 |
|-----------|---------------|----------|
| Exact name | e.g. `ibm-nasa-geospatial/Prithvi-EO-2.0-300M` | Clay Foundation Model v1.5 |
| Primary capability | EO ViT MAE; HLS 6-band pretrain | Multi-sensor embeddings |
| SSRI role | Possible **encoder research** for spectral features — **not** 13-channel SSRI contract | Embeddings / fine-tune research |
| License | Apache-2.0 (HF cards / NASA-IMPACT materials) | Apache-2.0 for current weights (older Clay versions may be OpenRAIL-M — pin version) |
| Input mismatch | 6 HLS bands ≠ SSRI 13 channels (terrain + gravity + magnetics) | Sensor stacks ≠ SSRI FeatureStack |
| Integration effort | **High** (new head, new data, new loader) | **High** |
| Scientific suitability | Only after labelled fine-tune + spatial eval | Same |
| Main risks | Channel contract break; GPU; false “foundation = validated hazard” narrative | Same |

**Neither** replaces Manual Training’s Stage 2.5 path without a multi-month research programme.

### Scorecard vs SSRI needs

| Model | Fits A (predict)? | Fits C/E (language)? | Fits current CPU Render? | Priority |
|-------|-------------------|----------------------|--------------------------|----------|
| Existing `SSRIModel` | **Yes (software)** | No | Yes (~2.2M params) | **Keep / fix** |
| gpt-oss-20b | No | Yes | Unlikely without ≥16GB dedicated | Optional later |
| gpt-oss-120b | No | Yes | No | Out of scope now |
| Llama-3.2-3B-Instruct | No | Yes | Maybe (measure) | Better PoC LLM size |
| Prithvi / Clay | Only after redesign | No | Unlikely on free CPU | Research track |

---

## 9. Recommended architecture: which component does what

```text
Client AOI / dataset
        │
        ▼
Conventional geospatial pipeline (FeatureStack / Stage 2.5 tiles)
        │
        ▼
SSRIModel (Stage 2.5)  ──►  softmax probabilities, drivers, uncertainty*
        │
        ▼
Structured assessment JSON (scores, CRS, checkpoint id, disclaimer)
        │
        ▼
[Optional] Small open-weight LLM  ──►  plain-language summary / report
        │         (must cite JSON fields; refuse new scores)
        ▼
Frontend dashboard / PDF
```

\*Fix dropout/calibration separately; do not invent uncertainty.

| Task | Component |
|------|-----------|
| Susceptibility scores | `SSRIModel` + softmax |
| Nodata / CRS / channels | Conventional validation |
| Training | Existing `Trainer` |
| Explanations (v1) | Keep `build_template_explanation` |
| Explanations (v2) | Optional LLM on JSON |
| Chat / reports | Optional LLM + tools |
| Ops diagnosis | Offline LLM or human |

---

## 10. Proposed proof of concept and acceptance criteria

### PoC A — Language layer (only after infra/auth works)

- **Task:** Generate a client-facing paragraph from a **frozen** assess JSON fixture (known scores, drivers, `NOT_VALIDATED`).
- **Input:** Real schema fields from `assess` response (no raw FeatureStack to the LLM).
- **Baseline:** Current `build_template_explanation` output.
- **Metrics:** (1) No numeric score outside JSON ±0; (2) all three class names correct; (3) disclaimer present; (4) latency/RAM on the **intended** host; (5) human review for unsupported geology claims.
- **Pass:** 10/10 fixture cases with zero invented scores; RAM within measured host budget; p95 latency acceptable for async report job (not blocking map click unless budgeted).
- **Fail / rollback:** Any invented susceptibility; OOM on target host; dependency conflicts with CPU torch image.

### PoC B — Geospatial (no LLM)

- **Task:** Authenticated production assess with Stage 2.5 checkpoint; softmax sum≈1; perturbation changes output.
- **Ground truth:** If three-class GT missing, this is **software verification only** — say so explicitly.
- **Pass:** Authenticated 200; checkpoint id recorded; softmax contract; scientific_status remains NOT_VALIDATED.
- **Fail:** Demo/fixture silent path; sigmoid-only sums ≠1; CORS/auth block.

### PoC C — EO foundation (research only; optional later)

- Spatially blocked fine-tune on labelled data matching the **actual** input bands used.
- Compare to current `SSRIModel` baseline on same splits.
- **Do not** promote to assess without beating baseline on held-out spatial blocks and legal/product review.

---

## 11. Known blockers and missing information

1. Production CORS must include `https://ssri-gamma.vercel.app`.
2. Legitimate production API key for assess (never commit secrets).
3. Confirmed Stage 2.5 assessable checkpoint on Render disk/path.
4. Assess sigmoid vs runner softmax defect still in source.
5. Three-class labelled GT and African transfer data incomplete.
6. Render/Railway exact CPU/RAM/GPU **unknown**.
7. Developer workstation GPU/RAM **unknown**.
8. Live acquisition credentials and geophysics paths must be configured for live AOIs.
9. Domain similarity often uncalibrated without centroid path.

---

## 12. Sources and verification dates

| Source | Used for | Date |
|--------|----------|------|
| Repo: `architecture/model.py`, `config.py`, `ml/constants.py` | SSRIModel contract | 2026-11-02 |
| `count_parameters(create_ssri_model())` | 2,246,659 params | 2026-11-02 |
| `api/routes/assess.py`, `uncertainty/__init__.py`, `inference/runner.py` | Pipeline / activations | 2026-11-02 |
| `model/Dockerfile` | CPU-only torch deploy | 2026-11-02 |
| `docs/SCIENTIFIC_VALIDATION_REPORT.md`, `SSRI_COMPLETION_SCORECARD.md` | Metrics / gates | as of 2026-09-09 docs |
| OpenAI gpt-oss announcement + Help Center + HF + GitHub | OpenAI open weights | 2026-11-02 |
| HF / NASA-IMPACT Prithvi-EO-2.0 | EO alternative | 2026-11-02 |
| Clay Foundation docs + GitHub | EO alternative + Apache-2.0 | 2026-11-02 |
| Meta Llama 3.2 HF blog / license | Smaller LLM alternative | 2026-11-02 |
| Browser CORS error origin | `https://ssri-gamma.vercel.app` | 2026-11-02 |

---

## 13. Final recommendation

### **Option 4 — Hybrid architecture**

**Trade-offs**

| Option | Trade-off |
|--------|-----------|
| 1 Retain only | Correct for hazard core; misses fluent reports/chat until templates suffice |
| 2 Add LLM only | Improves language; **fails** if used to “make predictions work” |
| 3 Replace geospatial model | High cost/risk; no labelled PoC yet; channel mismatch with EO FMs |
| **4 Hybrid** | Keeps correct predictor class; adds language where LLMs help; matches hardware reality |

**Smallest practical next step (no new model yet)**

1. Set `SSRI_CORS_ORIGINS=https://ssri-gamma.vercel.app` on Render; verify OPTIONS preflight returns `Access-Control-Allow-Origin`.
2. Configure a legitimate API key for assess; run one authenticated inference.
3. Fix assess-path probability transform to softmax for `SSRIModel`.
4. Promote/train a real Stage 2.5 checkpoint; keep `NOT_VALIDATED`.
5. Only then run **PoC A** with a **small** open-weight LLM (or defer language to templates).

**Do not** download gpt-oss onto the current Render API service until RAM/GPU are confirmed.

---

## Concise answer (selection question)

**What is the most practical free, legally usable AI model or combination that can make SSRI work better, on which hardware, for which tasks, and what must we fix first?**

- **Combination:** Keep **`SSRIModel` (~2.25M, CPU-friendly)** for subsidence / landslide / sinkhole scores; optionally add later a **small open-weight instruct LLM** (e.g. Llama-3.2-3B-class, or OpenAI **`gpt-oss-20b` only on ≥16 GB dedicated memory**) for explanations/reports grounded on assessment JSON. Do **not** use OpenAI gpt-oss or any LLM to invent hazard probabilities. EO foundations (Prithvi/Clay, Apache-2.0) are a separate research track, not a drop-in.
- **Hardware:** Production API is **CPU torch** today; exact Render RAM/GPU are **unknown** and must be measured. gpt-oss-20b needs ~16 GB class memory per OpenAI; 120b needs ~80 GB GPU class.
- **Fix before integrating any new model:** CORS for `https://ssri-gamma.vercel.app`, assess authentication, Stage 2.5 checkpoint path, softmax contract, and honest labelled-data plan. Without those, a new AI model will not make SSRI “work.”

**Awaiting review and approval before any implementation or weight download.**
