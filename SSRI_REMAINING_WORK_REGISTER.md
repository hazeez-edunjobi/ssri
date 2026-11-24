# SSRI — Remaining Work Register

**Date:** 2026-11-24  
**Baseline HEAD:** `44558779ffe93a0f2a3d151e8f0a9d309f7e8753` (+ local uncommitted completion work)  
**Companion:** `SSRI_FINAL_PRODUCT_COMPLETION_REPORT.md`

| ID | Priority | Description | Current state | Required action | Required dataset / approval | Blocks local release? | Blocks scientific validation? | Blocks production? |
|---|---|---|---|---|---|---|---|---|
| R-01 | P0 | Real subsidence ground truth | Missing on disk (USGS stacks landslide-only; UGLC Africa empty; Lagos InSAR docs-only) | Ingest authoritative inventory into schema / Stage 2.5 `label.tif` | Agency or peer-reviewed positives + controls | No | **Yes** | Yes (for scientific claims) |
| R-02 | P0 | Independent scientific validation of Stage 2.5 model | NOT_VALIDATED / synthetic bootstrap | Spatially honest eval + review | R-01 + approval to report metrics | No | **Yes** | Yes |
| R-03 | P1 | Validate candidate magnetic lineaments | 72 candidates extracted, NOT_VALIDATED | Geological QC vs mapped structures | Fault/fracture GIS | No | Yes (structural claims) | Soft |
| R-04 | P1 | Abeokuta overburden thickness (m) | Unavailable | Acquire thickness inventory with units/CRS | Borehole / thickness survey | No | Partial | Soft |
| R-05 | P1 | Confirmed faults/fractures layer | Not implemented | Catalogue asset + provenance | Authoritative structural GIS | No | Yes (if claimed) | Soft |
| R-06 | P2 | Lithology / geological boundaries / soil / groundwater | Not implemented | Design + ingest | Suitable GIS + licences | No | Partial | Soft |
| R-07 | P2 | Inject lineament/overburden into live inference | Explicitly false | New approved model + loader | Scientific + product approval | No | N/A | If required by product |
| R-08 | Done | Assessment history UI | `/assessments` + `/assessments/[id]` on `GET /api/v1/assess/history` | Commit when approved | Approval | No | No | No |
| R-09 | Done | Staging production-gate subset (F-05) | Staging blocks demo / dev-auth / wildcard CORS | Keep staging ≠ silent prod; full auth still prod-only | Ops awareness | No | No | Soft (prod still needs full gate) |
| R-10 | Done (ops note) | Lease recovery default (F-08) | Staging defaults on when unset; prod/dev off unless explicit | **Production enable still needs ops approval** | Ops decision for prod | No | No | Soft until prod opt-in |
| R-11 | Done (product path) | Checkpoint load residual paths | `safe_torch` on product/runtime paths | Leave PoC `torch.load` out of assess path | None | No | No | Soft (PoC scripts only) |
| R-12 | Done | CORS DELETE | DELETE allowed | Keep FE delete aligned | None | No | No | No |
| R-13 | P3 | Marketing README `/v1/hazard` note | Docs only | Optional cleanup | None | No | No | No |
| R-14 | Done | F-01/F-03/F-04 FE remediation | Implemented locally | Commit when approved | Approval | No | No | No |
| R-15 | Done | Candidate lineament extraction | Implemented + Abeokuta artefacts | Geological review (R-03) | — | No | — | — |
| R-16 | Soft | Pre-existing FE lint (`RequireSession` / `PlatformShell` setState-in-effect) | Present; assessments pages lint clean | Optional refactor | None | No | No | Soft |

**Legend:** Local release can proceed with documented scientific limitations. Production readiness still requires security/ops items and must not claim scientific validation.
