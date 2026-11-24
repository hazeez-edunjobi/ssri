"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { PlatformShell } from "@/components/platform/PlatformShell";
import { TmiSurveyPreview } from "@/components/geological/TmiSurveyPreview";
import { COMMON_CRS_OPTIONS } from "@/lib/crsOptions";
import {
  declareGeologicalMetadata,
  downloadGeologicalOriginal,
  extractGeologicalLineaments,
  geologicalDerivedUrl,
  getAbeokutaTmiPreset,
  getGeologicalDataset,
  listGeologicalMagnetic,
  previewGeologicalTmi,
  processGeologicalTmi,
  runGeologicalMagnetic,
  setGeologicalActivation,
  setGeologicalCompatibility,
  validateGeologicalDataset,
  type GeologicalDataset,
  type InspectReport,
  type MagneticProducts,
  type TmiPreview,
  type ValidationReport,
} from "@/lib/geologicalApi";
import {
  clientValidationOutcome,
  validationOutcomeTone,
} from "@/lib/validationOutcome";

export default function GeologicalDetailPage() {
  const params = useParams();
  const geoId = String(params.id || "");
  const [dataset, setDataset] = useState<GeologicalDataset | null>(null);
  const [inspect, setInspect] = useState<InspectReport | null>(null);
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [measurementType, setMeasurementType] = useState("");
  const [crs, setCrs] = useState("");
  const [units, setUnits] = useState("");
  const [description, setDescription] = useState("");
  const [sourceClient, setSourceClient] = useState("");
  const [xCol, setXCol] = useState("X");
  const [yCol, setYCol] = useState("Y");
  const [zCol, setZCol] = useState("Z");
  const [ack, setAck] = useState<string[]>([]);
  const [surveyDate, setSurveyDate] = useState("");
  const [surveyMethod, setSurveyMethod] = useState("");
  const [samplingSpacing, setSamplingSpacing] = useState("");
  const [processingHistory, setProcessingHistory] = useState("");
  const [geoCoverage, setGeoCoverage] = useState("");
  const [gridResolution, setGridResolution] = useState("100");
  const [compatibility, setCompatibility] = useState<Record<string, unknown> | null>(
    null,
  );
  const [processing, setProcessing] = useState<Record<string, unknown> | null>(null);
  const [tmiPreview, setTmiPreview] = useState<TmiPreview | null>(null);
  const [magnetic, setMagnetic] = useState<MagneticProducts | null>(null);
  const [magneticOp, setMagneticOp] = useState("rte");
  const [inclination, setInclination] = useState("11.04");
  const [declination, setDeclination] = useState("3.52");
  const [gaussWave, setGaussWave] = useState("2000");
  const [gaussStd, setGaussStd] = useState("0.5");
  const [gaussMode, setGaussMode] = useState("low_pass");
  const [rteClip, setRteClip] = useState("10");

  const isTmi = measurementType === "total_magnetic_intensity" || measurementType === "tmi";
  const looksAbeokuta = Boolean(
    (dataset?.original_filename || dataset?.display_name || "")
      .toLowerCase()
      .match(/abeokuta|sheet\s*260/),
  );

  const applyDetail = useCallback(
    (body: Awaited<ReturnType<typeof getGeologicalDataset>>) => {
      setDataset(body.dataset);
      setInspect(body.inspect || null);
      setValidation(body.validation || null);
      setCompatibility(
        body.feature_compatibility ||
          body.dataset.feature_compatibility ||
          body.validation?.feature_compatibility ||
          null,
      );
      setProcessing(body.processing || body.dataset.processing_report || null);
      setMeasurementType(body.dataset.measurement_type || "");
      setCrs(body.dataset.crs || "");
      setUnits(body.dataset.units || "");
      setDescription(body.dataset.description || "");
      setSourceClient(body.dataset.source_client || "");
      const prov = body.dataset.provenance || {};
      setSurveyDate(String(prov.survey_date || ""));
      setSurveyMethod(String(prov.survey_method || ""));
      setSamplingSpacing(String(prov.sampling_spacing || ""));
      setProcessingHistory(String(prov.processing_history || ""));
      setGeoCoverage(String(prov.geographic_coverage || ""));
      const cols = body.inspect?.detected_columns;
      const headers = body.inspect?.header_row;
      if (headers && cols) {
        setXCol(headers[cols.x ?? 0] || "X");
        setYCol(headers[cols.y ?? 1] || "Y");
        setZCol(headers[cols.z ?? 2] || "Z");
      }
    },
    [],
  );

  const reload = useCallback(() => {
    if (!geoId) return;
    getGeologicalDataset(geoId)
      .then(applyDetail)
      .catch((err: Error) => setError(err.message));
  }, [geoId, applyDetail]);

  useEffect(() => {
    if (!geoId) return;
    let cancelled = false;
    getGeologicalDataset(geoId)
      .then(async (body) => {
        if (cancelled) return;
        applyDetail(body);
        const mt = body.dataset.measurement_type;
        if (mt === "total_magnetic_intensity" || mt === "tmi") {
          try {
            const mag = await listGeologicalMagnetic(geoId);
            if (!cancelled) setMagnetic(mag);
            const previewBody = await previewGeologicalTmi(geoId);
            if (!cancelled) setTmiPreview(previewBody.preview);
          } catch {
            /* optional until validated/processed */
          }
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [geoId, applyDetail]);

  const warnNames = useMemo(
    () =>
      (validation?.checks || [])
        .filter((c) => c.status === "WARN")
        .map((c) => c.name),
    [validation],
  );

  const outcome = clientValidationOutcome(validation?.overall);
  const outcomeTone = validationOutcomeTone(outcome);
  const headerNames = useMemo(() => {
    const headers = inspect?.header_row;
    return Array.isArray(headers) ? headers.filter(Boolean) : [];
  }, [inspect]);

  async function applyAbeokutaPreset() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const { preset } = await getAbeokutaTmiPreset();
      setMeasurementType(preset.measurement_type);
      setCrs(preset.crs);
      setUnits(preset.units || "");
      setXCol(preset.x_column);
      setYCol(preset.y_column);
      setZCol(preset.z_column);
      setGeoCoverage(preset.geographic_coverage || "");
      setDescription(preset.measurement_description || "");
      setGridResolution("100");
      if (preset.publication_magnetic_params) {
        const p = preset.publication_magnetic_params;
        if (p.inclination_deg != null) setInclination(String(p.inclination_deg));
        if (p.declination_deg != null) setDeclination(String(p.declination_deg));
        if (p.gaussian_central_wavelength_m != null)
          setGaussWave(String(p.gaussian_central_wavelength_m));
        if (p.gaussian_std != null) setGaussStd(String(p.gaussian_std));
      }
      const declared = await declareGeologicalMetadata(geoId, {
        apply_abeokuta_tmi_preset: true,
        measurement_type: preset.measurement_type,
        measurement_description: preset.measurement_description,
        crs: preset.crs,
        working_crs: preset.working_crs || preset.processing_crs || "EPSG:32631",
        units: preset.units,
        x_column: preset.x_column,
        y_column: preset.y_column,
        z_column: preset.z_column,
        geographic_coverage: preset.geographic_coverage,
      });
      setDataset(declared.dataset);
      setNotice(
        "Abeokuta Sheet 260 metadata applied (X=easting, Y=northing, Z=TMI; source EPSG:32632 → processing EPSG:32631 → display EPSG:4326). Validate next.",
      );
      const previewBody = await previewGeologicalTmi(geoId);
      setTmiPreview(previewBody.preview);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not apply Abeokuta preset");
    } finally {
      setBusy(false);
    }
  }

  async function onDeclare(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body: Record<string, unknown> = {
        measurement_type: measurementType || null,
        crs: crs || null,
        units: units || null,
        description,
        source_client: sourceClient,
      };
      if (isTmi) {
        body.survey_date = surveyDate || null;
        body.survey_method = surveyMethod || null;
        body.sampling_spacing = samplingSpacing || null;
        body.processing_history = processingHistory || null;
        body.geographic_coverage = geoCoverage || null;
        body.source_organization = sourceClient || null;
      }
      if (dataset?.asset_kind === "point_grid_csv") {
        body.x_column = xCol;
        body.y_column = yCol;
        body.z_column = zCol;
      }
      if (looksAbeokuta || isTmi) {
        body.apply_abeokuta_tmi_preset = looksAbeokuta;
      }
      await declareGeologicalMetadata(geoId, body);
      setNotice("Metadata saved. Run validation next.");
      reload();
      if (isTmi || looksAbeokuta) {
        const previewBody = await previewGeologicalTmi(geoId);
        setTmiPreview(previewBody.preview);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Declare failed");
    } finally {
      setBusy(false);
    }
  }

  async function onValidate() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body = await validateGeologicalDataset(geoId);
      setDataset(body.dataset);
      setValidation(body.validation);
      setNotice(`Validation ${body.validation.overall}`);
      if (
        body.dataset.measurement_type === "total_magnetic_intensity" ||
        looksAbeokuta
      ) {
        const previewBody = await previewGeologicalTmi(geoId);
        setTmiPreview(previewBody.preview);
      }
    } catch (err) {
      // Validation may return 400 with a FAIL report still embedded — surface message.
      setError(err instanceof Error ? err.message : "Validation failed");
      reload();
      try {
        const previewBody = await previewGeologicalTmi(geoId);
        setTmiPreview(previewBody.preview);
      } catch {
        /* preview optional after fail */
      }
    } finally {
      setBusy(false);
    }
  }

  async function onDownloadOriginal() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await downloadGeologicalOriginal(geoId, dataset?.original_filename || undefined);
      setNotice("Original file download started.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setBusy(false);
    }
  }

  async function onActivate(status: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body = await setGeologicalActivation(geoId, {
        activation_status: status,
        acknowledged_warnings: status === "inactive" ? [] : ack,
      });
      setDataset(body.dataset);
      setNotice(`Activation set to ${body.dataset.activation_status}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Activation failed");
    } finally {
      setBusy(false);
    }
  }

  async function onProcessTmi() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body = await processGeologicalTmi(geoId, {
        resolution: Number(gridResolution),
      });
      setDataset(body.dataset);
      setProcessing(body.processing);
      setCompatibility(body.feature_compatibility || null);
      const mag = await listGeologicalMagnetic(geoId);
      setMagnetic(mag);
      setNotice("Derived TMI grid written (original preserved).");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Processing failed");
      reload();
    } finally {
      setBusy(false);
    }
  }

  async function onMagneticOp() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body = await runGeologicalMagnetic(geoId, {
        operation: magneticOp,
        resolution: Number(gridResolution) || 100,
        inclination_deg: Number(inclination),
        declination_deg: Number(declination),
        gaussian_central_wavelength_m: Number(gaussWave),
        gaussian_std: Number(gaussStd),
        gaussian_mode: gaussMode,
        rte_amplitude_clip: Number(rteClip),
      });
      setDataset(body.dataset);
      const mag = await listGeologicalMagnetic(geoId);
      setMagnetic(mag);
      setNotice(`Magnetic operation '${magneticOp}' completed (NOT_VALIDATED).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Magnetic operation failed");
    } finally {
      setBusy(false);
    }
  }

  async function onExtractLineaments() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body = await extractGeologicalLineaments(geoId, {
        percentile: 92,
        ensure_derivatives: true,
      });
      setDataset(body.dataset);
      const mag = await listGeologicalMagnetic(geoId);
      setMagnetic(mag);
      const stats = (body.lineaments?.statistics || {}) as {
        n_lineaments?: number;
      };
      setNotice(
        `Candidate magnetic lineaments extracted (n=${stats.n_lineaments ?? "?"}). ` +
          "NOT confirmed faults. NOT_VALIDATED. used_in_inference=false.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lineament extraction failed");
    } finally {
      setBusy(false);
    }
  }

  async function refreshMagnetic() {
    try {
      const mag = await listGeologicalMagnetic(geoId);
      setMagnetic(mag);
    } catch {
      /* optional */
    }
  }

  async function onCompatibility(decision: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body = await setGeologicalCompatibility(geoId, { decision });
      setDataset(body.dataset);
      setCompatibility(body.feature_compatibility || body.dataset.feature_compatibility || null);
      setNotice(`Compatibility decision: ${decision}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Compatibility update failed");
    } finally {
      setBusy(false);
    }
  }

  if (!dataset && !error) {
    return (
      <PlatformShell>
        <p className="text-sm text-stone">Loading dataset…</p>
      </PlatformShell>
    );
  }

  return (
    <PlatformShell>
      <Link href="/geological" className="text-xs text-stone underline">
        ← Geological catalogue
      </Link>
      <h1 className="mt-3 font-display text-2xl">{dataset?.display_name || geoId}</h1>
      <p className="mt-1 text-sm text-stone">
        {dataset?.geo_id} · {dataset?.asset_kind} · validation{" "}
        {dataset?.validation_status} · processing {dataset?.processing_status || "not_started"}{" "}
        · activation {dataset?.activation_status}
      </p>
      <p className="mt-2 text-xs text-stone">
        Scientific status: {dataset?.scientific_validation_status || "NOT_VALIDATED"}.
        Uploaded source ≠ validated ≠ processed ≠ model-compatible ≠ training-ready.
        Catalogue activation does not feed live 13-channel inference. Mutations and
        original download require operator/admin (<code>manage_geological</code>).
      </p>

      {error && <p className="mt-4 text-sm text-amber-900">{error}</p>}
      {notice && <p className="mt-4 text-sm text-leaf">{notice}</p>}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy || !dataset?.has_original}
          onClick={onDownloadOriginal}
          className="rounded-xl border border-meadow px-4 py-2 text-sm disabled:opacity-50"
        >
          Download original file
        </button>
        {dataset?.original_filename && (
          <span className="self-center text-xs text-stone">
            {dataset.original_filename}
            {dataset.content_sha256
              ? ` · sha256 ${String(dataset.content_sha256).slice(0, 12)}…`
              : ""}
          </span>
        )}
      </div>

      <section className="mt-8 rounded-2xl border border-meadow bg-chalk p-5">
        <h2 className="font-display text-lg">Inspect</h2>
        {!inspect || Object.keys(inspect).length === 0 ? (
          <p className="mt-2 text-sm text-stone">No inspect report yet.</p>
        ) : (
          <dl className="mt-3 grid gap-2 text-sm md:grid-cols-2">
            <div>
              <dt className="text-xs text-stone">Rows</dt>
              <dd>{String(inspect.row_count ?? "—")}</dd>
            </div>
            <div>
              <dt className="text-xs text-stone">Suggested columns</dt>
              <dd>{JSON.stringify(inspect.detected_columns || {})}</dd>
            </div>
            <div>
              <dt className="text-xs text-stone">Negative Z count</dt>
              <dd>{String(inspect.negative_z_count ?? "—")}</dd>
            </div>
            <div>
              <dt className="text-xs text-stone">Missing lattice cells</dt>
              <dd>{String(inspect.missing_lattice_cells ?? "—")}</dd>
            </div>
            <div className="md:col-span-2">
              <dt className="text-xs text-stone">Coverage bbox</dt>
              <dd>{JSON.stringify(inspect.coverage_bbox || dataset?.coverage_bbox || null)}</dd>
            </div>
          </dl>
        )}
      </section>

      <form
        onSubmit={onDeclare}
        className="mt-6 grid gap-3 rounded-2xl border border-meadow bg-chalk p-5 md:grid-cols-2"
      >
        <h2 className="font-display text-lg md:col-span-2">Declare metadata</h2>
        {(looksAbeokuta || isTmi || dataset?.asset_kind === "point_grid_csv") && (
          <div className="md:col-span-2 rounded-xl border border-leaf/40 bg-mist/60 p-3 text-sm">
            <p className="text-bark">
              Abeokuta Sheet 260 (publication-guided): <strong>X=easting</strong>,{" "}
              <strong>Y=northing</strong>, <strong>Z=TMI</strong>. Source{" "}
              <strong>EPSG:32632</strong> → processing <strong>EPSG:32631</strong> →
              display <strong>EPSG:4326</strong>. Z is not elevation or a hazard
              label. Not a Stage 2.5 training input.
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={() => void applyAbeokutaPreset()}
              className="mt-2 rounded-lg bg-leaf px-3 py-2 text-xs font-medium text-chalk disabled:opacity-50"
              data-testid="abeokuta-tmi-preset"
            >
              Apply Abeokuta TMI metadata
            </button>
          </div>
        )}
        {dataset?.asset_kind === "point_grid_csv" ? (
          <label className="text-xs md:col-span-2">
            Measurement type
            <select
              className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
              value={measurementType}
              onChange={(e) => setMeasurementType(e.target.value)}
              required
            >
              <option value="">Select…</option>
              <option value="overburden_thickness">overburden_thickness</option>
              <option value="depth_to_bedrock">depth_to_bedrock</option>
              <option value="total_magnetic_intensity">
                total_magnetic_intensity (TMI — not hazard labels)
              </option>
            </select>
          </label>
        ) : (
          <p className="text-xs text-stone md:col-span-2">
            Measurement type is fixed as lineament_vectors for this asset.
          </p>
        )}
        <label className="text-xs">
          Source CRS (required — never assumed)
          <select
            className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
            value={
              COMMON_CRS_OPTIONS.some((o) => o.code === crs) ? crs : crs ? "__custom__" : ""
            }
            onChange={(e) => {
              const v = e.target.value;
              if (v === "__custom__") return;
              setCrs(v);
            }}
            required={!crs}
          >
            <option value="">Select EPSG…</option>
            {COMMON_CRS_OPTIONS.map((o) => (
              <option key={o.code} value={o.code}>
                {o.code} — {o.label}
              </option>
            ))}
            {crs && !COMMON_CRS_OPTIONS.some((o) => o.code === crs) ? (
              <option value="__custom__">Custom: {crs}</option>
            ) : null}
          </select>
          <input
            className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
            value={crs}
            onChange={(e) => setCrs(e.target.value)}
            placeholder="Or type EPSG:#### / WKT"
            required
            aria-label="Source CRS text"
          />
          <span className="mt-1 block text-[11px] text-stone">
            Source CRS is the coordinate system of the uploaded file. Processing CRS
            (working metres grid) and display CRS (WGS84 map) are separate roles.
          </span>
        </label>
        {dataset?.asset_kind === "point_grid_csv" && (
          <label className="text-xs">
            Units {isTmi ? "(do not assume nT)" : ""}
            <input
              className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
              value={units}
              onChange={(e) => setUnits(e.target.value)}
              placeholder={isTmi ? "unknown or confirmed unit" : "m"}
              required={!isTmi}
            />
          </label>
        )}
        {dataset?.asset_kind === "point_grid_csv" && (
          <>
            <label className="text-xs">
              X column
              {headerNames.length ? (
                <select
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={xCol}
                  onChange={(e) => setXCol(e.target.value)}
                >
                  {headerNames.map((name) => (
                    <option key={`x-${name}`} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={xCol}
                  onChange={(e) => setXCol(e.target.value)}
                />
              )}
            </label>
            <label className="text-xs">
              Y column
              {headerNames.length ? (
                <select
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={yCol}
                  onChange={(e) => setYCol(e.target.value)}
                >
                  {headerNames.map((name) => (
                    <option key={`y-${name}`} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={yCol}
                  onChange={(e) => setYCol(e.target.value)}
                />
              )}
            </label>
            <label className="text-xs">
              Z / measurement column
              {headerNames.length ? (
                <select
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={zCol}
                  onChange={(e) => setZCol(e.target.value)}
                >
                  {headerNames.map((name) => (
                    <option key={`z-${name}`} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={zCol}
                  onChange={(e) => setZCol(e.target.value)}
                />
              )}
            </label>
          </>
        )}
        <label className="text-xs md:col-span-2">
          Description
          <input
            className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <label className="text-xs md:col-span-2">
          Source organization
          <input
            className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
            value={sourceClient}
            onChange={(e) => setSourceClient(e.target.value)}
            placeholder="Leave blank → remains unknown"
          />
        </label>
        {isTmi && (
          <>
            <label className="text-xs">
              Survey date
              <input
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={surveyDate}
                onChange={(e) => setSurveyDate(e.target.value)}
                placeholder="unknown if blank"
              />
            </label>
            <label className="text-xs">
              Survey method
              <input
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={surveyMethod}
                onChange={(e) => setSurveyMethod(e.target.value)}
                placeholder="unknown if blank"
              />
            </label>
            <label className="text-xs">
              Sampling / measurement spacing
              <input
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={samplingSpacing}
                onChange={(e) => setSamplingSpacing(e.target.value)}
                placeholder="unknown if blank"
              />
            </label>
            <label className="text-xs">
              Geographic coverage (text)
              <input
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={geoCoverage}
                onChange={(e) => setGeoCoverage(e.target.value)}
                placeholder="unknown if blank"
              />
            </label>
            <label className="text-xs md:col-span-2">
              Processing history (client-supplied)
              <input
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={processingHistory}
                onChange={(e) => setProcessingHistory(e.target.value)}
                placeholder="unknown if blank — no RTP/UC assumed"
              />
            </label>
          </>
        )}
        <button
          type="submit"
          disabled={busy}
          className="rounded-xl bg-leaf px-4 py-2 text-sm text-chalk disabled:opacity-50 md:w-fit"
        >
          Save declaration
        </button>
      </form>

      <div className="mt-6 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={onValidate}
          className="rounded-xl border border-meadow px-4 py-2 text-sm disabled:opacity-50"
        >
          Run validation
        </button>
      </div>

      {validation && Object.keys(validation).length > 0 && (
        <section className="mt-6 rounded-2xl border border-meadow bg-chalk p-5">
          <h2 className="font-display text-lg">
            Validation · {outcome}
            <span className="ml-2 text-sm font-normal text-stone">
              ({validation.overall || "—"})
            </span>
          </h2>
          <p
            className={
              outcomeTone === "ok"
                ? "mt-1 text-sm text-leaf"
                : outcomeTone === "warn"
                  ? "mt-1 text-sm text-amber-800"
                  : outcomeTone === "block"
                    ? "mt-1 text-sm text-red-800"
                    : "mt-1 text-sm text-stone"
            }
          >
            {outcome === "Ready"
              ? "Dataset meets requirements for compatible operations."
              : outcome === "Ready with warnings"
                ? "Processing is possible — read every warning before relying on outputs."
                : outcome === "Blocked"
                  ? "Fix the blocking issues below. Analysis controls stay disabled."
                  : "Run validation to determine readiness."}
          </p>
          <p className="mt-1 text-xs text-stone">
            can_train={String(validation.can_train ?? false)} · can_process=
            {String(validation.can_process ?? "—")} · can_activate_reporting=
            {String(validation.can_activate_reporting ?? "—")}
          </p>
          <ul className="mt-3 space-y-2 text-sm">
            {(validation.checks || []).map((check) => (
              <li key={check.name} className="rounded-lg border border-meadow/60 px-3 py-2">
                <span className="font-medium">
                  {check.name}: {check.status}
                </span>
                <p className="text-stone">{check.message}</p>
              </li>
            ))}
          </ul>
          <div className="mt-6 text-sm">
            <h3 className="font-medium">TMI spatial preview</h3>
            <TmiSurveyPreview preview={tmiPreview} />
          </div>

          {validation.tmi_statistics && (
            <div className="mt-4 text-sm">
              <h3 className="font-medium">TMI statistics</h3>
              <pre className="mt-2 overflow-x-auto rounded-lg bg-mist p-3 text-xs">
                {JSON.stringify(validation.tmi_statistics, null, 2)}
              </pre>
            </div>
          )}
          {validation.spatial && (
            <div className="mt-4 text-sm">
              <h3 className="font-medium">Spatial coverage</h3>
              <pre className="mt-2 overflow-x-auto rounded-lg bg-mist p-3 text-xs">
                {JSON.stringify(validation.spatial, null, 2)}
              </pre>
            </div>
          )}
        </section>
      )}

      {isTmi && (
        <section className="mt-6 rounded-2xl border border-meadow bg-chalk p-5">
          <h2 className="font-display text-lg">TMI gridding</h2>
          <p className="mt-1 text-xs text-stone">
            Grid TMI in the processing CRS (metres for Abeokuta EPSG:32631). Original
            CSV is never overwritten. Magnetic transforms are run separately below —
            not applied silently. Does not feed live hazard predictions.
          </p>
          {(dataset?.provenance || magnetic?.crs_roles) && (
            <dl className="mt-3 grid gap-2 text-sm md:grid-cols-3">
              <div>
                <dt className="text-xs text-stone">Source CRS</dt>
                <dd>
                  {String(
                    magnetic?.crs_roles?.source_crs ||
                      dataset?.crs ||
                      (dataset?.provenance as Record<string, unknown> | undefined)
                        ?.source_crs ||
                      "—",
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-stone">Processing CRS</dt>
                <dd>
                  {String(
                    magnetic?.crs_roles?.processing_crs ||
                      dataset?.working_crs ||
                      (dataset?.provenance as Record<string, unknown> | undefined)
                        ?.processing_crs ||
                      "—",
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-stone">Display CRS</dt>
                <dd>
                  {String(
                    magnetic?.crs_roles?.display_crs ||
                      (dataset?.provenance as Record<string, unknown> | undefined)
                        ?.display_crs ||
                      "EPSG:4326",
                  )}
                </dd>
              </div>
            </dl>
          )}
          <label className="mt-3 block text-xs">
            Grid resolution (metres for UTM processing; Sheet 260 ≈ 100 m)
            <input
              className="mt-1 w-full max-w-xs rounded-lg border border-meadow bg-mist px-3 py-2"
              value={gridResolution}
              onChange={(e) => setGridResolution(e.target.value)}
            />
          </label>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={
                busy ||
                dataset?.validation_status !== "validated" ||
                validation?.can_process === false
              }
              onClick={onProcessTmi}
              className="rounded-xl border border-meadow px-4 py-2 text-sm disabled:opacity-50"
            >
              Process TMI grid
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void refreshMagnetic()}
              className="rounded-xl border border-meadow px-4 py-2 text-sm disabled:opacity-50"
            >
              Refresh products
            </button>
          </div>
          {processing && Object.keys(processing).length > 0 && (
            <pre className="mt-3 overflow-x-auto rounded-lg bg-mist p-3 text-xs">
              {JSON.stringify(processing, null, 2)}
            </pre>
          )}
        </section>
      )}

      {isTmi && (
        <section className="mt-6 rounded-2xl border border-meadow bg-chalk p-5">
          <h2 className="font-display text-lg">Publication-guided magnetic processing</h2>
          <p className="mt-1 text-xs text-stone">
            Explicit operations only. Publication parameters (I=11.04°, D=3.52°, Gaussian
            λ=2000 m, σ=0.5) are recorded separately from implementation choices (RTE
            amplitude clip, FFT NoData fill, Gaussian low-pass default). Maps are for
            comparison with published interpretations — not faults, sinkholes, landslides
            or hazard scores. Scientific status:{" "}
            <strong>{magnetic?.scientific_validation_status || "NOT_VALIDATED"}</strong>.
          </p>

          {(magnetic?.gridding_reconciliation ||
            magnetic?.inspect_missing_lattice_cells != null) && (
            <div className="mt-4 rounded-xl border border-meadow/50 bg-mist/50 p-3 text-sm">
              <h3 className="font-medium">Gridding reconciliation</h3>
              <dl className="mt-2 grid gap-2 md:grid-cols-2">
                <div>
                  <dt className="text-xs text-stone">Source lattice empty (inspect)</dt>
                  <dd>{String(magnetic?.inspect_missing_lattice_cells ?? "—")}</dd>
                </div>
                <div>
                  <dt className="text-xs text-stone">Expected source lattice cells</dt>
                  <dd>{String(magnetic?.inspect_expected_full_grid_cells ?? "—")}</dd>
                </div>
                <div>
                  <dt className="text-xs text-stone">Processing NoData cells</dt>
                  <dd>
                    {String(
                      (
                        magnetic?.gridding_reconciliation as
                          | { processing_crs_scatter_bin?: { cells_remaining_nodata?: number } }
                          | undefined
                      )?.processing_crs_scatter_bin?.cells_remaining_nodata ?? "—",
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-stone">Observation cells / interpolated</dt>
                  <dd>
                    {String(
                      (
                        magnetic?.gridding_reconciliation as
                          | {
                              processing_crs_scatter_bin?: {
                                cells_populated_by_direct_observations?: number;
                                cells_populated_by_interpolation?: number;
                              };
                            }
                          | undefined
                      )?.processing_crs_scatter_bin?.cells_populated_by_direct_observations ??
                        "—",
                    )}{" "}
                    /{" "}
                    {String(
                      (
                        magnetic?.gridding_reconciliation as
                          | {
                              processing_crs_scatter_bin?: {
                                cells_populated_by_interpolation?: number;
                              };
                            }
                          | undefined
                      )?.processing_crs_scatter_bin?.cells_populated_by_interpolation ?? "—",
                    )}
                  </dd>
                </div>
              </dl>
              <p className="mt-2 text-xs text-stone">
                {(
                  magnetic?.gridding_reconciliation as { reconciliation_note?: string } | undefined
                )?.reconciliation_note ||
                  "Source-CRS missing lattice cells and processing-CRS NoData differ because UTM 32N→31N warps the survey lattice."}
              </p>
            </div>
          )}

          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <label className="text-xs">
              Operation
              <select
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={magneticOp}
                onChange={(e) => setMagneticOp(e.target.value)}
              >
                {(magnetic?.operation_catalog || []).map((c) => (
                  <option key={c.operation} value={c.operation}>
                    {c.title || c.operation}
                  </option>
                ))}
                {!(magnetic?.operation_catalog || []).length && (
                  <>
                    <option value="tmi">TMI</option>
                    <option value="rte">Reduction to Magnetic Equator</option>
                    <option value="gaussian">Gaussian filter</option>
                    <option value="analytic_signal">Analytic signal</option>
                    <option value="first_vertical_derivative">First vertical derivative</option>
                    <option value="first_horizontal_derivative">
                      First horizontal derivative (THG)
                    </option>
                    <option value="tilt_derivative">Tilt derivative</option>
                    <option value="radially_averaged_power_spectrum">
                      Radially averaged power spectrum
                    </option>
                  </>
                )}
              </select>
            </label>
            <p className="self-end text-xs text-stone md:col-span-1">
              {(magnetic?.operation_catalog || []).find((c) => c.operation === magneticOp)
                ?.summary || ""}
            </p>
            <label className="text-xs">
              Inclination (°) — publication
              <input
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={inclination}
                onChange={(e) => setInclination(e.target.value)}
              />
            </label>
            <label className="text-xs">
              Declination (°) — publication
              <input
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={declination}
                onChange={(e) => setDeclination(e.target.value)}
              />
            </label>
            <label className="text-xs">
              Gaussian wavelength (m) — publication
              <input
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={gaussWave}
                onChange={(e) => setGaussWave(e.target.value)}
              />
            </label>
            <label className="text-xs">
              Gaussian σ — publication
              <input
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={gaussStd}
                onChange={(e) => setGaussStd(e.target.value)}
              />
            </label>
            <label className="text-xs">
              Gaussian mode — implementation choice
              <select
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={gaussMode}
                onChange={(e) => setGaussMode(e.target.value)}
              >
                <option value="low_pass">low_pass (default)</option>
                <option value="high_pass">high_pass residual</option>
              </select>
            </label>
            <label className="text-xs">
              RTE amplitude clip — implementation choice (not publication)
              <input
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={rteClip}
                onChange={(e) => setRteClip(e.target.value)}
                placeholder="10 or empty to disable"
              />
            </label>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy || dataset?.validation_status !== "validated"}
              onClick={() => void onMagneticOp()}
              className="rounded-xl bg-leaf px-4 py-2 text-sm text-chalk disabled:opacity-50"
            >
              Run magnetic operation
            </button>
            <button
              type="button"
              disabled={busy || dataset?.validation_status !== "validated"}
              onClick={() => void onExtractLineaments()}
              className="rounded-xl border border-bark/30 bg-chalk px-4 py-2 text-sm text-bark disabled:opacity-50"
              data-testid="extract-candidate-lineaments"
            >
              Extract candidate magnetic lineaments
            </button>
          </div>
          <p className="mt-2 text-xs text-stone">
            Candidate lineaments follow magnetic gradient ridges. They are{" "}
            <strong>not</strong> confirmed faults or fractures, stay{" "}
            <code>NOT_VALIDATED</code>, and are not injected into the 13-channel
            inference model.
          </p>
          {magnetic && (
            <div className="mt-4 space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {(magnetic.products || [])
                  .filter((p) => p.preview_exists)
                  .map((p) => {
                    const file =
                      p.operation === "tmi"
                        ? "tmi_preview.png"
                        : p.operation === "radially_averaged_power_spectrum"
                          ? "raps_preview.png"
                          : p.operation === "candidate_lineament_extraction"
                            ? "candidate_lineaments_preview.png"
                            : `${p.operation}_preview.png`;
                    return (
                      <figure key={p.operation} className="text-sm">
                        <figcaption className="mb-1 text-xs text-stone">
                          {p.title || p.operation}
                          {p.units ? ` · ${p.units}` : ""}
                        </figcaption>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={geologicalDerivedUrl(geoId, file)}
                          alt={`${p.operation} preview`}
                          className="w-full rounded-lg border border-meadow bg-mist"
                        />
                      </figure>
                    );
                  })}
              </div>
              {(magnetic as MagneticProducts & { candidate_lineaments?: Record<string, unknown> })
                .candidate_lineaments && (
                <div className="rounded-xl border border-dashed border-meadow bg-mist/60 p-3 text-xs text-stone">
                  <p className="font-medium text-bark">Candidate lineament provenance</p>
                  <pre className="mt-2 overflow-x-auto">
                    {JSON.stringify(
                      (magnetic as { candidate_lineaments?: unknown }).candidate_lineaments,
                      null,
                      2,
                    )}
                  </pre>
                  <a
                    className="mt-2 inline-block font-semibold text-moss"
                    href={geologicalDerivedUrl(geoId, "candidate_lineaments.geojson")}
                  >
                    Download candidate_lineaments.geojson
                  </a>
                </div>
              )}
              {magnetic.raps && (
                <div>
                  <h3 className="text-sm font-medium">RAPS (no source-depth claim)</h3>
                  <p className="mt-1 text-xs text-stone">
                    {String(
                      (magnetic.raps.depth_interpretation as { note?: string } | undefined)
                        ?.note ||
                        "Wavelength vs log10(power). Depth interpretation requires an explicit fitting method.",
                    )}
                  </p>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={geologicalDerivedUrl(geoId, "raps_preview.png")}
                    alt="RAPS chart"
                    className="mt-2 max-w-xl rounded-lg border border-meadow bg-mist"
                  />
                </div>
              )}
              <div>
                <h3 className="text-sm font-medium">Processing history (provenance)</h3>
                <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-mist p-3 text-xs">
                  {JSON.stringify(magnetic.processing_history || [], null, 2)}
                </pre>
              </div>
              {magnetic.publication_comparison && (
                <div>
                  <h3 className="text-sm font-medium">Publication comparison notes</h3>
                  <pre className="mt-2 overflow-x-auto rounded-lg bg-mist p-3 text-xs">
                    {JSON.stringify(magnetic.publication_comparison, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {(compatibility || validation?.feature_compatibility) && (
        <section className="mt-6 rounded-2xl border border-meadow bg-chalk p-5">
          <h2 className="font-display text-lg">Feature schema compatibility</h2>
          <p className="mt-1 text-xs text-stone">
            Client TMI is not the Stage 2.5 <code>magnetics</code> (EMAG2) channel.
            The 13-channel production model is unchanged. Not training-ready.
          </p>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-mist p-3 text-xs">
            {JSON.stringify(
              compatibility || validation?.feature_compatibility,
              null,
              2,
            )}
          </pre>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              className="rounded-xl border border-meadow px-3 py-2 text-sm"
              onClick={() => onCompatibility("accepted_with_limitations")}
            >
              Accept with limitations
            </button>
            <button
              type="button"
              disabled={busy}
              className="rounded-xl border border-meadow px-3 py-2 text-sm"
              onClick={() => onCompatibility("rejected")}
            >
              Reject
            </button>
          </div>
        </section>
      )}

      <section className="mt-6 rounded-2xl border border-meadow bg-chalk p-5">
        <h2 className="font-display text-lg">Activation</h2>
        <p className="mt-1 text-xs text-stone">
          reporting_only enables catalogue coverage matching — not live inference.
          TMI cannot be approved into the Stage 2.5 feature stack.
        </p>
        {warnNames.length > 0 && (
          <fieldset className="mt-3 space-y-1 text-xs">
            <legend>Acknowledge warnings</legend>
            {warnNames.map((name) => (
              <label key={name} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={ack.includes(name)}
                  onChange={(e) => {
                    setAck((prev) =>
                      e.target.checked
                        ? [...prev, name]
                        : prev.filter((n) => n !== name),
                    );
                  }}
                />
                {name}
              </label>
            ))}
          </fieldset>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            className="rounded-xl border border-meadow px-3 py-2 text-sm"
            onClick={() => onActivate("inactive")}
          >
            Deactivate
          </button>
          <button
            type="button"
            disabled={busy || dataset?.validation_status !== "validated"}
            className="rounded-xl bg-leaf px-3 py-2 text-sm text-chalk disabled:opacity-50"
            onClick={() => onActivate("reporting_only")}
          >
            Activate reporting_only
          </button>
        </div>
      </section>
    </PlatformShell>
  );
}
