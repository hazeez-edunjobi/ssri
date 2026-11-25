"use client";

import { useEffect, useRef, useState } from "react";
import { Download, Gauge, X } from "lucide-react";
import {
  downloadAssessmentSpatialOutput,
  type AssessResponse,
  type HazardProfile,
  type ShellSettings,
} from "@/lib/api";
import {
  buildConditioningGroups,
  conditioningSampleCaption,
  geologicalContextLines,
} from "@/lib/conditioning";
import { ASSESSMENT_PREVIEW_LABEL } from "@/lib/activeModelStatus";
import { PresentationDemoProgress } from "@/components/PresentationDemoProgress";
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

function conditioningStatusClass(status: string): string {
  if (status === "available") return "border-leaf/40 bg-leaf/10 text-moss";
  if (status === "nodata") return "border-amber-300 bg-amber-50 text-amber-900";
  return "border-meadow bg-chalk text-stone";
}

type AssessResultModalProps = {
  open: boolean;
  loading: boolean;
  error: string | null;
  result: AssessResponse | null;
  /** Server SSRI_DEMO_MODE — show DEMONSTRATION labeling, not live inference. */
  presentationDemo?: boolean;
  locationLabel: string | null;
  point?: { latitude: number; longitude: number } | null;
  projectedPoint?: {
    crs: string;
    x: number;
    y: number;
    axis_order: string;
  } | null;
  settings?: ShellSettings | null;
  onCancelLoading?: () => void;
  onClose: () => void;
  onViewMap: () => void;
};

export function AssessResultModal({
  open,
  loading,
  error,
  result,
  presentationDemo = false,
  locationLabel,
  point,
  projectedPoint,
  settings,
  onCancelLoading,
  onClose,
  onViewMap,
}: AssessResultModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  const [geotiffBusy, setGeotiffBusy] = useState(false);
  const [geotiffError, setGeotiffError] = useState<string | null>(null);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);
  useEffect(() => {
    if (!open) {
      setGeotiffBusy(false);
      setGeotiffError(null);
    }
  }, [open]);

  // Escape dismisses the dialog and focus returns to whatever was focused
  // before it opened (usually the assessment inputs), so a real user is never
  // trapped behind the overlay even mid-assessment.
  useEffect(() => {
    if (!open) return;
    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseRef.current();
    };
    document.addEventListener("keydown", handleKey);
    panelRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", handleKey);
      previouslyFocused?.focus?.();
    };
  }, [open]);

  if (!open) return null;

  const downloadReport = () => {
    if (!result) return;
    const html = buildAssessmentReportHtml({
      result,
      locationLabel,
      point: point ?? null,
      projectedPoint: projectedPoint ?? null,
      settings: settings ?? null,
      presentationDemo,
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
      <div
        ref={panelRef}
        tabIndex={-1}
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-meadow bg-chalk p-5 shadow-soft outline-none"
      >
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
                ? presentationDemo
                  ? "Preparing assessment report…"
                  : "Running analysis…"
                : error
                  ? "Assessment failed"
                  : result
                    ? `Assessment ${result.assessment_id}`
                    : "Assessment"}
            </h2>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              {presentationDemo && (
                <span
                  className="inline-block font-mono text-[10px] uppercase tracking-widest text-leaf"
                  data-testid="assess-illustrative-badge"
                >
                  {ASSESSMENT_PREVIEW_LABEL}
                </span>
              )}
              {!loading && result && (
                <span
                  className="inline-block font-mono text-[10px] uppercase tracking-widest text-stone"
                  data-testid="assess-not-validated"
                >
                  NOT_VALIDATED · relative susceptibility ranking
                </span>
              )}
            </div>
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
        {result?.location_provenance?.submitted && (
          <p
            className="mt-1 font-mono text-[10px] text-stone"
            data-testid="assess-location-provenance"
          >
            API confirmed {result.location_provenance.submitted.latitude.toFixed(6)},{" "}
            {result.location_provenance.submitted.longitude.toFixed(6)} (
            {result.location_provenance.submitted_crs ?? "EPSG:4326"})
            {result.location_provenance.model_grid?.pixel_row != null &&
            result.location_provenance.model_grid?.pixel_col != null
              ? ` · grid r${result.location_provenance.model_grid.pixel_row} c${result.location_provenance.model_grid.pixel_col}`
              : ""}
            {result.location_provenance.model_grid?.crs
              ? ` · ${result.location_provenance.model_grid.crs}`
              : ""}
          </p>
        )}

        {loading && presentationDemo && (
          <PresentationDemoProgress
            active={loading}
            onCancel={onCancelLoading}
          />
        )}
        {loading && !presentationDemo && (
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
                  {showScore && score != null && (
                    <div
                      className="mt-2 h-1.5 overflow-hidden rounded-full bg-meadow/50"
                      data-testid="assess-hazard-bar"
                      aria-hidden
                    >
                      <div
                        className="h-full rounded-full transition-[width] duration-500"
                        style={{
                          width: `${Math.max(2, score * 100)}%`,
                          background: colorFor(index),
                        }}
                      />
                    </div>
                  )}
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
                  {profile.primary_drivers && profile.primary_drivers.length > 0 && (
                    <p className="mt-1 text-[11px] text-stone" data-testid="assess-hazard-drivers">
                      Contributing features: {profile.primary_drivers.join(", ")}
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

            <div className="space-y-3" data-testid="assess-conditioning">
              <div>
                <p className="text-xs uppercase tracking-widest text-stone">
                  Lineament &amp; overburden analytics
                </p>
                {conditioningSampleCaption(result.conditioning_features) && (
                  <p
                    className="mt-1 font-mono text-[10px] text-stone"
                    data-testid="assess-conditioning-sample"
                  >
                    {conditioningSampleCaption(result.conditioning_features)}
                  </p>
                )}
              </div>
              {geologicalContextLines(result.conditioning_features).length > 0 && (
                <div
                  className="rounded-xl border border-meadow bg-mist px-4 py-3"
                  data-testid="assess-geological-context"
                >
                  <p className="text-sm font-medium text-bark">
                    Geological context (magnetic interpretation)
                  </p>
                  <p className="mt-0.5 text-[11px] text-stone">
                    Publication-guided themes from intersecting TMI catalogue footprints.
                    Not confirmed faults, not overburden thickness, not hazard scores.
                    Status remains NOT_VALIDATED.
                  </p>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-bark">
                    {geologicalContextLines(result.conditioning_features).map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </div>
              )}
              {buildConditioningGroups(result.conditioning_features).map((group) => (
                <div
                  key={group.id}
                  className="rounded-xl border border-meadow bg-mist px-4 py-3"
                  data-testid={`assess-conditioning-group-${group.id}`}
                >
                  <p className="text-sm font-medium text-bark">{group.title}</p>
                  <p className="mt-0.5 text-[11px] text-stone">{group.subtitle}</p>
                  <ul className="mt-3 space-y-2">
                    {group.metrics.map((metric) => (
                      <li
                        key={metric.key}
                        className="rounded-lg border border-meadow/70 bg-chalk/60 px-3 py-2"
                        data-testid={`assess-conditioning-${metric.key}`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-xs font-medium text-bark">{metric.label}</span>
                          <span
                            className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${conditioningStatusClass(metric.status)}`}
                            data-testid={`assess-conditioning-status-${metric.key}`}
                          >
                            {metric.status}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-bark" data-testid={`assess-conditioning-value-${metric.key}`}>
                          {metric.valueText}
                          {metric.status === "available" && metric.unit
                            ? ` · ${metric.unit}`
                            : metric.status !== "available" && metric.unit
                              ? ` · expected unit: ${metric.unit}`
                              : ""}
                        </p>
                        <p
                          className="mt-1 font-mono text-[10px] text-stone"
                          data-testid={`assess-conditioning-usage-${metric.key}`}
                        >
                          In product: {metric.supportedInProduct ? "yes (schema v2)" : "no"}
                          {" · "}
                          At sample cell:{" "}
                          {metric.availableAtLocation
                            ? "measured"
                            : metric.status === "nodata"
                              ? "NoData"
                              : "not available"}
                          {" · "}
                          Used in this assessment:{" "}
                          {metric.usedInThisAssessment ? "yes" : "no"}
                        </p>
                        <p className="mt-1 text-[11px] text-stone">{metric.usageNote}</p>
                        {metric.reason ? (
                          <p className="mt-1 text-[11px] text-stone">{metric.reason}</p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              {result.conditioning_features?.notes?.[0] && (
                <p className="text-[11px] text-stone" data-testid="assess-conditioning-note">
                  {result.conditioning_features.notes[0]}
                </p>
              )}
              <p className="text-[11px] text-stone">
                Unavailable or NoData is never shown as zero. A layer only counts as used
                in this assessment when it is present in the feature stack with a finite
                sample value.
              </p>
            </div>

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
          {!loading &&
            result &&
            (result.spatial_output_hazard || result.spatial_output_url) && (
              <button
                type="button"
                disabled={geotiffBusy}
                data-testid="assess-download-geotiff"
                className="inline-flex items-center gap-1.5 rounded-lg border border-meadow px-3 py-2 text-xs text-bark disabled:opacity-60"
                onClick={() => {
                  if (!result?.assessment_id || geotiffBusy) return;
                  setGeotiffError(null);
                  setGeotiffBusy(true);
                  const hint = result.spatial_output_hazard
                    ? `${result.assessment_id}-${result.spatial_output_hazard}.tif`
                    : `${result.assessment_id}.tif`;
                  void downloadAssessmentSpatialOutput(result.assessment_id, hint)
                    .catch((err: Error) => {
                      setGeotiffError(err.message || "GeoTIFF download failed");
                    })
                    .finally(() => setGeotiffBusy(false));
                }}
              >
                <Download className="h-3.5 w-3.5" />{" "}
                {geotiffBusy
                  ? "Downloading GeoTIFF…"
                  : `Download GeoTIFF${
                      result.spatial_output_hazard
                        ? ` (${result.spatial_output_hazard})`
                        : ""
                    }`}
              </button>
            )}
          {!loading &&
            result &&
            !result.spatial_output_url &&
            !result.spatial_output_hazard && (
              <p
                className="w-full text-[11px] text-stone"
                data-testid="assess-geotiff-absent"
              >
                No GeoTIFF artefact is available for this assessment. Enable “Produce
                GeoTIFF” before running, or the assessment type may not generate spatial
                output (for example demo mode).
              </p>
            )}
          {geotiffError ? (
            <p
              className="w-full text-[11px] text-amber-900"
              data-testid="assess-geotiff-error"
              role="alert"
            >
              {geotiffError}
            </p>
          ) : null}
          {!loading &&
            result?.spatial_output_url?.startsWith("http") &&
            result.spatial_output_expires_seconds != null && (
              <p className="w-full text-[11px] text-stone" data-testid="assess-geotiff-expiry">
                Object-storage signed URL typically expires after{" "}
                {result.spatial_output_expires_seconds}s
                {result.spatial_output_crs ? ` · CRS ${result.spatial_output_crs}` : ""}
                {result.spatial_output_georef_quality
                  ? ` · georef ${result.spatial_output_georef_quality}`
                  : ""}
                . Prefer the authenticated Download GeoTIFF control for durable access.
              </p>
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
