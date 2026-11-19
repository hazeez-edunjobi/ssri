"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, FlaskConical, Loader2, Upload } from "lucide-react";
import {
  activateTrainedModel,
  createTrainingDataset,
  getActiveTrainedModel,
  getShellEvaluation,
  getShellJob,
  getShellStatusFull,
  applyShellLabels,
  applyShellLineaments,
  applyShellOverburden,
  inspectShellLineaments,
  listTrainedModels,
  startShellTrainingJob,
  uploadShellDatasetZip,
  uploadShellLabelInventory,
  validateShellDataset,
  validateShellLayer,
  type ShellJobStatus,
  type ShellLayerReport,
  type ShellSettings,
  type ShellValidation,
  type TrainedModel,
} from "@/lib/api";
import { DASHBOARD_HREF } from "@/lib/navigation";

type Step = "upload" | "validate" | "train" | "evaluate" | "select";

const LIMITATIONS_FALLBACK = [
  "Scores are relative susceptibility rankings, not probabilities or risk estimates.",
  "Status stays NOT_VALIDATED. Not for insurance, engineering, safety, or emergency decisions.",
  "SYNTHETIC demos use fabricated labels and must never be treated as real geology.",
  "Models apply only inside the uploaded training geography.",
];

function statusTone(status: string): string {
  const s = status.toUpperCase();
  if (s === "PASS" || s === "EVALUATED" || s === "AVAILABLE") return "text-leaf";
  if (s === "WARN" || s === "WARNING") return "text-amber-800";
  if (s === "FAIL" || s.includes("NO ") || s.includes("DISABLED")) return "text-amber-900";
  return "text-stone";
}

export default function ReleaseShellPage() {
  const [step, setStep] = useState<Step>("upload");
  const [shellOn, setShellOn] = useState<boolean | null>(null);
  const [limitations, setLimitations] = useState<string[]>(LIMITATIONS_FALLBACK);
  const [name, setName] = useState("owner-upload");
  const [file, setFile] = useState<File | null>(null);
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [validation, setValidation] = useState<ShellValidation | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<ShellJobStatus | null>(null);
  const [evaluation, setEvaluation] = useState<Record<string, unknown> | null>(null);
  const [models, setModels] = useState<TrainedModel[]>([]);
  const [activePath, setActivePath] = useState<string | null>(null);
  const [epochs, setEpochs] = useState(3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [settings, setSettings] = useState<ShellSettings | null>(null);

  // Owner input panels (currently API-only surfaces exposed in plain language).
  const [layerFile, setLayerFile] = useState<File | null>(null);
  const [layerName, setLayerName] = useState("overburden_thickness");
  const [layerCrs, setLayerCrs] = useState("EPSG:32631");
  const [measurementType, setMeasurementType] = useState("thickness");
  const [layerUnits, setLayerUnits] = useState("m");
  const [layerReport, setLayerReport] = useState<ShellLayerReport | null>(null);
  const [labelFile, setLabelFile] = useState<File | null>(null);
  const [labelCrs, setLabelCrs] = useState("");
  const [labelInventory, setLabelInventory] = useState<Record<string, unknown> | null>(
    null,
  );
  const [lineamentFile, setLineamentFile] = useState<File | null>(null);
  const [lineamentCrs, setLineamentCrs] = useState("EPSG:32631");
  const [lineamentInfo, setLineamentInfo] = useState<Record<string, unknown> | null>(
    null,
  );
  const [lineamentApplied, setLineamentApplied] = useState<Record<string, unknown> | null>(
    null,
  );
  const [overburdenApplied, setOverburdenApplied] = useState<Record<string, unknown> | null>(
    null,
  );
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);

  // Hazards come from the backend registry (settings.hazards), never a local list.
  const hazardNames = (settings?.hazards ?? []).map((h) => h.name);
  const hazardNotes = hazardNames.length
    ? hazardNames.join(", ")
    : "subsidence, landslide, sinkhole";

  const refreshModels = useCallback(async () => {
    const [ms, active] = await Promise.all([
      listTrainedModels(),
      getActiveTrainedModel(),
    ]);
    setModels(ms.models);
    setActivePath(active.checkpoint_path);
  }, []);

  useEffect(() => {
    getShellStatusFull()
      .then((s) => {
        setShellOn(s.release_shell_enabled);
        if (s.limitations?.length) setLimitations(s.limitations);
        if (s.settings) setSettings(s.settings);
        return refreshModels().catch(() => undefined);
      })
      .catch((err: Error) => setError(err.message));
  }, [refreshModels]);

  useEffect(() => {
    if (!jobId || step !== "train") return;
    let cancelled = false;
    const tick = async () => {
      try {
        const status = await getShellJob(jobId);
        if (cancelled) return;
        setJob(status);
        if (status.status === "completed") {
          const result = status.result || {};
          const modelId =
            (result.model_id as string | undefined) ||
            ((result.seeds as Record<string, { model_id?: string }> | undefined)?.[
              "42"
            ]?.model_id);
          if (modelId) {
            try {
              const ev = await getShellEvaluation(modelId);
              if (!cancelled) setEvaluation(ev);
            } catch {
              if (result.evaluation) setEvaluation(result.evaluation as Record<string, unknown>);
            }
          } else if (result.evaluation) {
            setEvaluation(result.evaluation as Record<string, unknown>);
          }
          await refreshModels();
          setStep("evaluate");
        } else if (status.status === "failed" || status.status === "cancelled") {
          setError(status.error_message || "Training job failed.");
          setStep("evaluate");
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    };
    tick();
    const id = window.setInterval(tick, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [jobId, step, refreshModels]);

  const onUpload = async () => {
    setBusy(true);
    setError(null);
    setUploadProgress(0);
    try {
      if (!file) throw new Error("Choose a Stage 2.5 dataset ZIP.");
      const created = await createTrainingDataset({
        name: name.trim() || "owner-upload",
        notes: "Release-shell owner upload",
        hazard_notes: hazardNotes,
      });
      const id = created.dataset.dataset_id;
      await uploadShellDatasetZip(id, file, undefined, (ratio) =>
        setUploadProgress(ratio),
      );
      setDatasetId(id);
      const validated = await validateShellDataset(id);
      setValidation(validated.validation);
      setStep("validate");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
      setUploadProgress(null);
    }
  };

  const onRevalidate = async () => {
    if (!datasetId) return;
    setBusy(true);
    setError(null);
    try {
      const validated = await validateShellDataset(datasetId);
      setValidation(validated.validation);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onTrain = async () => {
    if (!datasetId) return;
    if (!validation?.can_train) {
      setError("Training refused: validation did not PASS/WARN with can_train.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const started = await startShellTrainingJob({
        dataset_id: datasetId,
        epochs,
        seeds: [42, 43, 44],
        device: "cpu",
      });
      setJobId(started.job_id);
      setStep("train");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onPromote = async (modelId: string) => {
    setBusy(true);
    setError(null);
    try {
      const result = await activateTrainedModel(modelId);
      setActivePath(result.checkpoint_path);
      await refreshModels();
      setStep("select");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onValidateLayer = async () => {
    setBusy(true);
    setError(null);
    setLayerReport(null);
    try {
      if (!layerFile) throw new Error("Choose a point-grid layer CSV (X, Y, value).");
      if (!layerCrs.trim()) {
        throw new Error(
          "Declare the CRS. We cannot guess it and negative X often means the file is not in longitude/latitude.",
        );
      }
      const result = await validateShellLayer(
        layerFile,
        layerName.trim(),
        layerCrs.trim(),
        undefined,
        undefined,
        measurementType,
        layerUnits.trim() || undefined,
      );
      setLayerReport(result.layer);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onUploadLabels = async () => {
    setBusy(true);
    setError(null);
    setLabelInventory(null);
    try {
      if (!labelFile) throw new Error("Choose a label inventory CSV.");
      if (!labelCrs.trim()) throw new Error("Declare the CRS for the label file.");
      const result = await uploadShellLabelInventory(labelFile, labelCrs.trim());
      setLabelInventory(result.labels);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onApplyLabels = async () => {
    setBusy(true);
    setError(null);
    try {
      if (!datasetId) throw new Error("Upload a Stage 2.5 dataset before applying labels.");
      if (!labelFile) throw new Error("Choose a label inventory CSV.");
      if (!labelCrs.trim()) throw new Error("Declare the CRS for the label file.");
      const result = await applyShellLabels(datasetId, labelFile, labelCrs.trim());
      setLabelInventory(result.labels_applied);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onInspectLineaments = async () => {
    setBusy(true);
    setError(null);
    setLineamentInfo(null);
    try {
      if (!lineamentFile) throw new Error("Choose a lineament vector file (GeoJSON).");
      const result = await inspectShellLineaments(lineamentFile);
      setLineamentInfo(result.lineaments);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onApplyLineaments = async () => {
    setBusy(true);
    setError(null);
    setLineamentApplied(null);
    try {
      if (!datasetId)
        throw new Error("Upload and validate a dataset first, then apply lineaments.");
      if (!lineamentFile) throw new Error("Choose a lineament vector file (GeoJSON).");
      if (!lineamentCrs.trim())
        throw new Error("Declare the lineament CRS. SSRI will not guess it.");
      const result = await applyShellLineaments(
        datasetId,
        lineamentFile,
        lineamentCrs.trim(),
      );
      setLineamentApplied(result.lineaments_applied);
      const validated = await validateShellDataset(datasetId);
      setValidation(validated.validation);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onApplyOverburden = async () => {
    setBusy(true);
    setError(null);
    setOverburdenApplied(null);
    try {
      if (!datasetId)
        throw new Error("Upload and validate a dataset first, then apply overburden.");
      if (!layerFile) throw new Error("Choose an overburden point-grid CSV.");
      if (!layerCrs.trim()) throw new Error("Declare the overburden CRS.");
      if (measurementType !== "thickness") {
        throw new Error(
          "Only measurement_type=thickness can be written into the v2 overburden_thickness channel. Depth-to-interface must use layer name depth_to_bedrock and is not auto-converted.",
        );
      }
      const result = await applyShellOverburden(datasetId, layerFile, {
        layerName: layerName.trim() || "overburden_thickness",
        crs: layerCrs.trim(),
        measurementType,
        units: layerUnits.trim() || "m",
      });
      setOverburdenApplied(result.overburden_applied);
      const validated = await validateShellDataset(datasetId);
      setValidation(validated.validation);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const aggregate =
    (evaluation?.aggregate_gates as Record<string, string> | undefined) ||
    (evaluation?.gates as Record<string, string> | undefined) ||
    null;
  const perHazard =
    (evaluation?.per_hazard as Record<string, Record<string, unknown>> | undefined) ||
    (evaluation?.hazards as Record<string, Record<string, unknown>> | undefined) ||
    null;
  const perBlock =
    (evaluation?.per_block as unknown[]) ||
    (evaluation?.block_table as unknown[]) ||
    null;

  return (
    <main className="min-h-screen bg-mist text-bark">
      <header className="border-b border-meadow bg-chalk/95 px-4 py-3 md:px-8">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link
              href={DASHBOARD_HREF}
              className="inline-flex items-center gap-1 text-xs text-stone hover:text-moss"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Assessment
            </Link>
            <span className="text-meadow">/</span>
            <h1 className="font-display text-lg text-bark">Owner training shell</h1>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-stone">
            <FlaskConical className="h-3.5 w-3.5 text-leaf" />
            NOT_VALIDATED · relative rankings only
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-5xl gap-6 px-4 py-8 md:grid-cols-[1fr_280px] md:px-8">
        <section className="space-y-6">
          {shellOn === false && (
            <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-xs text-amber-900">
              Release shell is off. Set <code>SSRI_RELEASE_SHELL=true</code> on the API
              and restart. Until then use{" "}
              <Link href="/training/operator" className="underline">
                classic operator training
              </Link>{" "}
              or see <code>poc/release_shell/OWNER_API_GUIDE.md</code>.
            </div>
          )}

          {error && (
            <div className="rounded-xl border border-amber-300 bg-chalk px-4 py-3 text-xs text-amber-900">
              {error}
            </div>
          )}

          {(step === "upload" || step === "validate") && (
            <div className="space-y-4 rounded-2xl border border-meadow bg-chalk p-5">
              <h2 className="font-display text-base">1. Upload Stage 2.5 ZIP</h2>
              <p className="text-xs text-stone">
                Georeferenced tiles with the channels for the declared schema (v1:{" "}
                {settings?.channel_schemas?.v1?.channel_count ?? 13} channels; v2:{" "}
                {settings?.channel_schemas?.v2?.channel_count ?? 16} channels, adding
                overburden and lineament layers) in documented order, labels per hazard,
                8+ separate 5° regions preferred. SYNTHETIC template is for dry-run only.
              </p>
              <label className="block text-xs">
                Dataset name
                <input
                  className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-meadow bg-mist px-3 py-4 text-xs">
                <Upload className="h-4 w-4 text-leaf" />
                <span>{file ? file.name : "Choose ZIP"}</span>
                <input
                  type="file"
                  accept=".zip"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              </label>
              <button
                type="button"
                disabled={busy || !file}
                onClick={onUpload}
                className="inline-flex items-center gap-2 rounded-lg bg-bark px-4 py-2 text-xs text-chalk disabled:opacity-50"
              >
                {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Upload and validate
              </button>
              {file && (
                <p className="text-[11px] text-stone">
                  {(file.size / (1024 * 1024)).toFixed(1)} MB selected. There is no
                  arbitrary app-level size rejection; disk, ZIP expansion guards, and
                  optional SSRI_UPLOAD_MAX_BYTES still apply.
                </p>
              )}
              {uploadProgress !== null && (
                <div className="space-y-1">
                  <div className="h-2 overflow-hidden rounded bg-mist">
                    <div
                      className="h-full bg-leaf transition-[width]"
                      style={{ width: `${Math.round(uploadProgress * 100)}%` }}
                    />
                  </div>
                  <p className="text-[11px] text-stone">
                    Upload progress {Math.round(uploadProgress * 100)}%
                  </p>
                </div>
              )}
            </div>
          )}

          <div className="space-y-4 rounded-2xl border border-meadow bg-chalk p-5">
            <div>
              <h2 className="font-display text-base">Prepare owner inputs</h2>
              <p className="text-xs text-stone">
                Optional checks you can run before training. Every file must carry an
                explicit CRS — we never guess coordinates. We only report here; nothing
                trains until you start training below.
              </p>
            </div>

            {settings && (
              <div className="rounded-xl border border-meadow/60 bg-mist px-3 py-3 text-xs">
                <p className="font-medium text-bark">Current settings</p>
                <ul className="mt-1 space-y-1 text-stone">
                  <li>
                    Block size:{" "}
                    {settings.block_size_deg != null
                      ? `${settings.block_size_deg}° (override)`
                      : `${settings.default_block_size_deg}° (default)`}{" "}
                    · buffer {settings.buffer_km} km
                  </li>
                  <li>
                    Minimums: {settings.minimums.tiles_per_hazard} tiles/hazard,{" "}
                    {settings.minimums.blocks} blocks,{" "}
                    {settings.minimums.held_out_blocks} held out
                  </li>
                  <li>
                    Channel schema: default {settings.default_channel_schema} ·
                    supported {settings.supported_channel_schemas.join(", ")}
                  </li>
                  <li data-testid="shell-hazard-registry">
                    Hazards (backend registry):{" "}
                    {hazardNames.length ? hazardNames.join(", ") : "unavailable"}
                  </li>
                  <li>
                    Preview unevaluated scores:{" "}
                    <span
                      className={
                        settings.preview_unevaluated_scores ? "text-leaf" : "text-amber-800"
                      }
                    >
                      {settings.preview_unevaluated_scores ? "on" : "off"}
                    </span>
                  </li>
                </ul>
                <p className="mt-1 text-[11px] text-stone">
                  Block size, schema version and the preview toggle are set by the API
                  operator via environment variables (see OWNER_API_GUIDE.md). They are
                  shown here so you know what training will use.
                </p>
                {settings.channel_schemas && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-bark">
                      Channel names per schema (layer → channel mapping)
                    </summary>
                    <ul className="mt-1 space-y-1 text-stone">
                      {Object.entries(settings.channel_schemas).map(([key, schema]) => (
                        <li key={key}>
                          <span className="font-medium text-bark">
                            {key} ({schema.channel_count} channels):
                          </span>{" "}
                          {schema.channel_names.join(", ")}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            )}

            <div className="rounded-xl border border-meadow/60 bg-mist px-3 py-3 text-xs">
              <p className="font-medium text-bark">Check a layer (CRS + units)</p>
              <p className="mt-1 text-stone">
                Upload a point-grid CSV (X, Y, value) and declare what the layer means and
                its CRS. We flag negative thickness and irregular gaps before you rely on
                it.
              </p>
              <div className="mt-2 grid gap-2 md:grid-cols-3">
                <label className="block">
                  Layer name
                  <input
                    className="mt-1 w-full rounded-lg border border-meadow bg-chalk px-3 py-2"
                    value={layerName}
                    onChange={(e) => setLayerName(e.target.value)}
                    list="shell-channel-names"
                  />
                  <datalist id="shell-channel-names">
                    {settings?.channel_schemas?.v2?.channel_names?.map((c) => (
                      <option key={c} value={c} />
                    ))}
                    <option value="depth_to_bedrock" />
                  </datalist>
                </label>
                <label className="block">
                  CRS (required)
                  <input
                    className="mt-1 w-full rounded-lg border border-meadow bg-chalk px-3 py-2"
                    value={layerCrs}
                    onChange={(e) => setLayerCrs(e.target.value)}
                    placeholder="e.g. EPSG:32631"
                  />
                </label>
                <label className="block">
                  File
                  <input
                    type="file"
                    accept=".csv,.txt"
                    className="mt-1 w-full text-[11px]"
                    onChange={(e) => setLayerFile(e.target.files?.[0] || null)}
                  />
                </label>
                <label className="block">
                  Measurement type
                  <select
                    className="mt-1 w-full rounded-lg border border-meadow bg-chalk px-3 py-2"
                    value={measurementType}
                    onChange={(e) => setMeasurementType(e.target.value)}
                  >
                    <option value="thickness">Thickness (overburden)</option>
                    <option value="depth_to_interface">Depth to interface</option>
                  </select>
                </label>
                <label className="block">
                  Units (required for thickness)
                  <input
                    className="mt-1 w-full rounded-lg border border-meadow bg-chalk px-3 py-2"
                    value={layerUnits}
                    onChange={(e) => setLayerUnits(e.target.value)}
                    placeholder="e.g. m — do not assume metres"
                  />
                </label>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy || !layerFile}
                  onClick={onValidateLayer}
                  className="inline-flex items-center gap-2 rounded-lg border border-bark px-3 py-2 disabled:opacity-50"
                >
                  {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Check layer
                </button>
                <button
                  type="button"
                  disabled={busy || !layerFile || !datasetId}
                  onClick={onApplyOverburden}
                  className="inline-flex items-center gap-2 rounded-lg border border-bark px-3 py-2 disabled:opacity-50"
                >
                  Apply thickness into dataset (v2)
                </button>
              </div>
              {overburdenApplied && (
                <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-chalk p-3 text-[11px] text-stone">
                  {JSON.stringify(overburdenApplied, null, 2)}
                </pre>
              )}
              {layerReport && (
                <div className="mt-2 rounded-lg border border-meadow/60 bg-chalk px-3 py-2">
                  <div className="flex justify-between gap-2">
                    <span className="font-medium">
                      {layerReport.layer_name || layerName}
                    </span>
                    <span className={statusTone(layerReport.overall)}>
                      {layerReport.overall}
                    </span>
                  </div>
                  <ul className="mt-1 space-y-1">
                    {(layerReport.checks || []).map((check) => (
                      <li key={check.name} className="flex justify-between gap-2">
                        <span>{check.name}</span>
                        <span className={statusTone(check.status)}>{check.status}</span>
                      </li>
                    ))}
                  </ul>
                  <ul className="mt-1 list-disc space-y-1 pl-4 text-stone">
                    {(layerReport.checks || [])
                      .filter((c) => c.status !== "PASS")
                      .map((c) => (
                        <li key={`m-${c.name}`}>{c.message}</li>
                      ))}
                  </ul>
                </div>
              )}
            </div>

            <div className="rounded-xl border border-meadow/60 bg-mist px-3 py-3 text-xs">
              <p className="font-medium text-bark">Label inventory (per hazard)</p>
              <p className="mt-1 text-stone">
                Upload the CSV listing known event locations. Declare its CRS. We report
                what we found per hazard; we never invent labels.
              </p>
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                <label className="block">
                  CRS (required)
                  <input
                    className="mt-1 w-full rounded-lg border border-meadow bg-chalk px-3 py-2"
                    value={labelCrs}
                    onChange={(e) => setLabelCrs(e.target.value)}
                    placeholder="e.g. EPSG:4326"
                  />
                </label>
                <label className="block">
                  File
                  <input
                    type="file"
                    accept=".csv,.txt"
                    className="mt-1 w-full text-[11px]"
                    onChange={(e) => setLabelFile(e.target.files?.[0] || null)}
                  />
                </label>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy || !labelFile}
                  onClick={onUploadLabels}
                  className="inline-flex items-center gap-2 rounded-lg border border-bark px-3 py-2 disabled:opacity-50"
                >
                  {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Summarise inventory
                </button>
                <button
                  type="button"
                  disabled={busy || !labelFile || !datasetId}
                  onClick={onApplyLabels}
                  className="inline-flex items-center gap-2 rounded-lg border border-leaf px-3 py-2 disabled:opacity-50"
                  data-testid="shell-apply-labels"
                >
                  Apply onto dataset tiles
                </button>
              </div>
              <p className="mt-1 text-[11px] text-stone">
                Apply snaps inventory points onto uploaded tiles. Empty cells stay
                unchanged. Re-validate before training.
              </p>
              {labelInventory && (
                <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-chalk p-3 text-[11px] text-stone">
                  {JSON.stringify(labelInventory, null, 2)}
                </pre>
              )}
            </div>

            <div className="rounded-xl border border-meadow/60 bg-mist px-3 py-3 text-xs">
              <p className="font-medium text-bark">Lineament vectors (optional)</p>
              <p className="mt-1 text-stone">
                Upload a GeoJSON of lineaments in the same projected metres CRS as the
                tiles. Inspect first, then apply to derive lineament_density /
                lineament_distance into every feature_stack (schema v2).
              </p>
              <label className="mt-2 block">
                CRS (required to apply)
                <input
                  className="mt-1 w-full rounded-lg border border-meadow bg-chalk px-3 py-2"
                  value={lineamentCrs}
                  onChange={(e) => setLineamentCrs(e.target.value)}
                  placeholder="e.g. EPSG:32631"
                />
              </label>
              <input
                type="file"
                accept=".geojson,.json"
                className="mt-2 w-full text-[11px]"
                onChange={(e) => setLineamentFile(e.target.files?.[0] || null)}
              />
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy || !lineamentFile}
                  onClick={onInspectLineaments}
                  className="inline-flex items-center gap-2 rounded-lg border border-bark px-3 py-2 disabled:opacity-50"
                >
                  {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Inspect lineaments
                </button>
                <button
                  type="button"
                  disabled={busy || !lineamentFile || !datasetId}
                  onClick={onApplyLineaments}
                  className="inline-flex items-center gap-2 rounded-lg border border-bark px-3 py-2 disabled:opacity-50"
                >
                  Apply density/distance into dataset
                </button>
              </div>
              {lineamentInfo && (
                <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-chalk p-3 text-[11px] text-stone">
                  {JSON.stringify(lineamentInfo, null, 2)}
                </pre>
              )}
              {lineamentApplied && (
                <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-chalk p-3 text-[11px] text-stone">
                  {JSON.stringify(lineamentApplied, null, 2)}
                </pre>
              )}
            </div>
          </div>

          {validation && (
            <div className="space-y-3 rounded-2xl border border-meadow bg-chalk p-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="font-display text-base">2. Validation report</h2>
                <span className={`text-sm font-medium ${statusTone(validation.overall)}`}>
                  {validation.overall}
                </span>
              </div>
              <p className="text-xs text-stone">
                can_train: {validation.can_train ? "yes" : "no"}
              </p>
              <ul className="space-y-2 text-xs">
                {(validation.checks || []).map((check) => (
                  <li
                    key={check.name}
                    className="rounded-lg border border-meadow/60 bg-mist px-3 py-2"
                  >
                    <div className="flex justify-between gap-2">
                      <span className="font-medium">{check.name}</span>
                      <span className={statusTone(check.status)}>{check.status}</span>
                    </div>
                    <p className="mt-1 text-stone">{check.message}</p>
                  </li>
                ))}
              </ul>
              {validation.hazards && (
                <div className="text-xs">
                  <p className="font-medium">Hazards</p>
                  <ul className="mt-1 space-y-1 text-stone">
                    {Object.entries(validation.hazards).map(([hz, info]) => (
                      <li key={hz}>
                        {hz}: {info.status || "unknown"}
                        {info.reason ? ` — ${info.reason}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={onRevalidate}
                  className="rounded-lg border border-meadow px-3 py-2 text-xs"
                >
                  Re-validate
                </button>
                <button
                  type="button"
                  disabled={busy || !validation.can_train}
                  onClick={onTrain}
                  className="inline-flex items-center gap-2 rounded-lg bg-bark px-4 py-2 text-xs text-chalk disabled:opacity-50"
                >
                  Start training (3 seeds)
                </button>
                <label className="flex items-center gap-2 text-xs text-stone">
                  Epochs
                  <input
                    type="number"
                    min={1}
                    max={50}
                    className="w-16 rounded border border-meadow bg-mist px-2 py-1"
                    value={epochs}
                    onChange={(e) => setEpochs(Number(e.target.value) || 3)}
                  />
                </label>
              </div>
            </div>
          )}

          {(step === "train" || job) && (
            <div className="space-y-3 rounded-2xl border border-meadow bg-chalk p-5">
              <h2 className="font-display text-base">3. Training progress</h2>
              <p className="text-xs text-stone">
                Job {jobId || "—"} · {job?.status || "queued"}
              </p>
              {job?.progress && (
                <pre className="overflow-auto rounded-lg bg-mist p-3 text-[11px] text-stone">
                  {JSON.stringify(job.progress, null, 2)}
                </pre>
              )}
            </div>
          )}

          {(step === "evaluate" || evaluation) && (
            <div className="space-y-3 rounded-2xl border border-meadow bg-chalk p-5">
              <h2 className="font-display text-base">4. Evaluation report</h2>
              <p className="text-xs text-stone">
                Gate strings only. Status remains NOT_VALIDATED.
              </p>
              {aggregate && (
                <ul className="space-y-1 text-xs">
                  {Object.entries(aggregate).map(([hz, gate]) => (
                    <li key={hz} className="flex justify-between gap-2">
                      <span>{hz}</span>
                      <span className={statusTone(String(gate))}>{String(gate)}</span>
                    </li>
                  ))}
                </ul>
              )}
              {perHazard && (
                <div className="space-y-2 text-xs">
                  <p className="font-medium">Per hazard (AUC / delta vs slope when present)</p>
                  {Object.entries(perHazard).map(([hz, row]) => (
                    <div
                      key={hz}
                      className="rounded-lg border border-meadow/60 bg-mist px-3 py-2"
                    >
                      <div className="font-medium">{hz}</div>
                      <pre className="mt-1 overflow-auto text-[11px] text-stone">
                        {JSON.stringify(row, null, 2)}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
              {perBlock && (
                <div className="text-xs">
                  <p className="font-medium">Per-block table</p>
                  <pre className="mt-1 overflow-auto rounded-lg bg-mist p-3 text-[11px] text-stone">
                    {JSON.stringify(perBlock, null, 2)}
                  </pre>
                </div>
              )}
              {!evaluation && (
                <p className="text-xs text-stone">
                  No evaluation payload yet. If training finished, open the job result or
                  follow OWNER_API_GUIDE.md.
                </p>
              )}
              <button
                type="button"
                onClick={() => setStep("select")}
                className="rounded-lg bg-bark px-4 py-2 text-xs text-chalk"
              >
                Choose checkpoint
              </button>
            </div>
          )}

          {(step === "select" || models.length > 0) && (
            <div className="space-y-3 rounded-2xl border border-meadow bg-chalk p-5">
              <h2 className="font-display text-base">5. Checkpoint selection</h2>
              <p className="text-xs text-stone">
                Active path: {activePath || "none"}
              </p>
              <ul className="space-y-2 text-xs">
                {models.map((m) => (
                  <li
                    key={m.model_id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-meadow/60 bg-mist px-3 py-2"
                  >
                    <div>
                      <div className="font-medium">{m.name || m.model_id}</div>
                      <div className="text-stone">{m.checkpoint_path}</div>
                    </div>
                    <button
                      type="button"
                      disabled={busy || m.active}
                      onClick={() => onPromote(m.model_id)}
                      className="rounded-lg border border-bark px-3 py-1 disabled:opacity-50"
                    >
                      {m.active ? "Active" : "Select"}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        <aside className="space-y-4">
          <div className="rounded-2xl border border-bark/20 bg-chalk px-4 py-3 text-xs text-bark">
            <p className="font-display text-sm text-bark">Known limitations</p>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-stone">
              {limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl border border-meadow bg-chalk px-4 py-3 text-xs text-stone">
            <p className="font-medium text-bark">API fallback</p>
            <p className="mt-1">
              If anything on this page is incomplete, use{" "}
              <code>poc/release_shell/OWNER_API_GUIDE.md</code>.
            </p>
          </div>
        </aside>
      </div>
    </main>
  );
}
