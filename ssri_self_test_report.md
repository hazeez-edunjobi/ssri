# SSRI DEPLOYED SELF-TEST REPORT

Date: 2026-10-01. Read-only. No production behavior was changed. No admin system was added.

Scientific status remains **NOT_VALIDATED**. A healthy HTTP response is not evidence that the model ran, and a passing software check is not evidence that scores predict real ground failure.

## 1. Deployment

| Item | Result |
|---|---|
| Environment | Render API in distributed mode. PostgreSQL connected. Redis connected. Queue reachable. |
| Deployment URL | Not recorded in the repository. `https://ssri.vercel.app` returns 200 but is an unrelated PHP site. |
| API URL | `https://ssri-api.onrender.com` |
| Commit / version | Not exposed by health or ready. Service name is `ssri-inference`. |
| Model | Not loaded in this self-test. |
| Checkpoint | Not observable. |
| Demo mode | Not observable. Unauthenticated calls never reach the demo branch. Repository default is `SSRI_DEMO_MODE=false`. |

Cold `GET /api/v1/health` took about 74s (service wake-up) and returned 200 `{"status":"ok","service":"ssri-inference"}`. A later call took about 2.2s. `GET /api/v1/ready` returned 200 in about 6.4s.

## 2. Authentication

Registration: invalid email is rejected (`400`, invalid format). A password shorter than 6 characters is rejected (`422`). The website form is stricter (12–20 characters with mixed case, a number, and a symbol); that rule is in the client, not in this Supabase response. A later signup with a valid-looking disposable address returned `429 email rate limit exceeded`. No account was created. Password text was not present in the responses.

Email verification: **not tested**.

Login: nonexistent account and wrong password both return `400` with `Invalid login credentials`. Successful login was **blocked** by the rate limit.

Session, workspace, logout: **not tested**. No access token was issued.

Protected API: **pass for rejection**.

- No token on `/api/v1/assess` and `/api/v1/inference`: `401 AUTHENTICATION_REQUIRED`.
- Fake bearer: `401 INVALID_CREDENTIALS`.
- No token on `/api/v1/platform/me`: `401 Sign in to continue.`
- Fake bearer on platform: `401` session invalid or expired.

Bodies were short JSON messages. No stack trace, filesystem path, or credential was returned.

Website login (Supabase) and model routes (API key) are different. `submitAssess` in `frontend/lib/api.ts` sends `NEXT_PUBLIC_SSRI_API_KEY` when that variable exists. It does not send the Supabase session. A signed-in user is not, by that code, authorized to run assess.

## 3. Model

Assess is written for `SSRIModel`: 13 channels, classes subsidence, landslide, sinkhole, cross-entropy. The foundation model is separate: landslide, subsidence, liquefaction, binary heads. They were not treated as the same vocabulary.

The live service never opened a checkpoint. Inference is **blocked**. Local foundation files still fail `load_inference_checkpoint` because they store `state_dict` / `config` rather than `model_state_dict` / `model_config`, and the v2 file still records version `ssri-foundation-v1`.

## 4. Mathematical verification

| Check | Result |
|---|---|
| Probability transform | Repository assess path uses sigmoid. Geospatial runner uses softmax. |
| Softmax verified live | Not tested. The request never reached the model. |
| Probability sum | Not measured live. Sigmoid outputs are not required to sum to 1. |
| Finite outputs | Not tested live. |
| Determinism | Not tested live. Repository `eval()` forward is deterministic. |
| Uncertainty | Default dropout is 0. MC sampling then has no dropout layers. That is not stochastic uncertainty. |

`run_mc_dropout` and the assess GeoTIFF branch call `torch.sigmoid`. `inference/runner.py` calls `logits_to_probabilities` (softmax). Same model family, two transforms.

## 5. Data verification

Channel order is explicit in `CHANNEL_NAMES`. The module does not check that position 8 is NDVI.

Deployed dataset, CRS, and alignment: **not tested**. The API accepts server paths, not an uploaded stack, and those paths were not reachable without credentials.

Local USGS v3, from the prior read-only scan, still has NDVI, NDWI, clay mineral ratio, and iron oxide entirely `-9999` on all 240 stacks. Nothing was filled in.

NaN and Inf rejection on the deployment: **not tested** (authentication stopped the call). In the repository, `SSRIModel.forward` still accepts non-finite tensors.

## 6. API verification

| Endpoint | Status | Auth | Notes |
|---|---|---|---|
| `GET /api/v1/health` | 200 | Public | Does not load a model. |
| `GET /health` | 200 | Public | Same body. |
| `GET /api/v1/ready` | 200 | Public | Infrastructure only. Can be ready while no model is loaded. |
| `POST /api/v1/assess` | 401 | API key | No prediction body. |
| `POST /api/v1/inference` | 401 | API key | Requires checkpoint, features, manifest, and statistics paths. |
| `GET /docs` | 200 | Public | Swagger UI is on. |

## 7. End-to-end

```text
Frontend     BLOCKED  (deployed app URL not identified)
Authentication  PARTIAL  (bad credentials rejected; no session created)
API          PASS for auth rejection; FAIL as a model test
Input validation  NOT REACHED
Model        NOT LOADED
Probability  NOT COMPUTED
Result       NOT RETURNED
```

The chain from user to hazard score was **not** verified.

## 8. Failures

**Real inference was not executed.** Expected a finite 3-class result from `SSRIModel`. Actual: 401 before load. Route: `assess_endpoint` in `model/src/ssri_model/api/routes/assess.py`. Severity: high. Class: blocked for the live numbers, and the self-test cannot claim the model ran.

**Ready does not mean the model loaded.** Expected not-ready when the checkpoint cannot load. Actual: `ready: true` with database and Redis only. Function: `readiness` in `model/src/ssri_model/api/routes/health.py`. Severity: high.

**Assess math is not softmax.** Expected class probabilities that sum to 1. Actual in source: per-logit sigmoid in `run_mc_dropout` (`model/src/ssri_model/uncertainty/__init__.py`), while `inference/runner.py` uses softmax. Severity: high. Live sum was not measured.

**User login does not authorize assess.** Expected the session to call the model. Actual: platform uses the Supabase token; assess uses an API key (`authHeaders` in `frontend/lib/api.ts`). Severity: high.

## 9. Warnings

- Swagger is public on the deployed host.
- Dropout 0 means uncertainty fields must not be described as calibrated stochastic uncertainty.
- Channel meaning is not checked inside the network.
- Foundation v2 metadata still says v1 and cannot be loaded by assess.
- Demo mode on the live process was not readable.
- Unknown-account and bad-password responses match, which is appropriate.

## 10. Final status

**SELF-TEST FAIL**

The API is up, infrastructure is connected, and unauthenticated model calls are rejected. That is not a successful model test. Real inference, softmax behavior on the live service, nodata handling on the live service, and the browser-to-result path were not verified.

## Local software tests

Separate from the deployment. Command:

```text
cd model
SSRI_EXECUTION_MODE=local
poetry run pytest --tb=no -q
```

Result of the re-run on 2026-10-01: **1 failed, 652 passed, 2 skipped, 513.67s**.

The failure was `tests/test_manual_training.py::test_training_api_upload_validate_and_start`. The suite was run with `--tb=no`, so the assertion text was not kept. Running that test by itself afterwards passed in 31.52s. It is not a stable failure, and it is not counted as a pass of the full suite.

The two skips are `tests/test_infrastructure_integration.py`, because `SSRI_INTEGRATION_TESTS` was not set. A skip is not a pass.

## Smallest safe fixes (not applied)

1. Make `/ready` fail when the configured assessment checkpoint cannot be loaded, or stop describing ready as model health.
2. Use softmax in `run_mc_dropout` and the assess GeoTIFF branch for `SSRIModel`, matching the runner and the cross-entropy loss.
3. Reject non-finite tensors and maps smaller than the normalization can handle with an SSRI error, before `forward`.
4. Decide one credential for assess: the signed-in user, or a documented API key. Do not leave the dashboard calling assess without the session.
