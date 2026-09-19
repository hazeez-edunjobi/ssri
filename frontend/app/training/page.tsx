"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  FlaskConical,
  Loader2,
  Upload,
} from "lucide-react";
import {
  type DatasetPreview,
  type TrainedModel,
  type TrainingDataset,
  type TrainingJobStatus,
  type TrainingRequirements,
  activateTrainedModel,
  createTrainingDataset,
  getActiveTrainedModel,
  getTrainingJob,
  getTrainingRequirements,
  listTrainedModels,
  listTrainingDatasets,
  startTrainingJob,
  uploadTrainingDatasetZip,
  validateTrainingDataset,
} from "@/lib/api";
import { DASHBOARD_HREF } from "@/lib/navigation";

type Step = "dataset" | "validate" | "configure" | "progress" | "result";

export default function TrainingPage() {
  const [step, setStep] = useState<Step>("dataset");
  const [requirements, setRequirements] = useState<TrainingRequirements | null>(
    null,
  );
  const [datasets, setDatasets] = useState<TrainingDataset[]>([]);
  const [models, setModels] = useState<TrainedModel[]>([]);
  const [activePath, setActivePath] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [geographicArea, setGeographicArea] = useState("");
  const [dataSource, setDataSource] = useState("");
  const [notes, setNotes] = useState("");

  const [dataset, setDataset] = useState<TrainingDataset | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [file, setFile] = useState<File | null>(null);

  const [epochs, setEpochs] = useState(5);
  const [batchSize, setBatchSize] = useState(2);
  const [learningRate, setLearningRate] = useState(0.001);
  const [seed, setSeed] = useState(42);
  const [modelName, setModelName] = useState("");

  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<TrainingJobStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshLists = useCallback(async () => {
    const [ds, ms, active] = await Promise.all([
      listTrainingDatasets(),
      listTrainedModels(),
      getActiveTrainedModel(),
    ]);
    setDatasets(ds.datasets);
    setModels(ms.models);
    setActivePath(active.checkpoint_path);
  }, []);

  useEffect(() => {
    getTrainingRequirements()
      .then(setRequirements)
      .catch((err: Error) => setError(err.message));
    refreshLists().catch((err: Error) => setError(err.message));
  }, [refreshLists]);

  useEffect(() => {
    if (!jobId || step !== "progress") return;
    let cancelled = false;
    const tick = async () => {
      try {
        const status = await getTrainingJob(jobId);
        if (cancelled) return;
        setJob(status);
        if (status.status === "completed") {
          setStep("result");
          await refreshLists();
        } else if (status.status === "failed" || status.status === "cancelled") {
          setError(status.error_message || "Training job failed.");
          setStep("result");
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    };
    tick();
    const id = window.setInterval(tick, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [jobId, step, refreshLists]);

  const onCreateAndUpload = async () => {
    setBusy(true);
    setError(null);
    try {
      if (!name.trim()) throw new Error("Dataset name is required.");
      if (!file) throw new Error("Choose a Stage 2.5 dataset .zip to upload.");
      const created = await createTrainingDataset({
        name: name.trim(),
        description,
        geographic_area: geographicArea,
        data_source: dataSource,
        notes,
        hazard_notes: "Stage 2.5 labels: subsidence, landslide, sinkhole",
      });
      const uploaded = await uploadTrainingDatasetZip(
        created.dataset.dataset_id,
        file,
      );
      setDataset(uploaded.dataset);
      setPreview(uploaded.preview);
      setStep("validate");
      await refreshLists();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onRevalidate = async () => {
    if (!dataset) return;
    setBusy(true);
    setError(null);
    try {
      const result = await validateTrainingDataset(dataset.dataset_id);
      setDataset(result.dataset);
      setPreview(result.preview);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onStart = async () => {
    if (!dataset) return;
    if (preview?.validation_status !== "passed") {
      setError("Fix validation errors before starting training.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const started = await startTrainingJob({
        dataset_id: dataset.dataset_id,
        epochs,
        batch_size: batchSize,
        learning_rate: learningRate,
        seed,
        model_name: modelName.trim() || null,
        device: "cpu",
      });
      setJobId(started.job_id);
      setStep("progress");
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
      await refreshLists();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const progress = job?.progress as
    | {
        phase?: string;
        epoch?: number;
        total_epochs?: number;
        train_loss?: number;
        validation_loss?: number;
        macro_f1?: number;
        message?: string;
      }
    | null
    | undefined;

  return (
    <main className="min-h-screen bg-void text-ink">
      <header className="border-b border-line bg-core/80 px-4 py-3 md:px-8">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link
              href={DASHBOARD_HREF}
              className="inline-flex items-center gap-1 text-xs text-muted hover:text-electric"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Assessment
            </Link>
            <span className="text-line">/</span>
            <h1 className="font-display text-lg text-ink">Manual Training</h1>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-muted">
            <FlaskConical className="h-3.5 w-3.5 text-cyan" />
            Research workflow · not scientific validation
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-5xl gap-6 px-4 py-8 md:grid-cols-[1fr_280px] md:px-8">
        <section className="space-y-6">
          <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-xs text-amber-100">
            Training completion means the model finished learning from your data.
            It does <strong>not</strong> mean the model is scientifically validated
            or production-ready.
          </div>

          {error && (
            <div className="rounded-xl border border-amber-500/40 bg-core px-4 py-3 text-xs text-amber-200">
              {error}
            </div>
          )}

          {step === "dataset" && (
            <div className="space-y-4 rounded-2xl border border-line bg-core p-5">
              <h2 className="font-display text-base">1. Create training dataset</h2>
              <p className="text-xs text-muted">
                Upload a Stage 2.5 dataset zip with{" "}
                <code className="text-cyan">manifest.json</code>,{" "}
                <code className="text-cyan">statistics.json</code>, and{" "}
                <code className="text-cyan">train/</code> +{" "}
                <code className="text-cyan">validation/</code> sample folders.
                Each sample needs <code className="text-cyan">feature_stack.npy</code>{" "}
                (13 channels), <code className="text-cyan">label.tif</code>, and{" "}
                <code className="text-cyan">metadata.json</code>.
              </p>
              <label className="block text-xs">
                Dataset name
                <input
                  className="mt-1 w-full rounded-lg border border-line bg-void px-3 py-2"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <label className="block text-xs">
                Description
                <textarea
                  className="mt-1 w-full rounded-lg border border-line bg-void px-3 py-2"
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </label>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="block text-xs">
                  Geographic area
                  <input
                    className="mt-1 w-full rounded-lg border border-line bg-void px-3 py-2"
                    value={geographicArea}
                    onChange={(e) => setGeographicArea(e.target.value)}
                  />
                </label>
                <label className="block text-xs">
                  Data source
                  <input
                    className="mt-1 w-full rounded-lg border border-line bg-void px-3 py-2"
                    value={dataSource}
                    onChange={(e) => setDataSource(e.target.value)}
                  />
                </label>
              </div>
              <label className="block text-xs">
                Notes
                <input
                  className="mt-1 w-full rounded-lg border border-line bg-void px-3 py-2"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </label>
              <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-line px-4 py-6 text-xs">
                <Upload className="h-4 w-4 text-cyan" />
                <span>
                  {file ? file.name : "Choose dataset .zip"}
                  <input
                    type="file"
                    accept=".zip,application/zip"
                    className="hidden"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                </span>
              </label>
              <button
                type="button"
                disabled={busy}
                onClick={onCreateAndUpload}
                className="rounded-xl bg-electric px-4 py-2 text-sm font-medium text-void disabled:opacity-50"
              >
                {busy ? "Uploading…" : "Upload & validate"}
              </button>
            </div>
          )}

          {step === "validate" && preview && (
            <div className="space-y-4 rounded-2xl border border-line bg-core p-5">
              <h2 className="font-display text-base">2. Dataset preview</h2>
              <div className="grid gap-2 text-xs md:grid-cols-2">
                <div>Samples: {preview.sample_count}</div>
                <div>
                  Splits: train {preview.train_count} · val {preview.validation_count} ·
                  test {preview.test_count}
                </div>
                <div>Channels: {preview.channel_count}</div>
                <div>
                  Spatial:{" "}
                  {preview.spatial_size
                    ? `${preview.spatial_size.height}×${preview.spatial_size.width}`
                    : "—"}
                </div>
                <div>CRS: {preview.crs || "—"}</div>
                <div>
                  Status:{" "}
                  <span
                    className={
                      preview.validation_status === "passed"
                        ? "text-leaf"
                        : "text-amber-300"
                    }
                  >
                    {preview.validation_status}
                  </span>
                </div>
              </div>
              {Object.keys(preview.class_distribution).length > 0 && (
                <div className="text-xs">
                  <div className="mb-1 text-muted">Class distribution (pixels)</div>
                  <ul className="space-y-1">
                    {Object.entries(preview.class_distribution).map(([k, v]) => (
                      <li key={k}>
                        {k}: {v}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {preview.errors.length > 0 && (
                <ul className="space-y-1 text-xs text-amber-200">
                  {preview.errors.map((item) => (
                    <li key={item}>• {item}</li>
                  ))}
                </ul>
              )}
              {preview.warnings.length > 0 && (
                <ul className="space-y-1 text-xs text-muted">
                  {preview.warnings.map((item) => (
                    <li key={item}>• {item}</li>
                  ))}
                </ul>
              )}
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={onRevalidate}
                  className="rounded-xl border border-line px-4 py-2 text-sm"
                >
                  Re-validate
                </button>
                <button
                  type="button"
                  disabled={busy || preview.validation_status !== "passed"}
                  onClick={() => setStep("configure")}
                  className="rounded-xl bg-electric px-4 py-2 text-sm font-medium text-void disabled:opacity-50"
                >
                  Configure training
                </button>
              </div>
            </div>
          )}

          {step === "configure" && (
            <div className="space-y-4 rounded-2xl border border-line bg-core p-5">
              <h2 className="font-display text-base">3. Configure training</h2>
              <p className="text-xs text-muted">
                Uses the existing SSRI Stage 2.5 trainer defaults. New checkpoints are
                saved separately and never overwrite the active model unless you promote
                them.
              </p>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="block text-xs">
                  Epochs
                  <input
                    type="number"
                    min={1}
                    className="mt-1 w-full rounded-lg border border-line bg-void px-3 py-2"
                    value={epochs}
                    onChange={(e) => setEpochs(Number(e.target.value))}
                  />
                </label>
                <label className="block text-xs">
                  Batch size
                  <input
                    type="number"
                    min={1}
                    className="mt-1 w-full rounded-lg border border-line bg-void px-3 py-2"
                    value={batchSize}
                    onChange={(e) => setBatchSize(Number(e.target.value))}
                  />
                </label>
                <label className="block text-xs">
                  Learning rate
                  <input
                    type="number"
                    step="0.0001"
                    className="mt-1 w-full rounded-lg border border-line bg-void px-3 py-2"
                    value={learningRate}
                    onChange={(e) => setLearningRate(Number(e.target.value))}
                  />
                </label>
                <label className="block text-xs">
                  Seed
                  <input
                    type="number"
                    className="mt-1 w-full rounded-lg border border-line bg-void px-3 py-2"
                    value={seed}
                    onChange={(e) => setSeed(Number(e.target.value))}
                  />
                </label>
              </div>
              <label className="block text-xs">
                Checkpoint name (optional)
                <input
                  className="mt-1 w-full rounded-lg border border-line bg-void px-3 py-2"
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                  placeholder="ssri-manual-run"
                />
              </label>
              <button
                type="button"
                disabled={busy}
                onClick={onStart}
                className="rounded-xl bg-electric px-4 py-2 text-sm font-medium text-void disabled:opacity-50"
              >
                {busy ? "Starting…" : "Start training"}
              </button>
            </div>
          )}

          {step === "progress" && (
            <div className="space-y-4 rounded-2xl border border-line bg-core p-5">
              <h2 className="flex items-center gap-2 font-display text-base">
                <Loader2 className="h-4 w-4 animate-spin text-cyan" />
                4. Training progress
              </h2>
              <div className="text-xs text-muted">Job: {jobId}</div>
              <div className="text-sm">Status: {job?.status || "queued"}</div>
              {progress && (
                <div className="grid gap-2 text-xs md:grid-cols-2">
                  <div>Phase: {progress.phase}</div>
                  <div>
                    Epoch: {progress.epoch ?? 0} / {progress.total_epochs ?? "—"}
                  </div>
                  <div>
                    Train loss:{" "}
                    {typeof progress.train_loss === "number"
                      ? progress.train_loss.toFixed(4)
                      : "—"}
                  </div>
                  <div>
                    Val loss:{" "}
                    {typeof progress.validation_loss === "number"
                      ? progress.validation_loss.toFixed(4)
                      : "—"}
                  </div>
                  <div>
                    Macro F1:{" "}
                    {typeof progress.macro_f1 === "number"
                      ? progress.macro_f1.toFixed(4)
                      : "—"}
                  </div>
                </div>
              )}
            </div>
          )}

          {step === "result" && (
            <div className="space-y-4 rounded-2xl border border-line bg-core p-5">
              <h2 className="flex items-center gap-2 font-display text-base">
                <CheckCircle2 className="h-4 w-4 text-leaf" />
                5. Training result
              </h2>
              {job?.status === "completed" ? (
                <>
                  <p className="text-sm text-leaf">Training completed successfully.</p>
                  <p className="text-xs text-muted">
                    Scientific validation status:{" "}
                    <strong>{job.scientific_validation_status}</strong>. Do not treat
                    this checkpoint as production-ready without separate evaluation.
                  </p>
                  {job.result && (
                    <pre className="overflow-auto rounded-xl bg-void p-3 text-[11px] text-muted">
                      {JSON.stringify(job.result, null, 2)}
                    </pre>
                  )}
                </>
              ) : (
                <p className="text-sm text-amber-200">
                  {job?.error_message || error || "Training did not complete."}
                </p>
              )}
              <button
                type="button"
                className="rounded-xl border border-line px-4 py-2 text-sm"
                onClick={() => {
                  setStep("dataset");
                  setJob(null);
                  setJobId(null);
                  setPreview(null);
                  setDataset(null);
                  setError(null);
                }}
              >
                Start another run
              </button>
            </div>
          )}
        </section>

        <aside className="space-y-4">
          <div className="rounded-2xl border border-line bg-core p-4 text-xs">
            <h3 className="mb-2 font-medium text-ink">Requirements</h3>
            {requirements ? (
              <ul className="space-y-1 text-muted">
                <li>Model: {requirements.architecture}</li>
                <li>Channels: {requirements.channels}</li>
                <li>Hazards: {requirements.hazards.join(", ")}</li>
                <li>Upload: {requirements.upload_format}</li>
              </ul>
            ) : (
              <p className="text-muted">Loading…</p>
            )}
          </div>

          <div className="rounded-2xl border border-line bg-core p-4 text-xs">
            <h3 className="mb-2 font-medium text-ink">Trained models</h3>
            {activePath && (
              <p className="mb-2 text-[11px] text-cyan">
                Active checkpoint set for promotion use.
              </p>
            )}
            {models.length === 0 && (
              <p className="text-muted">No trained models yet.</p>
            )}
            <ul className="space-y-3">
              {models.map((model) => (
                <li key={model.model_id} className="rounded-lg border border-line p-2">
                  <div className="font-medium text-ink">{model.name}</div>
                  <div className="text-[11px] text-muted">
                    {model.scientific_validation_status}
                    {model.active ? " · active" : ""}
                  </div>
                  <button
                    type="button"
                    disabled={busy || model.active}
                    onClick={() => onPromote(model.model_id)}
                    className="mt-2 text-[11px] text-electric disabled:opacity-40"
                  >
                    {model.active ? "Promoted" : "Promote for assessments"}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-line bg-core p-4 text-xs">
            <h3 className="mb-2 font-medium text-ink">Recent datasets</h3>
            {datasets.length === 0 && (
              <p className="text-muted">None yet.</p>
            )}
            <ul className="space-y-2 text-muted">
              {datasets.slice(0, 6).map((item) => (
                <li key={item.dataset_id}>
                  {item.name} · {item.validation_status}
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </main>
  );
}
