"use client";

import { useCallback, useEffect, useState } from "react";
import { PlatformShell } from "@/components/platform/PlatformShell";
import {
  fetchSubsidenceValidation,
  outcomeLabel,
  type SubsidenceValidationResponse,
} from "@/lib/subsidenceValidationApi";

function metricEntries(report: Record<string, unknown>): Array<[string, unknown]> {
  const metrics = report.metrics;
  if (!metrics || typeof metrics !== "object") return [];
  const obj = metrics as Record<string, unknown>;
  if (obj.metrics_computed !== true) return [];
  return Object.entries(obj).filter(([key]) => key !== "metrics_computed" && key !== "calibration_curve" && key !== "confusion_matrix");
}

export default function SubsidenceValidationPage() {
  const [data, setData] = useState<SubsidenceValidationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchSubsidenceValidation()
      .then((body) => {
        setData(body);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message);
        setData(null);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const report = data?.report ?? {};
  const quality =
    report.inventory_quality && typeof report.inventory_quality === "object"
      ? (report.inventory_quality as Record<string, unknown>)
      : null;
  const metrics = metricEntries(report);
  const reason =
    typeof report.reason === "string"
      ? report.reason
      : data?.ui_guidance?.outcome_meanings?.[data.outcome ?? ""] ?? null;

  return (
    <PlatformShell>
      <main className="mx-auto max-w-3xl px-6 py-10 text-bark">
        <p className="text-xs uppercase tracking-[0.2em] text-stone">Scientific integrity</p>
        <h1 className="mt-2 font-display text-3xl text-ink">Subsidence validation</h1>
        <p className="mt-3 max-w-2xl text-sm text-stone">
          Independent ground-truth review for the Stage 2.5 subsidence head. A healthy API,
          successful inference, or high susceptibility score is not scientific validation.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={reload}
            className="rounded-md border border-meadow bg-chalk px-4 py-2 text-sm text-ink"
            data-testid="validation-reload"
          >
            Refresh status
          </button>
        </div>

        {loading ? (
          <p className="mt-8 text-sm text-stone" data-testid="validation-loading">
            Loading validation status…
          </p>
        ) : null}

        {error ? (
          <div
            className="mt-8 rounded-2xl border border-clay/40 bg-chalk p-5 text-sm"
            data-testid="validation-error"
            role="alert"
          >
            <h2 className="font-display text-lg text-ink">Could not load validation</h2>
            <p className="mt-2 text-stone">{error}</p>
          </div>
        ) : null}

        {!loading && !error && data ? (
          <section className="mt-8 space-y-6" data-testid="validation-result">
            <div className="rounded-2xl border border-meadow bg-chalk p-5">
              <p className="text-xs uppercase tracking-wide text-stone">Outcome</p>
              <p className="mt-1 font-display text-xl text-ink" data-testid="validation-outcome">
                {outcomeLabel(data.outcome)}
              </p>
              <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-stone">Scientific status</dt>
                  <dd className="font-medium text-ink" data-testid="validation-scientific-status">
                    {data.scientific_validation_status}
                  </dd>
                </div>
                <div>
                  <dt className="text-stone">Independent ground truth</dt>
                  <dd className="font-medium text-ink" data-testid="validation-gt-available">
                    {data.ground_truth_available ? "Available for review" : "Not available"}
                  </dd>
                </div>
              </dl>
              {reason ? (
                <p className="mt-4 text-sm text-stone" data-testid="validation-reason">
                  {reason}
                </p>
              ) : null}
            </div>

            {data.ground_truth_provenance ? (
              <div className="rounded-2xl border border-meadow/60 bg-mist/40 p-5 text-sm">
                <h2 className="font-display text-lg text-ink">Provenance</h2>
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs text-stone">
                  {JSON.stringify(data.ground_truth_provenance, null, 2)}
                </pre>
              </div>
            ) : null}

            {quality ? (
              <div className="rounded-2xl border border-meadow/60 bg-mist/40 p-5 text-sm">
                <h2 className="font-display text-lg text-ink">Inventory quality</h2>
                <ul className="mt-3 space-y-1 text-stone">
                  <li>Total records: {String(quality.n_total ?? "—")}</li>
                  <li>Positives: {String(quality.n_positives ?? "—")}</li>
                  <li>Negatives: {String(quality.n_negatives ?? "—")}</li>
                  <li>
                    Underpowered:{" "}
                    {quality.underpowered === true
                      ? "yes — below minimum floors"
                      : quality.underpowered === false
                        ? "no"
                        : "—"}
                  </li>
                </ul>
              </div>
            ) : null}

            {metrics.length > 0 ? (
              <div className="rounded-2xl border border-meadow/60 bg-mist/40 p-5 text-sm">
                <h2 className="font-display text-lg text-ink">Supported metrics</h2>
                <p className="mt-2 text-stone">
                  Exploratory software metrics only. Status remains NOT_VALIDATED.
                </p>
                <ul className="mt-3 space-y-1" data-testid="validation-metrics">
                  {metrics.map(([key, value]) => (
                    <li key={key}>
                      <span className="text-stone">{key}:</span>{" "}
                      <span className="text-ink">
                        {typeof value === "number" ? value.toFixed(4) : String(value)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div
                className="rounded-2xl border border-dashed border-meadow bg-chalk p-5 text-sm text-stone"
                data-testid="validation-metrics-empty"
              >
                No metrics are shown. Missing metrics are never displayed as zero.
              </div>
            )}

            {Array.isArray(data.ui_guidance?.never_implies) ? (
              <ul className="list-disc space-y-1 pl-5 text-sm text-stone">
                {data.ui_guidance!.never_implies!.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
          </section>
        ) : null}

        {!loading && !error && !data ? (
          <p className="mt-8 text-sm text-stone" data-testid="validation-empty">
            No validation payload returned.
          </p>
        ) : null}
      </main>
    </PlatformShell>
  );
}
