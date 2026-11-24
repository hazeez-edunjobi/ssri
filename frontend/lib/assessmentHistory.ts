/**
 * Presentation helpers for GET /api/v1/assess/history.
 * Do not invent missing API fields.
 */

import type { AssessmentHistoryHazard, AssessmentHistoryItem } from "./api";

export function formatHistoryScore(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export function formatHistoryCoords(item: AssessmentHistoryItem): string {
  if (
    item.latitude == null ||
    item.longitude == null ||
    !Number.isFinite(item.latitude) ||
    !Number.isFinite(item.longitude)
  ) {
    return "Location not stored";
  }
  return `${item.latitude.toFixed(6)}, ${item.longitude.toFixed(6)}`;
}

export function dashboardHrefForHistory(item: AssessmentHistoryItem): string | null {
  if (
    item.latitude == null ||
    item.longitude == null ||
    !Number.isFinite(item.latitude) ||
    !Number.isFinite(item.longitude)
  ) {
    return null;
  }
  const params = new URLSearchParams({
    lat: String(item.latitude),
    lon: String(item.longitude),
  });
  return `/dashboard?${params.toString()}`;
}

export function formatHazardLine(hazard: AssessmentHistoryHazard): string {
  const name = hazard.hazard_type || "hazard";
  const score = formatHistoryScore(hazard.point_estimate ?? null);
  const tier =
    typeof hazard.confidence_tier === "string" && hazard.confidence_tier.trim()
      ? ` · ${hazard.confidence_tier}`
      : "";
  return `${name}: ${score}${tier}`;
}

export function historyEmptyMessage(total: number | undefined): string {
  if (total === 0 || total == null) {
    return "No persisted assessments yet. Run an assessment from the map to create history.";
  }
  return "No assessments on this page.";
}
