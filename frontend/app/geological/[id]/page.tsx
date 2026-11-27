"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Download } from "lucide-react";
import { PlatformShell } from "@/components/platform/PlatformShell";
import { GeologicalExplorationWorkspace } from "@/components/geological/GeologicalExplorationWorkspace";
import { GeologicalPipelineStepper } from "@/components/geological/GeologicalPipelineStepper";
import { GeologicalProcessingTimeline } from "@/components/geological/GeologicalProcessingTimeline";
import { GeologicalProductCards } from "@/components/geological/GeologicalProductCards";
import { GeologicalTechnicalDetails } from "@/components/geological/GeologicalTechnicalDetails";
import { Loader } from "@/components/ui/loader";
import { COMMON_CRS_OPTIONS } from "@/lib/crsOptions";
import {
  declareGeologicalMetadata,
  downloadGeologicalOriginal,
  extractGeologicalLineaments,
  fetchGeologicalDerived,
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
  directionBins,
  parseLineamentGeoJson,
  presentGeologicalProductCards,
  presentGlanceStats,
  presentPipelineSteps,
  presentProcessingHistory,
  statusBadges,
  type LineamentFeature,
} from "@/lib/geologicalPresentation";

export default function GeologicalDetailPage() {
  const params = useParams();
  const geoId = String(params.id || "");
  const [dataset, setDataset] = useState<GeologicalDataset | null>(null);
  const [inspect, setInspect] = useState<InspectReport | null>(null);
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

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
  const [processingHistoryNote, setProcessingHistoryNote] = useState("");
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
  const [activeOperation, setActiveOperation] = useState("tmi");
  const [showLineaments, setShowLineaments] = useState(true);
  const [lineamentFeatures, setLineamentFeatures] = useState<LineamentFeature[]>(
    [],
  );
  const [lineamentCrs, setLineamentCrs] = useState<string | null>(null);
  const [selectedLineamentId, setSelectedLineamentId] = useState<string | null>(
    null,
  );
  const [operatorOpen, setOperatorOpen] = useState(false);

  const isTmi =
    measurementType === "total_magnetic_intensity" || measurementType === "tmi";
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
      setProcessingHistoryNote(String(prov.processing_history || ""));
      setGeoCoverage(String(prov.geographic_coverage || ""));
      const cols = body.inspect?.detected_columns;
      const headers = body.inspect?.header_row;
      if (headers && cols) {
        setXCol(headers[cols.x ?? 0] || "X");
        setYCol(headers[cols.y ?? 1] || "Y");
        setZCol(headers[cols.z ?? 2] || "Z");
      }
      if (!body.dataset.crs || body.dataset.validation_status !== "validated") {
        setOperatorOpen(true);
      }
    },
    [],
  );

  const refreshMagnetic = useCallback(async () => {
    if (!geoId) return;
    const mag = await listGeologicalMagnetic(geoId);
    setMagnetic(mag);
  }, [geoId]);

  const reload = useCallback(() => {
    if (!geoId) return;
    getGeologicalDataset(geoId)
      .then(applyDetail)
      .catch((err: Error) => setError(err.message));
  }, [geoId, applyDetail]);

  const loadDetail = useCallback(async () => {
    if (!geoId) return;
    setLoading(true);
    setError(null);
    try {
      const body = await getGeologicalDataset(geoId);
      applyDetail(body);
      const mt = body.dataset.measurement_type;
      if (mt === "total_magnetic_intensity" || mt === "tmi") {
        try {
          const mag = await listGeologicalMagnetic(geoId);
          setMagnetic(mag);
          const previewBody = await previewGeologicalTmi(geoId);
          setTmiPreview(previewBody.preview);
        } catch {
          /* optional until validated/processed */
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load dataset");
    } finally {
      setLoading(false);
    }
  }, [geoId, applyDetail]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadDetail();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadDetail]);

  useEffect(() => {
    if (!geoId || !magnetic) return;
    const lineamentProduct = magnetic.products.find(
      (p) => p.operation === "candidate_lineament_extraction",
    );
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (!lineamentProduct?.geojson_exists) {
        setLineamentFeatures([]);
        setLineamentCrs(null);
        return;
      }
      void fetchGeologicalDerived(geoId, "candidate_lineaments.geojson")
        .then(async (blob) => {
          const text = await blob.text();
          if (cancelled) return;
          const parsed = parseLineamentGeoJson(JSON.parse(text));
          setLineamentFeatures(parsed.features);
          setLineamentCrs(parsed.crsName);
          setSelectedLineamentId((current) => current ?? parsed.features[0]?.id ?? null);
        })
        .catch(() => {
          if (!cancelled) {
            setLineamentFeatures([]);
            setLineamentCrs(null);
          }
        });
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [geoId, magnetic]);

  const warnNames = useMemo(
    () =>
      (validation?.checks || [])
        .filter((c) => c.status === "WARN")
        .map((c) => c.name),
    [validation],
  );

  const headerNames = useMemo(() => {
    const headers = inspect?.header_row;
    return Array.isArray(headers) ? headers.filter(Boolean) : [];
  }, [inspect]);

  const productCards = useMemo(
    () => presentGeologicalProductCards(magnetic),
    [magnetic],
  );
  const pipeline = useMemo(
    () =>
      presentPipelineSteps({
        dataset,
        validation,
        magnetic,
        compatibility,
      }),
    [dataset, validation, magnetic, compatibility],
  );
  const history = useMemo(
    () => presentProcessingHistory(magnetic, dataset),
    [magnetic, dataset],
  );
  const glance = useMemo(
    () => presentGlanceStats({ dataset, validation, magnetic }),
    [dataset, validation, magnetic],
  );
  const badges = useMemo(
    () => statusBadges({ dataset, validation }),
    [dataset, validation],
  );
  const bins = useMemo(() => directionBins(lineamentFeatures), [lineamentFeatures]);
  const valueRangeLabel = useMemo(() => {
    const range = glance.find((g) => g.label === "Value range");
    return range?.value || null;
  }, [glance]);

  async function applyAbeokutaPreset() {
    if (!geoId) return;
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
        if (p.gaussian_central_wavelength_m != null) {
          setGaussWave(String(p.gaussian_central_wavelength_m));
        }
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
      try {
        const previewBody = await previewGeologicalTmi(geoId);
        setTmiPreview(previewBody.preview);
      } catch {
        /* optional */
      }
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not apply Abeokuta preset");
    } finally {
      setBusy(false);
    }
  }

  async function onDeclare(event: FormEvent) {
    event.preventDefault();
    if (!geoId) return;
    setBusy(true);
    setError(null);
    try {
      await declareGeologicalMetadata(geoId, {
        measurement_type: measurementType || undefined,
        description: description || undefined,
        source_client: sourceClient || undefined,
        x_column: xCol,
        y_column: yCol,
        z_column: zCol,
        crs: crs || undefined,
        units: units || undefined,
        survey_date: surveyDate || undefined,
        survey_method: surveyMethod || undefined,
        sampling_spacing: samplingSpacing || undefined,
        processing_history: processingHistoryNote || undefined,
        geographic_coverage: geoCoverage || undefined,
      });
      setNotice("Metadata saved.");
      reload();
      try {
        const previewBody = await previewGeologicalTmi(geoId);
        setTmiPreview(previewBody.preview);
      } catch {
        /* optional */
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Declare failed");
    } finally {
      setBusy(false);
    }
  }

  async function onValidate() {
    if (!geoId) return;
    setBusy(true);
    setError(null);
    try {
      const body = await validateGeologicalDataset(geoId);
      setDataset(body.dataset);
      setValidation(body.validation);
      setNotice(`Validation ${body.validation.overall || "complete"}`);
      try {
        const previewBody = await previewGeologicalTmi(geoId);
        setTmiPreview(previewBody.preview);
      } catch {
        /* optional */
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDownloadOriginal() {
    if (!geoId) return;
    setBusy(true);
    setError(null);
    try {
      await downloadGeologicalOriginal(geoId, dataset?.original_filename);
      setNotice("Original file download started.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDownloadDerived(filename: string) {
    if (!geoId) return;
    setBusy(true);
    setError(null);
    try {
      const blob = await fetchGeologicalDerived(geoId, filename);
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setBusy(false);
    }
  }

  async function onActivate(status: string) {
    if (!geoId) return;
    setBusy(true);
    setError(null);
    try {
      const body = await setGeologicalActivation(geoId, {
        activation_status: status,
        acknowledged_warnings: status === "reporting_only" ? ack : [],
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
    if (!geoId) return;
    setBusy(true);
    setError(null);
    try {
      const body = await processGeologicalTmi(geoId, {
        resolution: Number(gridResolution) || 100,
      });
      setDataset(body.dataset);
      setProcessing(body.processing);
      if (body.feature_compatibility) setCompatibility(body.feature_compatibility);
      await refreshMagnetic();
      setActiveOperation("tmi");
      setNotice("TMI grid processed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Processing failed");
    } finally {
      setBusy(false);
    }
  }

  async function onMagneticOp() {
    if (!geoId) return;
    setBusy(true);
    setError(null);
    try {
      await runGeologicalMagnetic(geoId, {
        operation: magneticOp,
        inclination_deg: Number(inclination) || undefined,
        declination_deg: Number(declination) || undefined,
        gaussian_central_wavelength_m: Number(gaussWave) || undefined,
        gaussian_std: Number(gaussStd) || undefined,
        gaussian_mode: gaussMode,
        rte_amplitude_clip: rteClip.trim() ? Number(rteClip) : undefined,
      });
      await refreshMagnetic();
      setActiveOperation(magneticOp);
      setNotice(`Magnetic operation '${magneticOp}' completed (NOT_VALIDATED).`);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Magnetic operation failed");
    } finally {
      setBusy(false);
    }
  }

  async function onExtractLineaments() {
    if (!geoId) return;
    setBusy(true);
    setError(null);
    try {
      const body = await extractGeologicalLineaments(geoId, {});
      await refreshMagnetic();
      setShowLineaments(true);
      const count = (body.lineaments as { n_lineaments?: number } | undefined)
        ?.n_lineaments;
      setNotice(
        `Candidate lineaments extracted. NOT confirmed faults. used_in_inference=false. count=${String(
          count ?? "unknown",
        )}`,
      );
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lineament extraction failed");
    } finally {
      setBusy(false);
    }
  }

  async function onCompatibility(decision: string) {
    if (!geoId) return;
    setBusy(true);
    setError(null);
    try {
      const body = await setGeologicalCompatibility(geoId, { decision });
      if (body.feature_compatibility) setCompatibility(body.feature_compatibility);
      setDataset(body.dataset);
      setNotice(`Compatibility ${decision.split("_").join(" ")}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Compatibility update failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <PlatformShell>
        <Loader
          variant="section"
          title="Loading geological dataset"
          description="Fetching catalogue metadata and available magnetic products."
          data-testid="geological-detail-loading"
        />
      </PlatformShell>
    );
  }

  return (
    <PlatformShell>
      <div className="space-y-6" data-testid="geological-detail-workspace">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <Link href="/geological" className="text-xs text-moss hover:underline">
              ← Geological catalogue
            </Link>
            <h1 className="mt-2 font-display text-2xl text-bark">
              {dataset?.display_name || geoId}
            </h1>
            <p className="mt-1 font-mono text-[11px] text-stone">{geoId}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {badges.map((badge) => (
                <span
                  key={badge.label}
                  className={
                    badge.tone === "ok"
                      ? "rounded-full border border-leaf/40 bg-leaf/10 px-2.5 py-1 text-[11px] text-moss"
                      : badge.tone === "warn"
                        ? "rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 text-[11px] text-amber-900"
                        : badge.tone === "danger"
                          ? "rounded-full border border-red-300 bg-red-50 px-2.5 py-1 text-[11px] text-red-900"
                          : "rounded-full border border-meadow bg-mist px-2.5 py-1 text-[11px] text-stone"
                  }
                >
                  {badge.label}
                </span>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy || !dataset?.has_original}
              onClick={() => void onDownloadOriginal()}
              className="rounded-xl border border-meadow bg-chalk px-4 py-2 text-sm text-bark disabled:opacity-50"
            >
              Download original file
            </button>
            <button
              type="button"
              disabled={busy || lineamentFeatures.length === 0}
              onClick={() => void onDownloadDerived("candidate_lineaments.geojson")}
              className="inline-flex items-center gap-2 rounded-xl bg-moss px-4 py-2 text-sm text-chalk disabled:opacity-50"
            >
              <Download className="h-3.5 w-3.5" />
              Export lineaments (GeoJSON)
            </button>
          </div>
        </div>

        {error && (
          <p
            className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950"
            role="alert"
          >
            {error}
          </p>
        )}
        {notice && (
          <p className="rounded-xl border border-leaf/30 bg-leaf/10 px-3 py-2 text-sm text-moss">
            {notice}
          </p>
        )}

        <GeologicalPipelineStepper steps={pipeline} />

        <GeologicalExplorationWorkspace
          geoId={geoId}
          products={productCards}
          activeOperation={activeOperation}
          onChangeOperation={setActiveOperation}
          showLineaments={showLineaments}
          onToggleLineaments={setShowLineaments}
          lineamentFeatures={lineamentFeatures}
          selectedLineamentId={selectedLineamentId}
          onSelectLineament={setSelectedLineamentId}
          directionBins={bins}
          lineamentCrs={lineamentCrs}
          tmiPreview={tmiPreview}
          griddingProvenance={
            (magnetic?.gridding_provenance as Record<string, unknown> | null) ||
            null
          }
          valueRangeLabel={valueRangeLabel}
        />

        <GeologicalProductCards
          geoId={geoId}
          products={productCards}
          activeOperation={activeOperation}
          onSelect={setActiveOperation}
          onDownload={(filename) => void onDownloadDerived(filename)}
        />

        <div className="grid gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <GeologicalProcessingTimeline entries={history} />
          </div>
          <aside className="space-y-4 lg:col-span-2">
            <div className="rounded-2xl border border-meadow bg-chalk p-4">
              <h2 className="font-display text-lg text-bark">Dataset at a glance</h2>
              <dl className="mt-3 space-y-2 text-sm">
                {glance.map((row) => (
                  <div key={row.label} className="flex justify-between gap-3">
                    <dt className="text-stone">{row.label}</dt>
                    <dd className="font-medium text-bark">{row.value}</dd>
                  </div>
                ))}
                {!glance.length && (
                  <p className="text-xs text-stone">
                    Statistics appear after validation or magnetic product listing.
                  </p>
                )}
              </dl>
            </div>
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
              <h3 className="font-medium">What this dataset can and cannot do</h3>
              <p className="mt-2 text-xs leading-relaxed">
                Geological catalogue products support context, reporting, and map
                overlays. Client TMI does not replace the live EMAG2 magnetics channel,
                does not train Stage 2.5 models (can_train remains false), and remains
                NOT_VALIDATED for scientific or engineering decisions.
              </p>
            </div>
          </aside>
        </div>

        <GeologicalTechnicalDetails
          payload={{
            dataset,
            inspect,
            validation,
            compatibility,
            processing,
            magnetic,
            lineament_crs: lineamentCrs,
            lineament_count: lineamentFeatures.length,
          }}
        />

        <details
          className="rounded-2xl border border-meadow bg-chalk"
          open={operatorOpen}
          onToggle={(event) =>
            setOperatorOpen((event.target as HTMLDetailsElement).open)
          }
        >
          <summary className="cursor-pointer px-4 py-3 font-display text-lg text-bark">
            Processing controls
            <span className="ml-2 text-sm font-normal text-stone">
              Declare, validate, grid, magnetic ops, activation
            </span>
          </summary>
          <div className="space-y-6 border-t border-meadow/70 p-4">
            {looksAbeokuta && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void applyAbeokutaPreset()}
                className="rounded-xl border border-leaf/40 bg-leaf/10 px-4 py-2 text-sm text-moss disabled:opacity-50"
              >
                Apply Abeokuta TMI metadata
              </button>
            )}

            <form onSubmit={onDeclare} className="grid gap-3 md:grid-cols-2">
              <label className="text-xs">
                Measurement type
                <input
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={measurementType}
                  onChange={(e) => setMeasurementType(e.target.value)}
                />
              </label>
              <label className="text-xs">
                Source CRS
                <select
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={crs}
                  onChange={(e) => setCrs(e.target.value)}
                >
                  <option value="">Select CRS</option>
                  {COMMON_CRS_OPTIONS.map((option) => (
                    <option key={option.code} value={option.code}>
                      {option.code} — {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs">
                X column
                <select
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={xCol}
                  onChange={(e) => setXCol(e.target.value)}
                >
                  {(headerNames.length ? headerNames : ["X"]).map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs">
                Y column
                <select
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={yCol}
                  onChange={(e) => setYCol(e.target.value)}
                >
                  {(headerNames.length ? headerNames : ["Y"]).map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs">
                Z column
                <select
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={zCol}
                  onChange={(e) => setZCol(e.target.value)}
                >
                  {(headerNames.length ? headerNames : ["Z"]).map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs">
                Units
                <input
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={units}
                  onChange={(e) => setUnits(e.target.value)}
                />
              </label>
              <label className="text-xs md:col-span-2">
                Description
                <input
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </label>
              <label className="text-xs">
                Source client
                <input
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={sourceClient}
                  onChange={(e) => setSourceClient(e.target.value)}
                />
              </label>
              <label className="text-xs">
                Survey date
                <input
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={surveyDate}
                  onChange={(e) => setSurveyDate(e.target.value)}
                />
              </label>
              <label className="text-xs">
                Survey method
                <input
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={surveyMethod}
                  onChange={(e) => setSurveyMethod(e.target.value)}
                />
              </label>
              <label className="text-xs">
                Sampling spacing
                <input
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={samplingSpacing}
                  onChange={(e) => setSamplingSpacing(e.target.value)}
                />
              </label>
              <label className="text-xs md:col-span-2">
                Geographic coverage
                <input
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={geoCoverage}
                  onChange={(e) => setGeoCoverage(e.target.value)}
                />
              </label>
              <button
                type="submit"
                disabled={busy}
                className="rounded-xl border border-meadow px-4 py-2 text-sm disabled:opacity-50 md:col-span-2"
              >
                Save declaration
              </button>
            </form>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => void onValidate()}
                className="rounded-xl border border-meadow px-4 py-2 text-sm disabled:opacity-50"
              >
                Run validation
              </button>
            </div>

            {isTmi && (
              <div className="space-y-3 rounded-xl border border-meadow/70 p-3">
                <label className="block text-xs">
                  Grid resolution (metres)
                  <input
                    className="mt-1 w-full max-w-xs rounded-lg border border-meadow bg-mist px-3 py-2"
                    value={gridResolution}
                    onChange={(e) => setGridResolution(e.target.value)}
                  />
                </label>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={
                      busy ||
                      dataset?.validation_status !== "validated" ||
                      validation?.can_process === false
                    }
                    onClick={() => void onProcessTmi()}
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
                <label className="block text-xs">
                  Magnetic operation
                  <select
                    className="mt-1 w-full max-w-md rounded-lg border border-meadow bg-mist px-3 py-2"
                    value={magneticOp}
                    onChange={(e) => setMagneticOp(e.target.value)}
                  >
                    {(magnetic?.operation_catalog || []).map((c) => (
                      <option key={c.operation} value={c.operation}>
                        {c.title || c.operation}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="grid gap-2 md:grid-cols-2">
                  <label className="text-xs">
                    Inclination (°)
                    <input
                      className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                      value={inclination}
                      onChange={(e) => setInclination(e.target.value)}
                    />
                  </label>
                  <label className="text-xs">
                    Declination (°)
                    <input
                      className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                      value={declination}
                      onChange={(e) => setDeclination(e.target.value)}
                    />
                  </label>
                  <label className="text-xs">
                    Gaussian wavelength (m)
                    <input
                      className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                      value={gaussWave}
                      onChange={(e) => setGaussWave(e.target.value)}
                    />
                  </label>
                  <label className="text-xs">
                    Gaussian σ
                    <input
                      className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                      value={gaussStd}
                      onChange={(e) => setGaussStd(e.target.value)}
                    />
                  </label>
                  <label className="text-xs">
                    Gaussian mode
                    <select
                      className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                      value={gaussMode}
                      onChange={(e) => setGaussMode(e.target.value)}
                    >
                      <option value="low_pass">low_pass</option>
                      <option value="high_pass">high_pass</option>
                    </select>
                  </label>
                  <label className="text-xs">
                    RTE amplitude clip
                    <input
                      className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                      value={rteClip}
                      onChange={(e) => setRteClip(e.target.value)}
                    />
                  </label>
                </div>
                <div className="flex flex-wrap gap-2">
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
                    className="rounded-xl border border-bark/30 px-4 py-2 text-sm disabled:opacity-50"
                    data-testid="extract-candidate-lineaments"
                  >
                    Extract candidate magnetic lineaments
                  </button>
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => void onCompatibility("accepted_with_limitations")}
                className="rounded-xl border border-meadow px-4 py-2 text-sm disabled:opacity-50"
              >
                Accept with limitations
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void onCompatibility("rejected")}
                className="rounded-xl border border-meadow px-4 py-2 text-sm disabled:opacity-50"
              >
                Reject
              </button>
            </div>

            {warnNames.length > 0 && (
              <div className="space-y-2 text-sm">
                <p className="text-xs text-stone">
                  Acknowledge warnings before activation:
                </p>
                {warnNames.map((name) => (
                  <label key={name} className="flex items-center gap-2 text-xs">
                    <input
                      type="checkbox"
                      checked={ack.includes(name)}
                      onChange={(e) =>
                        setAck((prev) =>
                          e.target.checked
                            ? [...prev, name]
                            : prev.filter((item) => item !== name),
                        )
                      }
                    />
                    {name}
                  </label>
                ))}
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => void onActivate("inactive")}
                className="rounded-xl border border-meadow px-4 py-2 text-sm disabled:opacity-50"
              >
                Deactivate
              </button>
              <button
                type="button"
                disabled={busy || dataset?.validation_status !== "validated"}
                onClick={() => void onActivate("reporting_only")}
                className="rounded-xl bg-moss px-4 py-2 text-sm text-chalk disabled:opacity-50"
              >
                Activate reporting_only
              </button>
            </div>
          </div>
        </details>
      </div>
    </PlatformShell>
  );
}
