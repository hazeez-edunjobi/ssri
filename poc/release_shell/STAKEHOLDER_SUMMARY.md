# Stakeholder summary — SSRI upload-and-train shell (RC1)

SSRI can now take an owner’s own labelled Stage 2.5 tiles through **upload → validate → train (3 seeds) → evaluate → assess** on branch **`integration/ssri-shell-rc1`**, behind **`SSRI_RELEASE_SHELL` (default off)**. Nothing has been merged to `main`, deployed, or shipped as production weights.

What works today: a readable validation report (PASS/WARN/FAIL), automatic held-out evaluation with gate strings, jobs that expose progress and results, assess that returns a ranking score only when a hazard is **evaluated** and the query is inside the training geography—otherwise `not_available` / `outside_training_region` / `no_trained_model` with **null** score. Owner UI: **`/shell`**; API fallback: `OWNER_API_GUIDE.md`.

What it is not: scientific validation, calibrated probability, risk, or detection. Status stays **NOT_VALIDATED**. Research credibility cycles (v1–v3) concluded **NO-GAIN** for multivariate landslide models vs slope on leakage-free CONUS blocks; DeepSlide stays unwired. Owner data must meet the checklist in `README_OWNER.md` (13 channels, labels, enough tiles/blocks, no empty channels).
