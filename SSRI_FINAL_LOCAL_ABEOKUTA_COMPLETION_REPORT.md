# SSRI — Final Local Abeokuta Completion Report

**Date:** 2026-11-24  
**Scope:** Local Abeokuta assessment verification after commit `4455877` (catalogue overlays).  
**Git operations:** None after the approved commit. No push. No deploy. No retrain.

---

## Final decision

**READY WITH DOCUMENTED SCIENTIFIC LIMITATIONS**

Local platform software completes the Abeokuta assessment workflow with honest geological conditioning overlays. Scientific validation remains **NOT_VALIDATED**. Lineament and overburden are correctly reported as unavailable for this AOI and are **not** used in the 13-channel prediction.

---

## 1. Git state

| Item | Value |
|---|---|
| Branch | `main` |
| HEAD | `44558779ffe93a0f2a3d151e8f0a9d309f7e8753` |
| Message | Add honest catalogue overlays for lineament and overburden assess context. |
| Working tree at Phase 1 | Clean (`git status --porcelain` empty) |
| Tracking | `main...origin/main [ahead 1]` |

No unexpected modifications were present before this verification run. This report and fresh assess evidence under `poc/` may appear as local untracked artifacts afterward; they were **not** committed.

---

## 2. Local service readiness

`GET /api/v1/ready` (no secrets):

| Component | Status |
|---|---|
| Overall | `ready` |
| configuration | ok |
| postgresql | ok (connected) |
| redis | ok (connected) |
| queue | ok (reachable) |
| demo_mode | false |
| active_model_id | `ssri-model-e7af3afcd0` |
| scientific_validation_status (registry) | NOT_VALIDATED |

Also verified:

| Service | Evidence |
|---|---|
| FastAPI health | `GET /api/v1/health` → ok |
| Frontend | `http://localhost:3000` → HTTP 200 |
| Postgres container | `ssri-postgres` healthy on `:5432` |
| Redis | Listening `:6379` (host Redis + Compose redis healthy) |
| Celery/queue | Ready payload `queue: ok` |

Existing project configuration was used. No infrastructure replacement.

---

## 3. Dataset identity and CRS interpretation

| Field | Stored value |
|---|---|
| Path | `data/outputs/geological/datasets/geo_be00a34ad6f4/original/sheet_260_Abeokuta.csv` |
| Size | 10 143 316 bytes |
| geo_id | `geo_be00a34ad6f4` |
| display_name | Abeokuta TMI sheet 260 |
| measurement_type | `total_magnetic_intensity` |
| units | nT |
| z_meaning | `total_magnetic_intensity` |
| validation_status | validated |
| activation_status | inactive |
| scientific_validation_status | NOT_VALIDATED |

### Authoritative coordinate interpretation (stored metadata)

| Role | Meaning |
|---|---|
| X | Easting (source CRS) |
| Y | Northing (source CRS) |
| Z | Total Magnetic Intensity (TMI) — **not** elevation, depth, or overburden thickness |
| Source CRS | EPSG:32632 |
| Processing CRS | EPSG:32631 |
| Display CRS | EPSG:4326 |
| display_bbox_wgs84 | ≈ `[2.994, 6.995, 3.505, 7.506]` |

UI confirmation on dataset page: *“X=easting , Y=northing , Z=TMI . Source EPSG:32632 → processing EPSG:32631 → display EPSG:4326.”*

Assessment AOI was submitted as WGS84 point **lat 7.25, lon 3.25** (inside the display footprint). This does not reinterpret the original CSV columns as lon/lat.

---

## 4. Fresh assessment identity

### API assessment (authoritative for this report)

| Field | Value |
|---|---|
| HTTP | 200 |
| assessment_id | `assess-7dfc19ea9b27c4b7` |
| request_id | `abeokuta-final-local-completion` |
| AOI | 7.25, 3.25 |
| Evidence file | `poc/abeokuta_final_local_completion_assess.json` |

### Browser confirmation assessment

| Field | Value |
|---|---|
| assessment_id | `assess-2d53ef2273fe259f` |
| request_id | `assess-30f7edb3ff15` |
| Same AOI / scores / honesty | Confirmed in result modal |

---

## 5. Checkpoint identity and hash

| Item | Value |
|---|---|
| Active model | `ssri-model-e7af3afcd0` |
| Registry name | LOCAL-PIPELINE-SYNTHETIC-13CH |
| Path | `data/outputs/training/models/ssri-model-e7af3afcd0/best.pt` |
| SHA256 (file + assess notes) | `d912027e17ed532687f9d2a2c74fd3c18ca8c812ae49107d939ade19dde5d004` |
| checkpoint_source | `active_registry` |
| is_fixture_checkpoint | false |
| Training provenance shown | SYNTHETIC-300k-rehearsal@synthetic-300k-1 (not real-world geology) |

Checkpoint was not replaced or retrained during this run.

---

## 6. Assessment scores

| Hazard | Score | Confidence tier |
|---|---:|---|
| Subsidence | **58.2%** (0.5817) | Low |
| Landslide | **52.7%** (0.5270) | Low |
| Sinkhole | **49.2%** (0.4920) | Low |

Historical comparison (prior local runs ≈ 58.0 / 52.8 / 49.3%). Differences are within expected acquisition/MC noise. **No scientific improvement claimed.**

Notes state: relative susceptibility rankings; status remains **NOT_VALIDATED**.

---

## 7. Geological conditioning results

| Item | Result |
|---|---|
| schema_channel_count | **13** |
| catalogue_overlay.used_in_inference | **false** |
| geological_context | 1 item — `geo_be00a34ad6f4` |
| z_meaning | total_magnetic_intensity |
| structural_orientation_theme | Predominantly NE-SW structural trends |
| Qualification | NOT_VALIDATED; not confirmed faults/fractures; not hazard labels; not overburden thickness |

Publication-guided themes attached (sedimentary / transitional / basement / NE–SW).

---

## 8. Lineament availability

| Layer | status | value | used_in_inference |
|---|---|---|---|
| lineament_density | unavailable | null | false |
| lineament_distance | unavailable | null | false |

Reason (API): no activated lineament vector dataset covers the AOI; NE–SW themes are geological context only and were **not** converted into fabricated geometries.

**Did lineaments influence the prediction?** No.

---

## 9. Overburden availability

| Layer | status | value | used_in_inference |
|---|---|---|---|
| overburden_thickness | unavailable | null | false |

Reason (API): AOI intersects a TMI footprint; **TMI Z is not overburden thickness and was not substituted**; no activated thickness dataset covers the AOI.

**Did overburden influence the prediction?** No.

---

## 10. Frontend verification (targeted)

| Check | Result |
|---|---|
| Abeokuta dataset accessible | PASS — `/geological/geo_be00a34ad6f4` |
| TMI declared (not overburden) | PASS |
| Stored CRS roles shown | PASS — 32632 → 32631 → 4326 |
| Dashboard API ready + footprints | PASS — 3 WGS84 footprints |
| Active model `ssri-model-e7af3afcd0` | PASS |
| Channel schema v1 (13 channels) | PASS |
| Assess at 7.25, 3.25 completes | PASS |
| Result modal opens | PASS |
| Geological context visible | PASS — NE–SW + themes; not faults |
| Overburden unavailable + TMI disclaimer | PASS |
| Lineament unavailable + no fabricated vectors | PASS |
| Dashboard still operational | PASS |

Full November 23 headed acceptance gate was not repeated.

---

## 11. Test commands and results

```text
poetry -C model run pytest tests/test_geological_conditioning_overlay.py tests/test_assess_conditioning.py -q --tb=line
→ 6 passed in 9.77s

node --test frontend/lib/conditioning.test.ts
→ 6 passed (0 fail)
```

Regression checks:

- Active checkpoint ID and SHA256 unchanged.
- Live assess remains 13-channel (API + UI).
- No schema-v2 channel injection into the live tensor.

---

## 12. Scientific limitations

1. **NOT_VALIDATED** — no independent geological validation of scores or magnetic themes.
2. Active checkpoint is a **synthetic/local bootstrap** Stage 2.5 model, not real-world trained geology.
3. Lineament density/distance for Abeokuta: **unavailable** (no activated covering vectors).
4. Overburden thickness for Abeokuta: **unavailable** (no scientifically defensible thickness dataset; TMI not substituted).
5. Catalogue overlays do **not** enter live 13-channel inference.
6. Credible intervals in this payload are **degenerate** (identical lower/upper bounds equal to the point estimate). They must **not** be read as meaningful calibrated uncertainty.
7. Domain similarity is uncalibrated (`domain_similarity_calibrated=false`).

---

## 13. Remaining blockers

| Blocker | Type |
|---|---|
| Abeokuta overburden thickness (metres) dataset | External scientific data |
| Abeokuta lineament vector dataset (validated/activated) | External scientific data |
| Schema-v2 offline stack + compatible checkpoint if overlays must influence scores | Architecture / approved retrain decision |
| Independent scientific validation evidence | Scientific process |

No blocking **software** defects were observed in this completion run.

---

## 14. Conclusion

**READY WITH DOCUMENTED SCIENTIFIC LIMITATIONS**

Local SSRI completes Abeokuta assessment end-to-end on the approved overlay commit, preserves the 13-channel Stage 2.5 path, and honestly reports missing lineament/overburden measurements plus TMI geological context.

Stopped. No additional commit. No push. No deploy. Awaiting further approval.
