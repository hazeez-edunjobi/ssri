"use client";

import { Download, Gauge, X } from "lucide-react";
import type { AssessResponse, HazardProfile, ShellSettings } from "@/lib/api";
import { buildAssessmentReportHtml } from "@/lib/report";

/**
 * Deterministic palette (one accent per surface). Indexed by position so it
 * never depends on a hard-coded hazard-name list from the frontend.
 */
const HAZARD_PALETTE = ["#2D6A4F", "#9C6644", "#40916C", "#3EA6FF", "#6B7A71"];

function colorFor(index: number): string {
  return HAZARD_PALETTE[index % HAZARD_PALETTE.length];
}

function tierClass(tier: string | undefined): string {
  if (!tier) return "text-stone";
  if (tier.includes("Extrapolation")) return "text-amber-800";
  if (tier === "High") return "text-emerald";
  if (tier === "Moderate") return "text-leaf";
  return "text-stone";
}

function gateTone(gate: string | null | undefined): string {
  if (gate === "evaluated") return "text-leaf";
  if (!gate) return "text-stone";
  if (gate === "outside_training_region") return "text-amber-800";
  return "text-stone";
}

function scoreOf(profile: HazardProfile): number | null {
  if (typeof profile.score === "number" && Number.isFinite(profile.score)) {
    return profile.score;
  }
  if (
    typeof profile.susceptibility_score === "number" &&
    Number.isFinite(profile.susceptibility_score)
  ) {
    return profile.susceptibility_score;
  }
  return null;
}

function scoreAllowed(profile: HazardProfile): boolean {
  const gate = profile.gate_status;
  if (gate == null) return true; // classic (flag OFF) response
  if (gate === "evaluated") return true;
  return Boolean(profile.preview_unevaluated_scores);
}

type AssessResultModalProps = {
  open: boolean;
  loading: boolean;
  error: string | null;
  result: AssessResponse | null;
  locationLabel: string | null;
  point?: { latitude: number; longitude: number } | null;
  settings?: ShellSettings | null;
  onClose: () => void;
  onViewMap: () => void;
};

export function AssessResultModal({
  open,
  loading,
  error,
  result,
  locationLabel,
  point,
  settings,
  onClose,
  onViewMap,
}: AssessResultModalProps) {
  if (!open) return null;

  const downloadReport = () => {
    if (!result) return;
    const html = buildAssessmentReportHtml({
      result,
      locationLabel,
      point: point ?? null,
      settings: settings ?? null,
    });
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ssri-assessment-${result.assessment_id}.html`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="assess-result-title"
      data-testid="assess-result-modal"
    >
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-meadow bg-chalk p-5 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-widest text-leaf">
              Assessment result
            </p>
            <h2
              id="assess-result-title"
              className="mt-1 font-display text-lg text-bark"
            >
              {loading
                ? "Running analysis…"
                : error
                  ? "Assessment failed"
                  : result
                    ? `Assessment ${result.assessment_id}`
                    : "Assessment"}
            </h2>
            {!loading && result && (
              <span
                className="mt-1 inline-block rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-900"
                data-testid="assess-not-validated"
              >
                NOT_VALIDATED · relative susceptibility ranking
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-meadow p-1.5 text-stone hover:text-bark"
            aria-label="Close"
            data-testid="assess-result-close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {locationLabel && (
          <p className="mt-3 font-mono text-[11px] text-stone" data-testid="assess-result-location">
            AOI / point: {locationLabel}
          </p>
        )}

        {loading && (
          <p className="mt-6 font-mono text-sm text-stone" data-testid="assess-result-loading">
            Acquiring features and running inference…
          </p>
        )}

        {!loading && error && (
          <div
            className="mt-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-xs text-amber-900"
            data-testid="assess-result-error"
          >
            {error}
          </div>
        )}

        {!loading && result && (
          <div className="mt-4 space-y-3" data-testid="assess-result-body">
            <p className="flex items-center gap-2 text-xs uppercase tracking-widest text-stone">
              <Gauge className="h-3.5 w-3.5" /> {result.model_version} · {result.request_id}
            </p>
            {result.is_fixture_checkpoint && (
              <p
                className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900"
                data-testid="assess-fixture-banner"
              >
                Research / fixture model
                {result.checkpoint_dataset_name
                  ? ` (${result.checkpoint_dataset_name})`
                  : ""}
                . Live pipeline verification only — not a scientifically validated
                production prediction.
              </p>
            )}
            {!result.domain_similarity_calibrated && (
              <p className="text-[11px] text-stone">
                Domain similarity is not calibrated. Confidence tiers do not reflect
                domain shift.
              </p>
            )}
            <p className="font-mono text-[10px] text-stone">
              checkpoint sha256 {result.checkpoint_sha256.slice(0, 16)}…
              {result.checkpoint_dataset_name
                ? ` · dataset ${result.checkpoint_dataset_name}@${
                    result.checkpoint_dataset_version ?? "?"
                  }`
                : ""}
            </p>
            {result.channel_schema_version && (
              <p className="font-mono text-[10px] text-stone" data-testid="assess-schema">
                schema {result.channel_schema_version}
                {result.channel_names?.length
                  ? ` · ${result.channel_names.length} channels`
                  : ""}
              </p>
            )}

            {result.hazard_profiles.map((profile, index) => {
              const score = scoreOf(profile);
              const allowed = scoreAllowed(profile);
              const showScore = allowed && score != null;
              return (
                <div
                  key={profile.hazard_type}
                  className="rounded-xl border border-meadow bg-mist px-4 py-3"
                  data-testid={`assess-hazard-${profile.hazard_type}`}
                >
                  <div className="flex items-center justify-between text-sm text-bark">
                    <span className="flex items-center gap-2">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ background: colorFor(index) }}
                      />
                      {profile.hazard_type}
                    </span>
                    <span className="font-mono text-xs" data-testid="assess-hazard-score">
                      {showScore ? `${(score * 100).toFixed(1)}%` : "score withheld"}
                    </span>
                  </div>
                  {(profile.gate_status || profile.status) && (
                    <p className={`mt-2 text-xs ${gateTone(profile.gate_status)}`}>
                      Gate: {profile.gate_status ?? "—"}
                      {profile.status ? ` · ${profile.status}` : ""}
                    </p>
                  )}
                  {!showScore && profile.reason && (
                    <p className="mt-1 text-xs text-stone" data-testid="assess-hazard-reason">
                      {profile.reason}
                    </p>
                  )}
                  {profile.confidence_tier && (
                    <p className={`mt-2 text-xs ${tierClass(profile.confidence_tier)}`}>
                      Model confidence: {profile.confidence_tier}
                      <span className="text-stone"> (not hazard severity)</span>
                      {result.domain_similarity_calibrated &&
                      profile.domain_similarity_score != null
                        ? ` · domain ${profile.domain_similarity_score.toFixed(3)}`
                        : " · domain uncalibrated"}
                    </p>
                  )}
                  {profile.credible_interval_80 && profile.credible_interval_95 && (
                    <p className="mt-1 font-mono text-[11px] text-stone">
                      80% CI [{profile.credible_interval_80[0].toFixed(3)},{" "}
                      {profile.credible_interval_80[1].toFixed(3)}] · 95% CI [
                      {profile.credible_interval_95[0].toFixed(3)},{" "}
                      {profile.credible_interval_95[1].toFixed(3)}]
                    </p>
                  )}
                  {profile.limitations && profile.limitations.length > 0 && (
                    <ul className="mt-1 list-disc pl-4 text-[11px] text-stone">
                      {profile.limitations.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}

            <p className="text-xs text-stone">{result.explanation}</p>
            {result.notes.length > 0 && (
              <details className="text-[11px] text-stone">
                <summary>Notes</summary>
                <ul className="mt-1 list-disc pl-4">
                  {result.notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}

        <div className="mt-5 flex flex-wrap gap-2">
          {!loading && result && (
            <button
              type="button"
              onClick={downloadReport}
              className="inline-flex items-center gap-1.5 rounded-lg border border-meadow px-3 py-2 text-xs text-bark"
              data-testid="assess-download-report"
            >
              <Download className="h-3.5 w-3.5" /> Download report
            </button>
          )}
          <button
            type="button"
            onClick={onViewMap}
            className="rounded-lg border border-leaf px-3 py-2 text-xs text-moss"
            data-testid="assess-view-map"
          >
            View on map
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-leaf px-3 py-2 text-xs font-medium text-chalk"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
