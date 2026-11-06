# Remaining work register

Every open item, who owns it, what blocks it, and the cheapest next step.
Labels: **VERIFIED** (command/path), **REPORTED**, **UNKNOWN**.
Nothing here is pushed; this is a local-only branch.

| # | Item | Owner | Blocker | Cheapest next step |
|---|------|-------|---------|--------------------|
| 1 | Meaning + units of the client `Z` value (thickness vs depth vs elevation) | **Client** | Data has no metadata | Send `handoff/CLIENT_QUESTIONS.md`; do not train until answered |
| 2 | True CRS of the Abeokuta grid (EPSG or full definition); why X is negative | **Client** | File carries no CRS; `EPSG:32631` is ASSUMED-FOR-TEST only | Same message as #1; ask for EPSG or WKT/PROJ |
| 3 | Are the 7,129 missing grid cells intentional (mask/AOI) or data loss? | **Client** | UNKNOWN | Ask; treat as nodata meanwhile |
| 4 | Hazard location data with dates for landslide / subsidence / sinkhole | **Client** | No events provided for the area | Ask for outlines + dates + confidence |
| 5 | Lineament vector data (faults/fractures) as GeoJSON/GPKG | **Client** | None provided | Ask; lineament channels stay synthetic-only until then |
| 6 | Decision: which block size + buffer to use for the 56 km Abeokuta site | **Human owner** | Default 50 km buffer cannot work on a 56 km site (VERIFIED: only 0/5 km buffers feasible at 5–10 km blocks) | Pick from the estimate table in `../RUNBOOK_FIRST_REAL_RUN.md`; get reviewer view (#8) |
| 7 | First real (non-synthetic) training + evaluation | **Agent + Human** | Blocked by #1–#5 | After client answers, follow `../RUNBOOK_FIRST_REAL_RUN.md` |
| 8 | Independent geoscience review of assumptions, gates, limitations | **Human (external reviewer)** | Needs a named reviewer | Send `REVIEW_REQUEST.md`; one page to `REVIEW_CHECKLIST.md` / `MODEL_CARD.md` / `LIMITATIONS.md` |
| 9 | Confirm `pyproj` + DeepSlide optional group install from scratch | **Agent** | Sandbox blocks a full `poetry install` into a fresh venv (Poetry writes outside the permitted dir); no host with relaxed limits | On a normal host: `python -m venv .venv && poetry install --with deepslide`. Evidence so far: dry-run resolve EXIT=0 and a fresh pip venv importing h5py/smp/torch OK (REPORTED). |
| 10 | Frontend lint is red under ESLint 9 (legacy `.eslintrc.json`) | **Agent** | Pre-existing config mismatch, not introduced here | Migrate to flat `eslint.config.js` in a separate change; does not affect runtime |
| 11 | `/shell` surfaces that remain API-only (see FINISH_REPORT.md UI table) | **Agent** | 4-hour UI time box | Wire the remaining API-only inputs into `/shell` using `OWNER_API_GUIDE.md` as the interim fallback |
| 12 | `SSRI_UPLOAD_MAX_BYTES` recommended value from measured peak RSS | **Agent** | Measurement in progress | Finish synthetic profile (13ch/16ch), then set the value + memory guidance in the upload doc |
| 13 | `preview_unevaluated_scores` stays default OFF | **Agent** | Product decision | Leave OFF; document the toggle; flip only with owner sign-off |
| 14 | Real-data rehearsal ZIP committed? | **Agent** | Real client CSV is not committed (correct) | Keep the CSV out of git; use the ASSUMED-CRS copy under `outputs/` for tests only |

## Notes

- Items 1–5 are **human/client-dependent**; no code can close them without
  guessing, and guessing is explicitly disallowed.
- Item 6 is a real product decision surfaced by the block-count estimate.
- The first real model may honestly report
  `trained, no demonstrated skill beyond slope`. That is a correct result on
  thin data, not a defect (see `OWNER_STATUS.md`).
