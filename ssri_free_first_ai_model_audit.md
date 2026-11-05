# SSRI — Free-First AI Model Audit and Integration Plan

**Date:** 2026-11-03  
**Scope:** Read-only investigation and planning. No code changes, installs, training, live provider API calls, or charges.  
**Related prior report:** `docs/ai_model_selection_discovery.md` (2026-11-02). Defects below were **re-checked in the repository on this date**.

**Scientific status:** NOT_VALIDATED

---

## 1. Executive recommendation

**Outcome: AUGMENT**

Keep the existing `SSRIModel` geospatial engine for numerical hazard scores. Do **not** replace it with a language model or an off-the-shelf EO foundation model.

Add an **optional, server-side explanation layer** that:

1. Receives only structured assessment JSON (scores, drivers, warnings, disclaimers)—never full 13-channel rasters.
2. Calls a **free hosted LLM** when explicitly enabled and within quota.
3. Falls back to the existing template explanation (`build_template_explanation`) when the provider is missing, rate-limited, timed out, or disabled.
4. **Never** auto-switches to a paid provider.

**Best free-first candidate (language only):** Google **Gemini API Free Tier** (Flash-class model selected in AI Studio at enablement time) for hosted text generation with free input/output tokens within documented free-tier limits.

**Least expensive viable fallbacks (in order):**

1. Existing SSRI **template explanations** (zero AI cost; already shipped).
2. **Groq** free-plan inference for `openai/gpt-oss-20b` (or other free-listed models)—strong speed; confirm org limits in console.
3. **Cloudflare Workers AI** free allocation (10,000 Neurons/day)—good if already on Cloudflare; neuron budget is tight for chatty use.
4. **Local Ollama** with a small instruct model (e.g. Llama 3.2 1B/3B)—API-fee free; needs developer/host RAM; not assumed available on Render CPU API.
5. Paid Gemini / Groq Developer / Workers Paid—**only** when `SSRI_LLM_ALLOW_PAID=true` (or equivalent) is set deliberately.

**Do not use Cerebras as the default “free” path:** official docs describe a **$5 Free Trial** requiring a verified payment method, with **no permanent free tier**.

**REPLACE is not justified.** No free or pretrained model was found that matches SSRI’s 13-channel contract and three hazard classes with scientific evidence.

---

## 2. Verified current SSRI architecture and blockers

### 2.1 What the engine predicts

| Item | Verified fact | Evidence |
|------|---------------|----------|
| Model | `SSRIModel` lightweight U-Net | `model/src/ssri_model/architecture/model.py` |
| Parameters | ~2.25M | Prior session `count_parameters`; architecture unchanged |
| Inputs | `(B, 13, H, W)` | `_validate_input`; `CHANNEL_COUNT` |
| Channel order | elevation, slope, plan_curvature, profile_curvature, twi, relative_relief, valley_depth, ndvi, ndwi, clay_mineral_ratio, iron_oxide_index, gravity, magnetics | `ml/constants.py` `CHANNEL_NAMES` |
| Classes | 0 subsidence, 1 landslide, 2 sinkhole | Stage 2.5 / training requirements |
| Nodata | Feature `-9999`; label `-1` | `FEATURE_NODATA`, `LABEL_NODATA` |
| Dropout default | `0.0` | `SSRIModelConfig` |
| Explanations today | Template string from drivers/tiers | `uncertainty/__init__.py` `build_template_explanation` |

### 2.2 Checkpoints and paths

| Path | Status |
|------|--------|
| Geospatial runner | Softmax via `logits_to_probabilities` (`evaluation/predictions.py`) |
| Assess + MC-dropout | Still **`torch.sigmoid`** (`assess.py` ~272; `uncertainty/__init__.py` ~197, ~231) — **unchanged defect** |
| Foundation multitask `.pt` | Different contract; not assess-loadable |
| Demo mode | `SSRI_DEMO_MODE` → hardcoded presentation (`demo_assessment.py`) |
| Manual Training | Stage 2.5 ZIP / platform CSV → `Trainer` → `NOT_VALIDATED` |
| Deploy | Frontend Vercel (`ssri-gamma.vercel.app`); API Render CPU Docker (`model/Dockerfile`); auth: API key for assess, Supabase for platform |

### 2.3 Reusable without modification (for an LLM augment)

- Assess response schema fields (hazard profiles, drivers, scientific status).
- `build_template_explanation` as mandatory fallback.
- Existing API-key / Supabase boundaries (LLM called **after** auth, server-side only).
- Manual Training validators (LLM may *explain* errors; must not replace validation).

### 2.4 Blockers (still present)

1. Assess sigmoid vs runner softmax.
2. Dropout 0 → non-stochastic MC uncertainty.
3. Scientific gates unmet; three-class GT / African transfer incomplete.
4. Production CORS / API key issues for browser→API (ops, not model weights).
5. No proven production Stage 2.5 checkpoint on Render from this audit (not re-probed live today).

---

## 3. Free hosted API comparison

Research method: official documentation only; **no live API calls**. Quotas change; confirm in each provider console before enablement.

| Candidate | Model/provider | Free allowance (documented) | Paid fallback | Hardware needed | Main limitations |
|-----------|----------------|----------------------------|---------------|-----------------|------------------|
| **Gemini API Free** | Google AI Studio / Gemini Developer API; Flash-class IDs vary by account | Free tier: free input/output tokens for eligible models; RPM/TPM/RPD **per project**, shown in AI Studio; RPD resets midnight Pacific | Paid tiers with billing account | None (hosted) | Free-tier **content may be used to improve Google products** (pricing page); limits not a fixed public table; rate limits “not guaranteed” |
| **Groq Free** | e.g. `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b` (per rate-limits table) | Org-level RPM/RPD/TPM/TPD; example for gpt-oss-20b on docs table: **30 RPM, 1K RPD, 8K TPM, 200K TPD**; exact org limits on console Limits page | Developer plan for higher limits / Batch | None (hosted) | Quotas can exhaust quickly; model list changes; confirm commercial ToS; 429 when exceeded |
| **Cloudflare Workers AI Free** | e.g. `@cf/meta/llama-3.2-1b-instruct`, `@cf/meta/llama-3.2-3b-instruct`, plus other free-plan models | **10,000 Neurons/day** free; reset 00:00 UTC | Workers Paid $0.011 / 1,000 Neurons above free; some frontier models require Paid | None (hosted) | Neuron budget small; some models Paid-only; text-gen default ~300 RPM (paid models lower) |
| **Cerebras Free Trial** | e.g. `gpt-oss-120b`, `qwen-3.8-27b` | **$5 credits**, payment method required, **expires in 30 days**; Free Trial RPM/TPM caps | Pay-as-you-go Developer | None (hosted) | **Not a permanent free tier**; API inactive when credits gone |
| OpenAI ChatGPT/API (comparison) | Proprietary API models | Not a free production LLM API for this use | Pay-per-token | Hosted | Cost; not free-first |
| OpenAI gpt-oss weights | Self-host / third-party host | Weights free (Apache 2.0); hosting not free | GPU host / Groq / CF | High if self-host | Self-host exceeds typical Render CPU |

**Gemini privacy note (verified from Google pricing docs):** Free Tier lists “Content used to improve our products”; Paid Tier generally does not (model-dependent footnotes). For client AOI metadata, prefer redacting coordinates/names or use paid/no-train policies / local fallback when contracts require it.

---

## 4. Local / open-weight comparison

| Candidate | Role | License (summary) | Hardware | Free of API fee? | Fit for SSRI |
|-----------|------|-------------------|----------|------------------|--------------|
| Ollama + Llama 3.2 1B/3B Instruct | Explanations | Llama Community License (gated; commercial conditions) | ~0.75–6.5 GB weights class depending on quant (HF blog figures) | Yes | Dev / optional worker; measure host |
| gpt-oss-20b via Ollama | Explanations | Apache 2.0 + usage policy | ~16 GB class (OpenAI docs) | Yes (weights) | Unrealistic on current Render CPU API |
| Existing `SSRIModel` | **Numerical** hazards | Project code | CPU OK (~2M params) | N/A | **Keep** |

Local production on Render requires confirming instance RAM. Prefer local only as **dev fallback** or a separate optional worker—not inside the slim API container by default.

---

## 5. Geospatial foundation-model comparison

| Candidate | Match to 13-ch SSRI? | Hazard classes | License | Still need fine-tune? | Verdict |
|-----------|----------------------|----------------|---------|----------------------|---------|
| Prithvi-EO-2.0 | No (HLS 6-band) | Not SSRI 3-class out of box | Apache-2.0 | Yes + new head/data | Research only |
| Clay v1.5 | No (multi-sensor EO) | Not SSRI sinkhole/subsidence GT | Apache-2.0 (pin version) | Yes | Research only |
| Generic CV segmenters | No | Unproven on SSRI labels | Varies | Yes | Not a free drop-in |

**Strategy A (replace) fails** on modality mismatch and missing validated hazard inventories.

---

## 6. Replace-versus-augment analysis

### Strategy A — Replace custom model

**Not recommended.** No free pretrained model provides scientifically meaningful, spatially explicit susceptibility for subsidence, landslide, and sinkhole on SSRI’s FeatureStack without substantial new labelled data, fine-tuning, and evaluation. An LLM inventing scores would violate scientific integrity.

### Strategy B — Augment (recommended)

Use a free LLM for:

- Plain-language explanation of **already computed** scores and drivers.
- Dataset upload / validation guidance (from known error codes).
- Feature-layer and disclaimer education from docs.
- Assessment summary paragraphs.

Geospatial engine remains authoritative for numbers. LLM must refuse new scores, calibration claims, or “validated” language when `scientific_validation_status=NOT_VALIDATED`.

### Strategy C — Hybrid providers

Useful later: Gemini (primary) → template fallback; optional Groq as second free host; optional Ollama on laptop. **Do not** build a complex multi-provider mesh in v1. One provider + template fallback is enough.

---

## 7. Cost and quota analysis

Assumptions (stated explicitly):

- Explanation request ≈ 1–2K tokens in + 0.5–1K out (estimate, not measured).
- Low usage ≈ 20 explanations/day; moderate ≈ 200/day; high ≈ 2,000/day.
- No live measurement performed.

| Scenario | Gemini Free | Groq Free (gpt-oss-20b @ 1K RPD) | CF Workers AI (10k neurons/day) | Template only |
|----------|-------------|-----------------------------------|----------------------------------|---------------|
| Dev/test | Likely within free RPM/RPD if sparse | Likely OK | OK if small models | $0 |
| Low (20/day) | Likely free | Within 1K RPD | Depends on neuron cost of model | $0 |
| Moderate (200/day) | Check RPD in AI Studio | Likely OK if under 1K RPD | May exhaust neurons | $0 |
| High (2k/day) | Exceeds typical free RPD → 429 | Exceeds 1K RPD | Exceeds free neurons | $0 |

**Fail-safe rule:** On 429 / timeout / missing key → return template explanation + `llm_status: unavailable`. **Never** charge a paid API unless an explicit paid flag is set.

Hosting costs (Render/Vercel/Railway) already exist; LLM add-on should not require a new GPU for Strategy B with hosted free APIs.

---

## 8. Recommended minimal architecture

```text
Frontend (dashboard)
    → existing POST /api/v1/assess (API key auth)
        → SSRIModel computation (unchanged)
        → assessment JSON
        → [optional] explain_assessment(json)  // new thin module
              → if SSRI_LLM_ENABLED and key present:
                    Gemini (or configured free provider)
              → else / on failure:
                    build_template_explanation(...)
        → response (+ llm_meta: provider|template|error_code)
```

### Untouched

- `SSRIModel`, Trainer, FeatureStack acquisition, Manual Training ingest, JobService, auth systems, frontend auth.

### New (smallest)

| Piece | Responsibility |
|-------|----------------|
| `ssri_model/api/llm/` (proposed) | Provider client, prompt builder, response validator, timeout |
| Config | `SSRI_LLM_ENABLED`, `SSRI_LLM_PROVIDER=gemini|groq|none`, server-only API key, `SSRI_LLM_ALLOW_PAID=false`, timeout ms, max tokens |
| Optional route | `POST /api/v1/assess/explain` **or** optional flag on assess — prefer separate endpoint so assess latency stays stable |

### Contracts

- **Input to LLM:** hazard names, point estimates, confidence tiers, top drivers, warnings, `scientific_validation_status`, short AOI label if user-provided—**no rasters**.
- **Output:** `{ explanation: string, llm_used: bool, provider: string|null, refused_claims: [] }`.
- **Validation:** Reject/regenerate if output contains fabricated numeric scores not in input (simple parse check).

### Security

- Keys only in Render/server env—never `NEXT_PUBLIC_*`.
- Same auth as assess (`require_run_inference`) or platform principal for account features.
- Do not bypass API-key auth; website login ≠ assess authorization.

### Disable path

`SSRI_LLM_ENABLED=false` → templates only; zero provider calls.

---

## 9. Security and scientific-integrity risks

| Risk | Mitigation |
|------|------------|
| LLM invents hazard % | Prompt + post-check against JSON; strip/replace on mismatch |
| Free Gemini trains on prompts | Redact PII/precise coords; disclose; or use paid/no-train / local |
| Silent paid spend | `ALLOW_PAID=false`; no second key for paid endpoints |
| Quota exhaustion | Template fallback; surface `llm_status` |
| Secrets in frontend | Server-only env |
| Claiming scientific validation | Hardcode disclaimer from `NOT_VALIDATED` |
| CORS/auth still broken | Fix ops before shipping LLM UX |

---

## 10. Phased implementation plan

| Phase | Work | Cost |
|-------|------|------|
| **0** | Fix CORS, API key, assess softmax, confirm Stage 2.5 checkpoint path | $0 AI |
| **1** | Add optional explain module + Gemini free + template fallback + unit tests (mocked HTTP) | $0 if free tier |
| **2** | Optional Groq as config-selectable alternate free host | $0 |
| **3** | Optional Ollama for local/dev | Hardware only |
| **4** | Paid only if product usage exceeds free quotas and flag enabled | Explicit |
| **Later / research** | EO foundation fine-tune — separate programme | Compute + labels |

No new DB, queue, auth system, or framework required for Phases 0–2.

---

## 11. Testing and acceptance criteria

| Test | Expect |
|------|--------|
| Happy path (mocked Gemini/Groq) | Explanation grounded; `llm_used=true` |
| Missing credentials | Template; no crash |
| 429 / quota | Template; `llm_status=rate_limited` |
| Timeout / 5xx | Template after bounded retries (≤1–2) |
| Malformed JSON from LLM | Reject; template |
| Fabricated score in text | Detector fails closed to template |
| `ALLOW_PAID=false` | No paid endpoint URLs called (assert in tests) |
| `LLM_ENABLED=false` | Zero outbound LLM HTTP |
| Secrets | Not in responses/logs at info level |
| Regression | Existing assess/training tests still pass |
| Local Ollama (optional) | Latency/RAM recorded; skip if not installed |

**Do not** make live charged calls in CI.

---

## 12. Sources (official / primary)

| Source | URL | Used for |
|--------|-----|----------|
| Gemini rate limits | https://ai.google.dev/gemini-api/docs/rate-limits | Free tier mechanics |
| Gemini pricing / free vs paid / data use | https://ai.google.dev/gemini-api/docs/pricing | Free tokens; improve-products note |
| Groq rate limits | https://console.groq.com/docs/rate-limits | RPM/RPD/TPM table |
| Groq models | https://console.groq.com/docs/models | Model IDs / paid plan context |
| Cloudflare Workers AI pricing | https://developers.cloudflare.com/workers-ai/platform/pricing/ | 10k Neurons/day |
| Cloudflare Workers AI limits | https://developers.cloudflare.com/workers-ai/platform/limits/ | RPM by task |
| Cerebras rate limits / billing | https://inference-docs.cerebras.ai/support/rate-limits ; account-billing | $5 trial; no permanent free |
| OpenAI gpt-oss | https://openai.com/index/introducing-gpt-oss/ | Open weights ≠ free host |
| Prithvi / Clay | Hugging Face / project docs (prior discovery) | EO mismatch |
| SSRI code | paths cited in §2 | Architecture / defects |

Verification date for provider pages: **2026-11-03**.

---

## 13. Unknowns requiring further investigation

1. Exact Gemini free RPD/RPM for the specific Flash model ID at enablement (AI Studio).
2. Whether SSRI’s org ToS / client contracts allow Gemini free-tier data use.
3. Groq console exact free-model list for the SSRI account (docs note exceptions).
4. Render RAM if considering Ollama sidecar.
5. Neuron cost of a typical explanation on Cloudflare for chosen model.
6. Whether production assess currently loads a real Stage 2.5 checkpoint (needs authenticated probe after CORS/key fix).

---

## Final selection

| Field | Value |
|-------|--------|
| **Outcome** | **AUGMENT** |
| **Best free-first candidate** | **Google Gemini API Free Tier** (Flash-class) for optional explanations |
| **Least expensive fallback** | Built-in **template explanations** (always); then **Groq** free `openai/gpt-oss-20b`; then **Cloudflare** 10k Neurons/day; then local **Ollama** small model |
| **Not selected as free default** | Cerebras (trial + card); OpenAI paid API; self-hosted gpt-oss on Render CPU |
| **Engine** | Retain `SSRIModel`; do not REPLACE |

Await approval before any implementation.
