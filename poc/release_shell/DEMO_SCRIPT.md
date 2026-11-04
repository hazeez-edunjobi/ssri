# 5-minute demo script

Prereqs: API running with `SSRI_RELEASE_SHELL=true` (see README_OWNER.md). Use SYNTHETIC mins for the tiny template.

## 1) Assess with no checkpoint → `no_trained_model`

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/assess -H "Content-Type: application/json" -d "{}"
```

Expect: `"status":"no_trained_model"`.

## 2) Validation FAIL (broken ZIP)

Create a zip that is not a Stage 2.5 dataset (e.g. a single `readme.txt`), create a dataset, upload, validate — expect FAIL / training refuse. Or use a dataset whose spectral channels are all `-9999` (validator check `channel_quality`).

## 3) SYNTHETIC template → validate → train → evaluate

```bash
# build template once
poetry -C model run python poc/release_shell/scripts/build_synthetic_template.py

# create dataset (training API)
curl -s -X POST http://127.0.0.1:8000/api/v1/training/datasets -H "Content-Type: application/json" -d "{\"name\":\"SYNTHETIC demo\",\"notes\":\"SYNTHETIC\"}"

# upload + validate + train via release-shell routes (use returned dataset_id)
```

Poll job until completed; fetch evaluation JSON. Confirm baselines (majority, slope) and gate strings — never “validated”.

## 4) Assess with checkpoint

POST `/api/v1/assess` with `features` (.npy) + `checkpoint`. Hazards without training remain `not_available` when using the shell contract fields in notes/limitations.

## Timing

Aim for ≤5 minutes of talking time; training epochs for SYNTHETIC should be 2–3 on CPU.
