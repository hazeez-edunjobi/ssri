/**
 * Build a self-contained HTML assessment report from an API response.
 *
 * Wording is fixed: scores are "relative susceptibility rankings", never risk,
 * probability, detection or validation. Status stays NOT_VALIDATED. Everything
 * shown here is copied from the API response; nothing is inferred or fabricated.
 */
import type { AssessResponse, ShellSettings } from "./api";

export type ReportInput = {
  result: AssessResponse;
  locationLabel: string | null;
  point?: { latitude: number; longitude: number } | null;
  settings?: ShellSettings | null;
  generatedAt?: Date;
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

export function buildAssessmentReportHtml(input: ReportInput): string {
  const { result, locationLabel, point, settings } = input;
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
    settings?.block_size_deg != null
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
  <h1>SSRI assessment report</h1>
  <p class="muted">Assessment ${escapeHtml(result.assessment_id)} · generated ${escapeHtml(generatedAt)}</p>

  <h2>Location</h2>
  <dl>
    <dt>AOI / point</dt><dd>${escapeHtml(locationLabel ?? "not provided")}</dd>
    <dt>Latitude (WGS84, °N)</dt><dd>${point ? point.latitude.toFixed(6) : "not provided"}</dd>
    <dt>Longitude (WGS84, °E)</dt><dd>${point ? point.longitude.toFixed(6) : "not provided"}</dd>
    <dt>Training CRS</dt><dd>${
      noteValue(notes, "assess_crs") ?? "not reported by the API"
    }</dd>
  </dl>

  <h2>Checkpoint</h2>
  <dl>
    <dt>Assessment id</dt><dd>${escapeHtml(result.assessment_id)}</dd>
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

  <h2>Evaluation summary</h2>
  <p class="muted">${
    noteValue(notes, "evaluation")
      ? escapeHtml(noteValue(notes, "evaluation"))
      : "Not attached to this point assessment. AUC with confidence interval, delta vs slope baseline, the per-block table and seeds live in the model's evaluation report (release-shell models/&lt;id&gt;/evaluation)."
  }</p>

  <h2>Limitations</h2>
  <ul>${localEvidence.map((l) => `<li>${escapeHtml(l)}</li>`).join("") || "<li>None reported.</li>"}</ul>

  <h2>Notes</h2>
  <ul>${notes.map((n) => `<li>${escapeHtml(n)}</li>`).join("")}</ul>

  <p class="muted">${escapeHtml(result.explanation)}</p>
  <p class="muted">scientific_validation_status: NOT_VALIDATED · score_framing: relative susceptibility ranking · request ${escapeHtml(result.request_id)}</p>
</body>
</html>`;
}
