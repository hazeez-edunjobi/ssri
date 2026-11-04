# SSRI authenticated production self-test

Date: 2026-10-01

scientific_status: NOT_VALIDATED

This report continues the earlier deployed self-test. It does not replace `ssri_self_test_report.md` or `ssri_self_test_report.json`.

No secrets are recorded. Production code, authentication, model weights, and probability math were not changed.

## 1. Deployment

- API: https://ssri-api.onrender.com
- Service: ssri-inference
- Environment: Render, execution mode distributed (from the earlier `/api/v1/ready` body)
- Deployment/version: not exposed by `/health` or `/ready`

The earlier self-test already recorded:

- GET `/health` 200
- GET `/api/v1/health` 200
- GET `/api/v1/ready` 200
- PostgreSQL connected, Redis connected
- Readiness does not load a checkpoint

Those health calls were not repeated as proof of model execution.

## 2. Authentication

- Credential mechanism: `Authorization: Bearer <API key>`
- Parser: `parse_api_key` in `model/src/ssri_model/auth/credentials.py`
- Expected shape: `ssri_<16 hex key id>_<urlsafe secret of at least 32 characters>`
- Verifier: `authenticate_api_key` in `model/src/ssri_model/auth/dependencies.py`, against the server key store
- Assess and inference dependency: `require_run_inference_rate_limited` in `model/src/ssri_model/api/dependencies.py`
- Platform routes use a separate Supabase access token. That token does not authorize `/api/v1/assess` or `/api/v1/inference`.
- Credential available: NO
- Authenticated request reached API: NO

Checked local sources for an existing key name only (`SSRI_API_KEY`, `NEXT_PUBLIC_SSRI_API_KEY`, `SSRI_AUTH_API_KEY`, `SSRI_TEST_API_KEY`): absent from the process environment, the repo `.env`, and `frontend/.env.local`. Pytest keys in `model/tests/auth_helpers.py` are written into a temporary key store and cannot authenticate Render.

No key was minted. Authentication was not bypassed.

Production model verification: BLOCKED — no legitimate authenticated test credential available.

## 3. Production model

Live checkpoint identity was not observed, because the request never passed authentication.

Repository contract for the assess path (not a live load):

- Model class intended by `/api/v1/assess`: `SSRIModel`
- Loader: `load_inference_checkpoint` → `load_evaluation_model`
- Required payload keys: `model_state_dict`, `model_config`
- Required config: `in_channels == 13`, `num_classes == 3`
- Class vocabulary: subsidence (0), landslide (1), sinkhole (2)
- Checkpoint on the deployed host: NOT OBSERVED
- Checkpoint version: NOT OBSERVED
- Default dropout in `SSRIModelConfig`: 0.0

`SSRIMultiTaskModel` checkpoints (`state_dict` / `config`, liquefaction head) are a different contract and are rejected by the assess loader. No deployed file was opened.

## 4. Production inference

- Authenticated inference: NOT RUN
- HTTP status: not applicable (no credential; earlier unauthenticated posts returned 401)
- Request ID: none
- Model execution verified: NO
- Prediction returned: NO

Chain reached:

USER → API (health/ready from the prior test) → AUTHENTICATION REJECTED

Chain not reached:

INPUT VALIDATION → 13-CHANNEL FEATURE CONTRACT → CHECKPOINT → MODEL → LOGITS → PROBABILITY TRANSFORM → HAZARD RESULT → FRONTEND

## 5. Probability verification

Live logits were not available.

Source inspection on this date, unchanged from the prior audit:

- Expected transform for `SSRIModel`: softmax over the class dimension (`logits_to_probabilities` in `model/src/ssri_model/evaluation/predictions.py`). The geospatial runner uses that function.
- Observed transform on the assess path: `torch.sigmoid` in `run_mc_dropout` (`model/src/ssri_model/uncertainty/__init__.py`) and in the GeoTIFF branch of `assess_endpoint` (`model/src/ssri_model/api/routes/assess.py`).
- Probability sum on the deployed API: NOT MEASURED

Repository finding, not a live measurement:

FAIL — assess-path 3-class probability conversion is inconsistent with the mutually exclusive SSRI model contract.

This was not “fixed” during this task. The deployed service was not shown to be running that source revision, so the live transform stays NOT MEASURED.

## 6. Input perturbation

- Baseline result: NOT RUN
- Perturbed result: NOT RUN
- Output changed: NOT TESTED

BLOCKED at authentication.

## 7. Determinism

- Repeated runs: 0
- Variation: NOT TESTED
- Status: BLOCKED

## 8. Uncertainty

From repository defaults, not from a loaded production checkpoint:

- Dropout default: 0.0 (`SSRIModelConfig` in `model/src/ssri_model/architecture/config.py`). `blocks.py` then uses `nn.Identity` instead of `Dropout2d`.
- MC sampling: `enable_mc_dropout` only toggles `Dropout`, `Dropout2d`, and `Dropout3d`. With dropout 0 there is nothing to toggle.
- Observed variance on the deployed model: NOT MEASURED
- Status: WARNING — stochastic MC-dropout uncertainty is unavailable in the default architecture. Zero variance must not be read as calibrated confidence.

Live dropout on the Render checkpoint was not read.

## 9. Input validation

| Check | Result |
| --- | --- |
| NaN | BLOCKED — public assess/inference require a credential and do not accept an anonymous raw tensor |
| +Inf / -Inf | BLOCKED |
| 12 channels | BLOCKED |
| 14 channels | BLOCKED |
| Wrong spatial dimensions | BLOCKED |
| Nodata (`FEATURE_NODATA = -9999`) | BLOCKED |

The public inference body asks for server paths (`checkpoint`, `features`, `manifest`, `statistics`). The public assess body asks for a checkpoint path and/or a features path and/or a point or polygon. Neither was callable without a key. Internal non-finite handling was not re-run against production.

## 10. API vs runner consistency

Source comparison only. Not measured on Render.

| Item | Assess API path | Geospatial runner |
| --- | --- | --- |
| Normalization | shared feature-stack normalization when a statistics file is used | same helper |
| Channel order | `CHANNEL_NAMES` (13), semantic order not checked beyond count | same |
| Probability conversion | sigmoid | softmax |
| Nodata | runner masks `FEATURE_NODATA`; assess GeoTIFF branch does not use that mask before sigmoid | masks pixels where any channel is nodata, label nodata `-1` |
| Model | `SSRIModel` via `load_inference_checkpoint` | same loader |
| Class vocabulary | subsidence, landslide, sinkhole | same |

Probability conversion remains inconsistent in source.

## 11. Demo/mock verification

- Demo mode on Render: NOT OBSERVED. `SSRI_DEMO_MODE` is read after API-key authentication on assess, so an anonymous call cannot reveal it.
- Repository default in `.env.example`: `SSRI_DEMO_MODE=false`
- Static output: `api/demo_assessment.py` returns hardcoded Lagos scenarios when demo mode is on. That function was not invoked against production.
- Fallback prediction: not observed live. Source still short-circuits to demo output before checkpoint load when the flag is set.

## 12. Local test suite

Earlier full suite (2026-10-01, `--tb=no`, so the assertion text was discarded):

- Passed: 652
- Failed: 1
- Skipped: 2 (both in `tests/test_infrastructure_integration.py`; `SSRI_INTEGRATION_TESTS` unset)
- Failed name: `tests/test_manual_training.py::test_training_api_upload_validate_and_start`
- Duration: 513.67s

Diagnostic runs this session, with `--tb=short`:

| Run | Result |
| --- | --- |
| Isolated, process A | 1 passed in 27.30s |
| Isolated, process B (parallel with A) | 1 passed in 27.29s |
| Module `tests/test_manual_training.py` | 7 passed in 34.39s |
| Full suite this session | not re-run |

Reproduced: NO

Status: INTERMITTENT / NOT REPRODUCED

No traceback exists for the original failure because that suite used `--tb=no`.

What the test does: `test_training_api_upload_validate_and_start` uploads a Stage 2.5 zip, starts a `JobType.TRAINING` job on `LocalJobExecutor`, then polls up to 60 times with `time.sleep(0.5)` (30 seconds) and asserts `status == completed`.

The two isolated passes finished in about 27 seconds, inside a 30 second poll budget. That margin is small. A full suite that already took 514 seconds can starve the same background train so the poll ends while the job is still running. That is a plausible order/load dependency. It was not reproduced here, including when two copies ran at once, so it is not stated as a confirmed root cause.

No assertion was weakened. No sleep was added. The test was not marked flaky.

## DEPLOYED TESTS

Blocked at authentication: live model identity, one authenticated inference, perturbation, determinism, non-finite input, channel count, nodata, demo-mode flag.

## LOCAL TESTS

Flaky-target reproduction: not reproduced (isolated twice, module once).

Repository probability mismatch: still present in source.

## FINAL STATUS

SELF-TEST BLOCKED

scientific_status = NOT_VALIDATED
