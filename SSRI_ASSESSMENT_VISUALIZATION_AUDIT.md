# SSRI — Assessment visualization audit

**Baseline before work:** `2bc160d` (`main` = `origin/main`)  
**Fix commit:** `6a847cbfef8527e438e576e932ddb5b65b1ca7e4` (`6a847cb`)
**Verdict:** **COMPLETE WITH WARNINGS**

---

## 1. Gravity layer — root cause and resolution

| Question | Finding |
|----------|---------|
| Config | `GRAVITY_DATA_PATH` (default `/data/geophysics/processed/lagos_gravity_wgm2012_bouguer.tif`; `.env.example` uses repo-relative `data/geophysics/processed/...`) |
| Loader | `GET /api/v1/layers/gravity` in `model/src/ssri_model/api/routes/layers.py` → GeoJSON for MapLibre |
| Frontend | `getGravityLayer()` + dashboard map source `ssri-gravity` |
| Local GeoTIFF | **Present** under `data/geophysics/processed/lagos_gravity_wgm2012_bouguer.tif` |
| Production (Render) | **Missing** — `GET https://ssri-api.onrender.com/api/v1/layers/gravity` → **404** |
| Fabrication | **None** — no substitute raster |

**Root cause:** Optional visualization GeoTIFF is not mounted on the production API host. Assessment does **not** depend on this overlay.

**Resolution in this pass (honest UX + clearer API, no fake data):**

- API 404 detail now states the overlay is **optional**, how to mount `GRAVITY_DATA_PATH`, and that assessments can still run.
- Frontend distinguishes `loading` / `ready` / `unavailable`.
- Visibility control no longer reads as “Visible” when the layer failed to load (`Not on map` / `Shown on map` / `Hidden on map`).
- Client copy explains the overlay is optional and assessment can continue.

**Ops follow-up (not done here):** mount the WGM2012 Bouguer GeoTIFF on Render (or set `GRAVITY_DATA_PATH` to a persistent volume path) if the overlay is desired in demos.

---

## 2. Gravity classification

**Optional visualization / diagnostic map overlay.**

- Not required to submit an assessment.
- Separate from Stage 2.5 channel acquisition used inside inference (when live/offline stacks include a gravity channel).
- Missing overlay must not block hazard assessment.

---

## 3. Lineament integration and presentation

| Aspect | Status |
|--------|--------|
| Supported in product | Schema **v2** (`lineament_density`, `lineament_distance`) via `/shell` apply |
| Live AOI (v1) | Not acquired; results show **unavailable** |
| Result UI | Dedicated **Lineaments** panel with status, values/units, provenance/reason |
| Used vs available | Explicit: in product / at sample cell / used in this assessment |
| Zero fill | Forbidden |
| Schema-v2 offline | Unchanged; advanced offline `.npy` path retained under Advanced operator options |

---

## 4. Overburden integration and presentation

| Aspect | Status |
|--------|--------|
| Supported in product | Schema **v2** `overburden_thickness` |
| Live AOI (v1) | Not acquired; **unavailable** |
| Result UI | Dedicated **Overburden thickness** panel |
| Units | Thickness (m); depth-to-interface not auto-converted |
| Used vs available | Same three-way distinction as lineaments |
| Zero fill | Forbidden |

---

## 5. Developer-facing control changes

Checkpoint path and offline `.npy` path are removed from the default client surface.

- Collapsed **Advanced operator options** (`data-testid="advanced-operator-options"`).
- Still available for operators/tests; links to `/training/operator` and `/shell`.
- Promoted/active checkpoint continues to prefill **internally** for assess requests without showing filesystem paths by default.
- Validation copy no longer steers ordinary clients toward offline filesystem paths.

---

## 6. Map visualization improvements

- Gravity panel title: “Gravity overlay”.
- Status always shown (`loading` / optional unavailable / ready).
- Toggle disabled until ready; label never claims the layer is shown when unavailable.
- On load failure: clear meta, force not visible, keep assessment usable.
- Hazard / coordinate / GeoTIFF controls retained.

---

## 7. Test results

| Test | Result |
|------|--------|
| Frontend unit (`npm test`) | **PASS** (29) |
| Frontend typecheck | **PASS** |
| Frontend lint | **PASS** |
| Frontend production build | **PASS** |
| Gravity load helper tests | **PASS** |
| Missing gravity message tests | **PASS** |
| Lineament/overburden availability + unused-state tests | **PASS** |
| Backend `tests/test_layers_gravity.py` (present + missing) | **PASS** |
| E2E: advanced controls collapsed; validation copy updated | Updated in `e2e/dashboard.spec.ts` (requires signed-in env to execute fully) |
| GeoTIFF download regression (unit/report) | **PASS** (existing report tests) |

Synthetic fixtures: unit tests use synthetic conditioning/gravity messages. Real local GeoTIFF exists for local API; production host still lacks the mount.

---

## 8. Remaining limitations / warnings

1. **Production gravity overlay still unavailable** until ops mounts the GeoTIFF — UI now reports this honestly.
2. Live AOI remains **v1 / 13 channels**; lineament/overburden will usually show unavailable unless a schema-v2 offline stack is assessed.
3. Redis/readiness and authenticated production smoke are **out of scope** for this task.
4. Advanced path fields are collapsed, not role-gated (dashboard session has email only; full admin role gating lives elsewhere).

---

## 9. Exact commit SHA

```text
6a847cbfef8527e438e576e932ddb5b65b1ca7e4
```

### Final verdict

**COMPLETE WITH WARNINGS** — client assessment UI is trustworthy about missing gravity and conditioning usage; production still needs an optional GeoTIFF mount for the gravity overlay to appear on the map.
