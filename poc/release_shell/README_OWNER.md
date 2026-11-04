# Owner guide — upload-and-train shell

For a **non-developer** operator. This lives on **`integration/ssri-shell-rc1`**. Nothing is merged to `main` or deployed by this work.

## What you prepare (data checklist)

Before upload, your ZIP must contain:

- [ ] Georeferenced tiles (label GeoTIFF with CRS + transform)
- [ ] **13 channels** in the documented order (see `DATASET_SPEC.md`)
- [ ] Labels per hazard: subsidence=0, landslide=1, sinkhole=2 (−1 = ignore)
- [ ] **No empty channels** (do not ship a channel that is −9999 on every pixel)
- [ ] Prefer **≥300 tiles**, **≥8 separate 5° regions**, **≥3 held-out blocks** (production defaults)
- [ ] Demo / dry-run only: `templates/SYNTHETIC_stage25_template.zip` — labelled **SYNTHETIC** everywhere

## What you can do

1. Upload a labelled Stage 2.5 ZIP  
2. Read a validation report (PASS / WARN / FAIL with readable reasons)  
3. Start multi-seed training (default 3 seeds)  
4. Read an automatic evaluation report (held-out blocks, AUC/CI when computable, delta vs slope, gate status, per-block table)  
5. Select a checkpoint and run assess  

Before any training, assess returns **`no_trained_model`**.

## Setup (once)

```powershell
cd model
poetry install
$env:SSRI_RELEASE_SHELL='true'
$env:SSRI_ASSESS_SOFTMAX='true'
# Optional lower thresholds for the SYNTHETIC dry-run only:
# $env:SSRI_RELEASE_SHELL_MIN_TILES='4'
# $env:SSRI_RELEASE_SHELL_MIN_BLOCKS='4'
# $env:SSRI_RELEASE_SHELL_MIN_HELD_OUT='2'
poetry run uvicorn ssri_model.api.app:app --reload --port 8000
```

In another terminal, UI:

```powershell
cd frontend
npm install
npm run dev
```

Open **`http://localhost:3000/shell`** (release-shell owner page) or follow **`OWNER_API_GUIDE.md`**.

Classic Stage 2.5 operator UI remains at `/training/operator` (does not call release-shell routes).

## Step by step (UI)

1. Open `/shell`  
2. Upload your Stage 2.5 ZIP  
3. Read PASS/WARN/FAIL — if `can_train` is no, **stop and fix data**  
4. Start training (3 seeds) and watch progress  
5. Read evaluation / gate strings (`evaluated` vs `trained, no demonstrated skill beyond slope` vs `trained, unconfirmed across seeds`)  
6. Select/promote a checkpoint  
7. Assess on the dashboard with that checkpoint path + a point inside/outside training geography  

## Step by step (API)

See **`OWNER_API_GUIDE.md`**.

## Must never be used for

Insurance, engineering design, safety-critical work, or emergency decisions. Scores are relative rankings only. Status stays **NOT_VALIDATED**.

See `LIMITATIONS.md`, `DEMO_SCRIPT.md`, `MERGE_CHECKLIST.md`, and `STAKEHOLDER_SUMMARY.md`.
