# African / Nigerian Target Dataset Investigation

**Date:** 2026-09-09  
**Purpose:** Unblock master-spec Phase 3 (direct transfer) and preserve DANN role design.  
**Rule:** Do not treat susceptibility maps as observation ground truth.

## DANN role design (locked)

| Role | Meaning | Label use |
|------|---------|-----------|
| **SOURCE** | USGS (and later BGS/IFFI) labelled FeatureStacks | Supervised training |
| **TARGET_UNLABELED** | African/Nigerian FeatureStacks for domain adaptation | **No labels** for training/tuning |
| **TARGET_HELD_OUT** | Independent labelled African/Nigerian samples | **Final evaluation only** (DIRECT TRANSFER vs DANN) |

Held-out target labels must **not** tune DANN hyperparameters.

Scaffold: `data/catalogs/uglc_africa/dann_role_design.json` (written when UGLC ingest succeeds).

---

## Candidate inventory

### 1. UGLC — Unified Global Landslide Catalogue (priority)

| Field | Finding |
|-------|---------|
| Access | Zenodo DOI `10.5281/zenodo.18643456` / `16755044`; GitHub UnibaGEO/UGLC_point |
| License | Open Zenodo deposit (confirm file-level terms before redistribution) |
| Coordinates | Yes (global point CSV / tiled GPKG) |
| Labels | Landslide inventory presence (harmonized) |
| Nigeria | Filterable by country / bbox |
| Held-out eval | **Yes** — presence points can support labelled target evaluation with documented pseudo-absences |
| Unlabelled target | **Yes** — FeatureStacks at African AOIs without using labels |
| Status **this environment** | **BLOCKED download** — Zenodo API `HTTP 504` / timeouts (2026-09-09). Ingest script ready: `python -m ssri_model.scripts.ingest_uglc_africa` |

**Action:** Manual download of UGLC point CSV → `--local-csv path` into ingest script.

### 2. NEMA Disaster Surveillance Map (Nigeria)

| Field | Finding |
|-------|---------|
| Access | Web/GIS portals; **no verified anonymous bulk event CSV** in this investigation |
| License | Government of Nigeria — terms unclear without portal registration |
| Coordinates / labels | Event-dependent; not confirmed machine-readable landslide inventory for SSRI |
| Usable now? | **Not yet** — needs human portal export + license review |
| Role if obtained | Possible TARGET_HELD_OUT / auxiliary if events have coords + hazard type |

### 3. Lagos InSAR (Ohenhen & Shirzaei) — Figshare `10.7294/19738957`

| Field | Finding |
|-------|---------|
| Access | Figshare (already assessed in `docs/dataset_candidates_report.md`) |
| License | Dataset v1 often CC0 — confirm version |
| Coordinates | Lagos AOI rasters / VLM |
| Labels | Continuous VLM / risk — **not** SSRI multi-task `label.tif` |
| Usable as? | **BENCHMARK-ONLY** / auxiliary subsidence reference — **not** landslide held-out GT |
| Susceptibility-as-truth? | **No** |

### 4. NGSA / NGMC geological maps

| Field | Finding |
|-------|---------|
| Access | Public map products (varies) |
| Labels | Geology / lithology — **not hazard events** |
| Usable as? | Feature/context layers only — **not** evaluation inventories |

### 5. NASA COOLR / GLC

| Field | Finding |
|-------|---------|
| Access | FeatureServer previously **HTTP 404**; data.nasa.gov export / COOLR viewer |
| Africa density | Sparse / reporting-biased (esp. Lagos coastal plain) |
| Usable as? | Partial global prior; weak for Nigeria-dense held-out set |
| Status | Still blocked for automated ingest here |

### 6. ThinkHazard! Nigeria landslide level

| Field | Finding |
|-------|---------|
| Usable as GT? | **No** — admin susceptibility class; underlying LS dataset not downloadable |

---

## What can actually be used for Phase 3

| Dataset | Labelled target eval | Unlabelled adaptation | Notes |
|---------|---------------------|-----------------------|-------|
| **UGLC Nigeria/Africa** (once downloaded) | **Primary candidate** | Yes | Best path; manual Zenodo fetch needed |
| Lagos InSAR | No (wrong label type) | Possible AOI features only | BENCHMARK-ONLY for subsidence science |
| NEMA | Unknown until export | Unknown | Human acquisition |
| NGSA maps | No | No (not events) | Context only |
| COOLR | Weak / sparse | Possible | Secondary |

## Phase 3 status

```text
PHASE 3 — DIRECT TRANSFER: BLOCKED ON USABLE LABELLED AFRICAN TARGET ON DISK
```

Next concrete step once UGLC CSV is local:

1. `poetry run python -m ssri_model.scripts.ingest_uglc_africa --local-csv <file>`
2. Partition Nigeria points into TARGET_HELD_OUT vs TARGET_UNLABELED (spatial blocks)
3. Build FeatureStacks for both partitions
4. Run DIRECT TRANSFER with `models/ssri-foundation-v*.pt` on held-out only
