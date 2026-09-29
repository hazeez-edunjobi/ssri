"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { PlatformShell } from "@/components/platform/PlatformShell";
import { platformGet, platformPost, uploadDatasetVersionWithProgress } from "@/lib/platformApi";

type Phase = "idle" | "selected" | "uploading" | "validating" | "ready" | "failed";

type CsvAnalysis = {
  csv_kind?: string;
  rows?: number;
  grid?: { width: number; height: number };
  x_spacing?: number;
  y_spacing?: number;
  crs?: string;
  detected_features?: string[];
  missing_features?: string[];
  labels_detected?: boolean;
  status?: string;
  trainable?: boolean;
};

type Version = {
  id: string;
  dataset_id: string;
  validation_status: string;
  validation_errors: string[];
  file_name: string;
  preview?: { csv_analysis?: CsvAnalysis };
};

type Run = {
  id: string;
  name: string;
  status: string;
  scientific_validation_status: string;
};

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function TrainingPage() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState<"zip" | "csv">("zip");
  const [crs, setCrs] = useState("");
  const [datasetName, setDatasetName] = useState("");
  const [datasetDescription, setDatasetDescription] = useState("");
  const [progress, setProgress] = useState(0);
  const [version, setVersion] = useState<Version | null>(null);
  const [runName, setRunName] = useState("Training run");
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    platformGet<{ training_runs: Run[] }>("/training/runs")
      .then((body) => setRuns(body.training_runs))
      .catch(() => undefined);
  }, [phase]);

  function chooseFile(next: File | null) {
    setVersion(null);
    setError(null);
    setProgress(0);
    setFile(next);
    setPhase(next ? "selected" : "idle");
  }

  async function onUpload() {
    if (!file) return;
    const name = datasetName.trim();
    if (!name) {
      setError("Give this dataset a name before uploading.");
      setPhase("failed");
      return;
    }
    if (format === "csv" && !crs.trim()) {
      setError("CRS is required for this CSV because X/Y values are projected coordinates. Provide a code such as EPSG:32631.");
      setPhase("failed");
      return;
    }
    setError(null);
    setPhase("uploading");
    setProgress(0);
    try {
      const created = await platformPost<{ dataset: { id: string } }>("/datasets", {
        name,
        description: datasetDescription,
      });
      const uploaded = await uploadDatasetVersionWithProgress(
        created.dataset.id,
        file,
        (ratio) => {
          setProgress(ratio);
          if (ratio >= 1) setPhase("validating");
        },
        format === "csv" ? { crs: crs.trim() } : undefined,
      );
      const nextVersion = uploaded.version as unknown as Version;
      setVersion(nextVersion);
      if (nextVersion.validation_status === "passed") {
        setPhase("ready");
      } else {
        setPhase("failed");
        setError(
          nextVersion.validation_errors?.[0] ||
            "This dataset did not pass validation, so it cannot be used for training.",
        );
      }
    } catch (err) {
      setPhase("failed");
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  }

  async function onStart(event: FormEvent) {
    event.preventDefault();
    if (!version || version.validation_status !== "passed") return;
    setStarting(true);
    setError(null);
    try {
      await platformPost(
        "/training/runs",
        {
          dataset_id: version.dataset_id,
          dataset_version_id: version.id,
          name: runName,
          description: datasetDescription,
        },
        crypto.randomUUID(),
      );
      setPhase("idle");
      setFile(null);
      setVersion(null);
      setDatasetName("");
      setDatasetDescription("");
      const body = await platformGet<{ training_runs: Run[] }>("/training/runs");
      setRuns(body.training_runs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Training could not start");
    } finally {
      setStarting(false);
    }
  }

  return (
    <PlatformShell>
      <h1 className="font-display text-3xl font-semibold text-bark">Manual training</h1>
      <p className="mt-2 max-w-2xl text-sm text-stone">
        Upload your own dataset to train the SSRI model. SSRI validates the file you provide.
        A finished run is not scientifically validated.
      </p>

      <section className="mt-6 rounded-3xl border border-meadow bg-chalk p-5 shadow-soft">
        <label className="block text-xs font-medium text-stone">
          Dataset name
          <input
            className="mt-1 w-full rounded-md border border-meadow bg-mist px-3 py-2 text-sm text-bark"
            value={datasetName}
            onChange={(event) => setDatasetName(event.target.value)}
            placeholder="Lagos training tiles"
            disabled={phase === "uploading" || phase === "validating"}
          />
        </label>
        <fieldset className="mt-4">
          <legend className="text-xs font-medium text-stone">Dataset format</legend>
          <div className="mt-2 flex gap-4 text-sm text-bark">
            <label className="flex items-center gap-2">
              <input type="radio" name="dataset-format" checked={format === "zip"} onChange={() => setFormat("zip")} />
              Stage 2.5 ZIP
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" name="dataset-format" checked={format === "csv"} onChange={() => setFormat("csv")} />
              CSV
            </label>
          </div>
        </fieldset>
        {format === "csv" && (
          <div className="mt-3 text-sm text-stone">
            <p>Supported CSV: X/Y spatial coordinates, the 13 SSRI feature columns, training labels, and a CRS you provide. A single X,Y,Z file is one feature layer and cannot train the model by itself.</p>
            <label className="mt-3 block text-xs font-medium text-stone">
              CRS
              <input
                className="mt-1 w-full rounded-md border border-meadow bg-mist px-3 py-2 text-sm text-bark"
                value={crs}
                onChange={(event) => setCrs(event.target.value)}
                placeholder="EPSG:32631"
              />
            </label>
          </div>
        )}
        <label className="mt-3 block text-xs font-medium text-stone">
          Description
          <input
            className="mt-1 w-full rounded-md border border-meadow bg-mist px-3 py-2 text-sm text-bark"
            value={datasetDescription}
            onChange={(event) => setDatasetDescription(event.target.value)}
            disabled={phase === "uploading" || phase === "validating"}
          />
        </label>

        <label
          className="mt-4 flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-leaf bg-mist px-6 py-8 text-center"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            chooseFile(event.dataTransfer.files?.[0] ?? null);
          }}
        >
          <span className="font-display text-xl text-bark">Drop your dataset here</span>
          <span className="mt-2 text-sm text-stone">
            {format === "csv" ? "or choose a .csv file, or a zip of feature-layer CSVs" : "or choose a .zip file"}
          </span>
          <input
            className="mt-4 text-xs text-stone"
            type="file"
            accept={format === "csv" ? ".csv,.zip,text/csv,application/zip" : ".zip,application/zip"}
            disabled={phase === "uploading" || phase === "validating"}
            onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
          />
        </label>

        {file && (
          <div className="mt-4 text-sm text-bark">
            <div className="font-medium">{file.name}</div>
            <div className="text-xs text-stone">{formatSize(file.size)}</div>
          </div>
        )}

        {(phase === "uploading" || phase === "validating") && (
          <div className="mt-4">
            <p className="text-sm text-moss">
              {phase === "uploading" ? "Uploading…" : "Validating dataset…"}
            </p>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-meadow">
              <div
                className="h-full bg-leaf transition-all"
                style={{ width: `${Math.round((phase === "validating" ? 1 : progress) * 100)}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-stone">{Math.round((phase === "validating" ? 1 : progress) * 100)}%</p>
          </div>
        )}

        {version?.preview?.csv_analysis && (
          <CsvReport analysis={version.preview.csv_analysis} />
        )}
        {phase === "ready" && (
          <p className="mt-4 text-sm font-semibold text-moss">Dataset validated. A finished run is still not scientifically validated.</p>
        )}
        {phase === "failed" && error && (
          <p className="mt-4 text-sm text-amber-900">{error}</p>
        )}
        {version && version.validation_status !== "passed" && version.validation_errors.length > 0 && (
          <ul className="mt-2 list-disc pl-5 text-xs text-amber-900">
            {version.validation_errors.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}

        {phase === "selected" && (
          <button
            type="button"
            className="mt-4 rounded-md bg-leaf px-4 py-2.5 text-sm font-semibold text-chalk hover:bg-moss"
            onClick={() => void onUpload()}
          >
            Upload dataset
          </button>
        )}
        {phase === "failed" && (
          <button
            type="button"
            className="mt-4 rounded-md border border-meadow px-4 py-2.5 text-sm font-semibold text-bark"
            onClick={() => chooseFile(null)}
          >
            Choose a different file
          </button>
        )}
      </section>

      {phase === "ready" && version && (
        <form onSubmit={onStart} className="mt-6 space-y-3 rounded-3xl border border-meadow bg-chalk p-5 shadow-soft">
          <h2 className="font-display text-xl text-bark">Continue to training</h2>
          <p className="text-sm text-stone">
            This run uses the dataset you just uploaded. It does not load a dataset from SSRI.
          </p>
          <label className="block text-xs font-medium text-stone">
            Training name
            <input
              className="mt-1 w-full rounded-md border border-meadow bg-mist px-3 py-2 text-sm text-bark"
              value={runName}
              onChange={(event) => setRunName(event.target.value)}
              required
            />
          </label>
          <button
            disabled={starting}
            className="rounded-md bg-leaf px-4 py-2.5 text-sm font-semibold text-chalk hover:bg-moss disabled:opacity-50"
            type="submit"
          >
            {starting ? "Starting…" : "Continue to training"}
          </button>
        </form>
      )}

      {error && phase !== "failed" && <p className="mt-4 text-sm text-amber-900">{error}</p>}

      <section className="mt-8">
        <h2 className="font-display text-lg text-bark">Training history</h2>
        {runs.length === 0 ? (
          <p className="mt-3 text-sm text-stone">No training runs yet. Upload a dataset above to start one.</p>
        ) : (
          <table className="mt-3 w-full text-left text-sm">
            <thead className="text-xs text-stone">
              <tr><th>Run</th><th>Status</th><th>Scientific status</th></tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className="border-t border-meadow">
                  <td className="py-2">
                    <Link href={`/training/${run.id}`} className="text-moss">{run.name}</Link>
                  </td>
                  <td>{run.status}</td>
                  <td>{run.scientific_validation_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="mt-4 text-xs text-stone">
          Datasets you have already uploaded stay on <Link className="text-moss" href="/datasets">My datasets</Link>.
        </p>
      </section>
    </PlatformShell>
  );
}

function CsvReport({ analysis }: { analysis: CsvAnalysis }) {
  const featureOnly = analysis.status === "FEATURE_LAYER_ONLY" || analysis.trainable === false;
  return (
    <div className="mt-4 rounded-2xl border border-meadow bg-mist p-4 text-sm text-bark">
      <p className="font-semibold">{featureOnly ? "Feature layer only" : "CSV analysis"}</p>
      <p className="mt-2 text-stone">
        Rows: {analysis.rows ?? "—"}. Grid: {analysis.grid ? `${analysis.grid.width} × ${analysis.grid.height}` : "—"}.
        X spacing: {analysis.x_spacing ?? "—"}. Y spacing: {analysis.y_spacing ?? "—"}. CRS: {analysis.crs || "—"}.
      </p>
      <p className="mt-2">Detected features: {(analysis.detected_features || []).join(", ") || "none"}</p>
      <p>Labels: {analysis.labels_detected ? "detected" : "missing"}</p>
      {featureOnly && (
        <p className="mt-2 text-canopy">
          Additional SSRI feature layers and training labels are required before this file can train the model.
        </p>
      )}
    </div>
  );
}
