"use client";

import { Gauge, X } from "lucide-react";
import type { AssessResponse, HazardProfile } from "@/lib/api";

const HAZARD_COLORS: Record<string, string> = {
  subsidence: "#2D6A4F",
  landslide: "#9C6644",
  sinkhole: "#40916C",
};

function tierClass(tier: string): string {
  if (tier.includes("Extrapolation")) return "text-amber-800";
  if (tier === "High") return "text-emerald";
  if (tier === "Moderate") return "text-leaf";
  return "text-stone";
}

type AssessResultModalProps = {
  open: boolean;
  loading: boolean;
  error: string | null;
  result: AssessResponse | null;
  locationLabel: string | null;
  onClose: () => void;
  onViewMap: () => void;
};

export function AssessResultModal({
  open,
  loading,
  error,
  result,
  locationLabel,
  onClose,
  onViewMap,
}: AssessResultModalProps) {
  if (!open) return null;

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

            {result.hazard_profiles.map((profile: HazardProfile) => (
              <div
                key={profile.hazard_type}
                className="rounded-xl border border-meadow bg-mist px-4 py-3"
                data-testid={`assess-hazard-${profile.hazard_type}`}
              >
                <div className="flex items-center justify-between text-sm text-bark">
                  <span className="flex items-center gap-2">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{
                        background: HAZARD_COLORS[profile.hazard_type] ?? "#3EA6FF",
                      }}
                    />
                    {profile.hazard_type}
                  </span>
                  <span className="font-mono text-xs">
                    {(profile.susceptibility_score * 100).toFixed(1)}%
                  </span>
                </div>
                <p className={`mt-2 text-xs ${tierClass(profile.confidence_tier)}`}>
                  Model confidence: {profile.confidence_tier}
                  <span className="text-stone"> (not hazard severity)</span>
                  {result.domain_similarity_calibrated &&
                  profile.domain_similarity_score != null
                    ? ` · domain ${profile.domain_similarity_score.toFixed(3)}`
                    : " · domain uncalibrated"}
                </p>
                <p className="mt-1 font-mono text-[11px] text-stone">
                  80% CI [{profile.credible_interval_80[0].toFixed(3)},{" "}
                  {profile.credible_interval_80[1].toFixed(3)}] · 95% CI [
                  {profile.credible_interval_95[0].toFixed(3)},{" "}
                  {profile.credible_interval_95[1].toFixed(3)}]
                </p>
              </div>
            ))}

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
