/**
 * Build a self-contained HTML assessment report from an API response.
 *
 * Wording is fixed: scores are "relative susceptibility rankings", never risk,
 * probability, detection or validation. Status stays NOT_VALIDATED. Everything
 * shown here is copied from the API response; nothing is inferred or fabricated.
 */
import type { AssessResponse, AssessmentEvaluationSummary, ShellSettings } from "./api";
import {
  buildConditioningGroups,
  conditioningSampleCaption,
} from "./conditioning.ts";

export type ReportInput = {
  result: AssessResponse;
  locationLabel: string | null;
  point?: { latitude: number; longitude: number } | null;
  projectedPoint?: {
    crs: string;
    x: number;
    y: number;
    axis_order: string;
  } | null;
  settings?: ShellSettings | null;
  generatedAt?: Date;
  /** When true, label the report as demonstration / sample data. */
  presentationDemo?: boolean;
};

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function noteValue(notes: string[], key: string): string | null {
  const prefix = `${key}=`;
  const found = notes.find((n) => n.startsWith(prefix));
  return found ? found.slice(prefix.length) : null;
}

/**
 * Find *affirmative* risk / probability / detection wording in a report or API
 * string. The backend mandates a negation disclaimer ("scores are relative
 * susceptibility rankings, not probabilities or risk estimates", see
 * `release_shell/flags.py`) which the report echoes verbatim, so the negation
 * phrases are stripped before matching. Any remaining hit is a real claim.
 *
 * Returns the offending substrings (empty array = the text is clean).
 */
export function findAffirmativeRiskClaims(text: string): string[] {
  const withoutNegations = text
    .toLowerCase()
    .replace(/not\s+probabilit(?:y|ies)\s+or\s+risk(?:\s+estimates)?\.?/g, "");
  return withoutNegations.match(/\b(risk|probabilit(?:y|ies)|detection)\b/g) ?? [];
}

function isScoreAllowed(profile: {
  score?: number | null;
  susceptibility_score?: number;
  gate_status?: string | null;
  preview_unevaluated_scores?: boolean;
}): boolean {
  const gate = profile.gate_status;
  if (gate == null) return true; // classic (flag OFF) response
  if (gate === "evaluated") return true;
  return Boolean(profile.preview_unevaluated_scores);
}

function scoreOf(profile: {
  score?: number | null;
  susceptibility_score?: number;
}): number | null {
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

function num(value: number | null | undefined, digits = 3): string {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(digits)
    : "—";
}

function ci95(ci: [number, number] | null | undefined): string {
  if (!ci || ci.length !== 2) return "—";
  return `[${num(ci[0])}, ${num(ci[1])}]`;
}

function evaluationSection(summary: AssessmentEvaluationSummary | null | undefined): string {
  if (!summary) {
    return `<p class="muted">Not attached to this point assessment. AUC with confidence interval, delta vs slope baseline, the per-block table and seeds live in the model's held-out evaluation (release-shell models/&lt;id&gt;/evaluation).</p>`;
  }
  const seedLabel =
    summary.seeds && summary.seeds.length > 0
      ? summary.seeds.join(", ")
      : "not reported";
  const rows = Object.entries(summary.hazards ?? {})
    .map(([name, h]) => {
      const auc =
        h.roc_auc == null ? "—" : `${num(h.roc_auc)} ${ci95(h.roc_auc_ci95)}`;
      const delta =
        h.delta_auc_vs_slope == null
          ? "—"
          : `${h.delta_auc_vs_slope >= 0 ? "+" : ""}${num(h.delta_auc_vs_slope)} ${ci95(h.delta_auc_ci95)}`;
      const frac =
        h.frac_held_out_blocks_auc_gt_0_5 == null
          ? "—"
          : `${(h.frac_held_out_blocks_auc_gt_0_5 * 100).toFixed(0)}%`;
      const seedAucs = Object.entries(h.seed_aucs ?? {})
        .map(([s, v]) => `seed ${s}: ${num(v)}`)
        .join("; ");
      return `<tr>
        <td>${escapeHtml(name)}</td>
        <td>${escapeHtml(h.gate_status ?? "—")}</td>
        <td>${escapeHtml(auc)}</td>
        <td>${escapeHtml(delta)}</td>
        <td>${escapeHtml(frac)}</td>
        <td>${escapeHtml(seedAucs || "—")}</td>
      </tr>`;
    })
    .join("");

  const blockTables = Object.entries(summary.hazards ?? {})
    .filter(([, h]) => h.per_block && Object.keys(h.per_block).length > 0)
    .map(([name, h]) => {
      const blockRows = Object.entries(h.per_block ?? {})
        .map(
          ([block, entry]) =>
            `<tr><td>${escapeHtml(block)}</td><td>${escapeHtml(entry.n ?? "—")}</td><td>${escapeHtml(entry.n_pos ?? "—")}</td><td>${escapeHtml(num(entry.roc_auc))}</td></tr>`,
        )
        .join("");
      return `<h3>Per-block held-out AUC — ${escapeHtml(name)}</h3>
      <table><thead><tr><th>Block</th><th>n</th><th>n positive</th><th>AUC</th></tr></thead><tbody>${blockRows}</tbody></table>`;
    })
    .join("");

  return `<p class="muted">Relative susceptibility rankings only. Status NOT_VALIDATED. Seeds: ${escapeHtml(seedLabel)}. Split policy: ${escapeHtml(summary.split_policy ?? "not reported")}. Representative seed: ${escapeHtml(Object.values(summary.hazards ?? {})[0]?.representative_seed ?? "—")}.</p>
  <table>
    <thead><tr><th>Hazard</th><th>Gate</th><th>ROC AUC (95% CI)</th><th>ΔAUC vs slope (95% CI)</th><th>Blocks AUC&gt;0.5</th><th>Per-seed AUC</th></tr></thead>
    <tbody>${rows || `<tr><td colspan="6">No evaluation rows.</td></tr>`}</tbody>
  </table>
  ${blockTables}`;
}

export function buildAssessmentReportHtml(input: ReportInput): string {
  const { result, locationLabel, point, projectedPoint, settings, presentationDemo } =
    input;
  const generatedAt = (input.generatedAt ?? new Date()).toISOString();
  const notes = result.notes ?? [];
  const dataHash = noteValue(notes, "data_hash");
  const localEvidence = [
    ...notes.filter((n) => n.startsWith("limitation=")).map((n) => n.slice(11)),
    ...(result.hazard_profiles ?? []).flatMap((p) => p.limitations ?? []),
  ].filter((v, i, all) => all.indexOf(v) === i);

  const hasLocalEvidenceOnly = localEvidence.some((l) =>
    /local evidence/i.test(l),
  );

  const channelList =
    result.channel_names && result.channel_names.length > 0
      ? result.channel_names.join(", ")
      : "not reported by the API";

  const hazardRows = (result.hazard_profiles ?? [])
    .map((profile) => {
      const allowed = isScoreAllowed(profile);
      const score = scoreOf(profile);
      const scoreCell =
        allowed && score != null
          ? `${(score * 100).toFixed(1)}% (relative susceptibility ranking)`
          : "withheld";
      const status = profile.status ?? profile.gate_status ?? "unknown";
      return `<tr>
        <td>${escapeHtml(profile.hazard_type)}</td>
        <td>${escapeHtml(profile.gate_status ?? "—")}</td>
        <td>${escapeHtml(status)}</td>
        <td>${escapeHtml(scoreCell)}</td>
        <td>${escapeHtml(profile.reason ?? "")}</td>
      </tr>`;
    })
    .join("");

  const blockSize =
    noteValue(notes, "block_size_deg") != null
      ? `${noteValue(notes, "block_size_deg")}° (checkpoint)`
      : settings?.block_size_deg != null
        ? `${settings.block_size_deg}° (override)`
        : settings
          ? `${settings.default_block_size_deg}° (default)`
          : "not reported";

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>SSRI assessment ${escapeHtml(result.assessment_id)}</title>
<style>
  body { font-family: Poppins, system-ui, sans-serif; color: #1f2a24; margin: 0; padding: 32px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  h2 { font-size: 14px; margin: 24px 0 6px; text-transform: uppercase; letter-spacing: .08em; color: #4a5a50; }
  .badge { display: inline-block; border: 1px solid #b45309; background: #fffbeb; color: #92400e;
           border-radius: 999px; padding: 2px 10px; font-size: 11px; margin-bottom: 8px; }
  dl { display: grid; grid-template-columns: 220px 1fr; gap: 4px 16px; margin: 0; font-size: 13px; }
  dt { color: #4a5a50; }
  dd { margin: 0; font-family: ui-monospace, monospace; word-break: break-all; }
  table { border-collapse: collapse; width: 100%; font-size: 12px; }
  th, td { border: 1px solid #d7e0da; padding: 6px 8px; text-align: left; vertical-align: top; }
  th { background: #f3f7f4; }
  ul { font-size: 12px; line-height: 1.5; }
  .muted { color: #6b7a71; font-size: 11px; }
</style>
</head>
<body>
  <span class="badge">NOT_VALIDATED · relative susceptibility ranking</span>
  ${
    presentationDemo
      ? `<p class="badge" style="letter-spacing:.08em;text-transform:uppercase;font-size:10px;color:#2D6A4F;background:transparent;border:0;padding:0;">Assessment Preview</p>
  <p class="muted">Methodology: Assessment Preview catalogue scenario — not live model inference or field-verified measurements for the named location.</p>`
      : ""
  }
  <h1>SSRI assessment report</h1>
  <p class="muted">Assessment ${escapeHtml(result.assessment_id)} · generated ${escapeHtml(generatedAt)}</p>

  <h2>Location</h2>
  <dl>
    <dt>AOI / point</dt><dd>${escapeHtml(locationLabel ?? "not provided")}</dd>
    <dt>Latitude (WGS84, °N)</dt><dd>${point ? point.latitude.toFixed(6) : "not provided"}</dd>
    <dt>Longitude (WGS84, °E)</dt><dd>${point ? point.longitude.toFixed(6) : "not provided"}</dd>
    <dt>Training CRS</dt><dd>${escapeHtml(noteValue(notes, "assess_crs") ?? "not reported by the API")}</dd>
    <dt>Location in training CRS</dt><dd>${
      projectedPoint
        ? `${escapeHtml(projectedPoint.crs)}: x ${projectedPoint.x.toFixed(3)}, y ${projectedPoint.y.toFixed(3)} (${escapeHtml(projectedPoint.axis_order)})`
        : "not provided"
    }</dd>
  </dl>

  <h2>Checkpoint</h2>
  <dl>
    <dt>Assessment id</dt><dd>${escapeHtml(result.assessment_id)}</dd>
    <dt>Checkpoint id</dt><dd>${escapeHtml(result.checkpoint_id ?? "not reported by the API")}</dd>
    <dt>Model version</dt><dd>${escapeHtml(result.model_version)}</dd>
    <dt>Checkpoint sha256</dt><dd>${escapeHtml(result.checkpoint_sha256)}</dd>
    <dt>Dataset name</dt><dd>${escapeHtml(result.checkpoint_dataset_name ?? "—")}</dd>
    <dt>Dataset version</dt><dd>${escapeHtml(result.checkpoint_dataset_version ?? "—")}</dd>
    <dt>Dataset hash</dt><dd>${escapeHtml(dataHash ?? "not reported by the API")}</dd>
    <dt>Fixture checkpoint</dt><dd>${result.is_fixture_checkpoint ? "yes" : "no"}</dd>
  </dl>

  <h2>Channel schema</h2>
  <dl>
    <dt>Schema version</dt><dd>${escapeHtml(result.channel_schema_version ?? "not reported by the API")}</dd>
    <dt>Ordered channels</dt><dd>${escapeHtml(channelList)}</dd>
    <dt>Block size</dt><dd>${escapeHtml(blockSize)}</dd>
    <dt>Buffer</dt><dd>${settings ? `${settings.buffer_km} km` : "not reported"}</dd>
    <dt>Split policy</dt><dd>${escapeHtml(noteValue(notes, "split_policy") ?? "not reported by the API")}</dd>
  </dl>
  ${hasLocalEvidenceOnly ? "<p><strong>Local evidence only:</strong> this model applies only inside the uploaded training geography.</p>" : ""}

  <h2>Per-hazard status</h2>
  <table>
    <thead><tr><th>Hazard</th><th>Gate</th><th>Status</th><th>Ranking</th><th>Reason</th></tr></thead>
    <tbody>${hazardRows || `<tr><td colspan="5">No hazard profiles returned.</td></tr>`}</tbody>
  </table>
  <p class="muted">Rankings appear only where the gate status is evaluated (or an unevaluated preview is explicitly enabled).</p>

  <h2>Lineament &amp; overburden analytics</h2>
  ${buildConditioningGroups(result.conditioning_features)
    .map(
      (group) => `
  <h3>${escapeHtml(group.title)}</h3>
  <p class="muted">${escapeHtml(group.subtitle)}</p>
  <dl>
    ${group.metrics
      .map((metric) => {
        const detail =
          metric.status === "available"
            ? `${metric.valueText}${metric.unit ? ` ${metric.unit}` : ""}`
            : `${metric.valueText}${metric.unit ? ` (expected unit: ${metric.unit})` : ""}`;
        const usage =
          `In product: ${metric.supportedInProduct ? "yes" : "no"}; ` +
          `at sample cell: ${
            metric.availableAtLocation
              ? "measured"
              : metric.status === "nodata"
                ? "NoData"
                : "not available"
          }; ` +
          `used in this assessment: ${metric.usedInThisAssessment ? "yes" : "no"}. ` +
          metric.usageNote;
        return `<dt>${escapeHtml(metric.label)} <span class="muted">(${escapeHtml(metric.key)} · ${escapeHtml(metric.status)})</span></dt><dd>${escapeHtml(detail)}${
          metric.reason ? ` — ${escapeHtml(metric.reason)}` : ""
        }<br/><span class="muted">${escapeHtml(usage)}</span></dd>`;
      })
      .join("")}
  </dl>`,
    )
    .join("")}
  ${
    conditioningSampleCaption(result.conditioning_features)
      ? `<p class="muted">${escapeHtml(conditioningSampleCaption(result.conditioning_features) || "")}</p>`
      : ""
  }

  <h2>Spatial output</h2>
  <dl>
    <dt>GeoTIFF URL</dt><dd>${escapeHtml(result.spatial_output_url ?? "not produced")}</dd>
    <dt>Hazard band</dt><dd>${escapeHtml(result.spatial_output_hazard ?? "—")}</dd>
    <dt>CRS</dt><dd>${escapeHtml(result.spatial_output_crs ?? "—")}</dd>
    <dt>Georef quality</dt><dd>${escapeHtml(result.spatial_output_georef_quality ?? "—")}</dd>
    <dt>Signed URL TTL (s)</dt><dd>${
      result.spatial_output_expires_seconds != null
        ? String(result.spatial_output_expires_seconds)
        : "—"
    }</dd>
  </dl>

  <h2>Evaluation summary</h2>
  ${evaluationSection(result.evaluation_summary)}

  <h2>Limitations</h2>
  <ul>${localEvidence.map((l) => `<li>${escapeHtml(l)}</li>`).join("") || "<li>None reported.</li>"}</ul>

  <h2>Notes</h2>
  <ul>${notes.map((n) => `<li>${escapeHtml(n)}</li>`).join("")}</ul>

  <p class="muted">${escapeHtml(result.explanation)}</p>
  <p class="muted">scientific_validation_status: NOT_VALIDATED · score_framing: relative susceptibility ranking · request ${escapeHtml(result.request_id)}</p>
</body>
</html>`;
}
