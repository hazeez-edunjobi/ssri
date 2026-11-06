# Owner status — where SSRI stands (plain language)

## What works today

- The full pipeline runs end to end: **create dataset → upload ZIP → validate →
  train (3 seeds) → evaluate with gates → select checkpoint → assess**.
- The **`/shell`** web page and the API both drive it. `OWNER_API_GUIDE.md` is the
  API fallback; `RUNBOOK_FIRST_REAL_RUN.md` is the step-by-step for the first real
  upload.
- The system **refuses to invent a score**. Outside the trained area you get
  `outside_training_region`; before any train you get `no_trained_model`; a model
  that does not beat the slope baseline is reported as
  `trained, no demonstrated skill beyond slope`.
- Local (km-scale) block sizes are supported for a single small site, and the
  output is labelled **"local evidence only; not validated beyond this site"**.

## What is only tested on SYNTHETIC data

- Every training/evaluation number we hold today comes from **SYNTHETIC** demo
  tiles, not real geology. They prove the machinery works; they say nothing
  about real ground risk.
- The **Abeokuta CSV is real client data, but its CRS is ASSUMED FOR TEST**
  (`EPSG:32631`) and its units/meaning are **UNKNOWN**. It has been used only to
  test that the validator flags things like negative thickness — not to train a
  real model.

## What needs the client

- The meaning and units of Z, the true CRS, whether the 7,129 gaps are
  intentional, and hazard location data with dates (see
  `handoff/CLIENT_QUESTIONS.md`).
- Without these we cannot produce a meaningful first real model.

## What needs a reviewer

- An **independent geoscientist** should check the assumptions, the gates, and
  the limitations before anyone treats an output as usable. See
  `handoff/REVIEW_REQUEST.md`.

## Honest expectation for the first real run

Do **not** expect a good model on day one. A single ~56 km site, limited labels,
and a large default buffer mean the first result is quite likely to be
**"trained, no demonstrated skill beyond slope"**. That is the correct, honest
outcome if the data is thin — it is not a bug. The pipeline is built to say so
rather than to pretend otherwise.
