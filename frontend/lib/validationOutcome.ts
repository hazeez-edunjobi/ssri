/**
 * Map backend validation overall codes to client-facing gate labels.
 * PASS → Ready, WARN → Ready with warnings, FAIL → Blocked.
 */

export type ClientValidationOutcome = "Ready" | "Ready with warnings" | "Blocked" | "Unknown";

export function clientValidationOutcome(
  overall: string | null | undefined,
): ClientValidationOutcome {
  const code = String(overall || "").toUpperCase();
  if (code === "PASS") return "Ready";
  if (code === "WARN") return "Ready with warnings";
  if (code === "FAIL") return "Blocked";
  return "Unknown";
}

export function validationOutcomeTone(
  outcome: ClientValidationOutcome,
): "ok" | "warn" | "block" | "neutral" {
  if (outcome === "Ready") return "ok";
  if (outcome === "Ready with warnings") return "warn";
  if (outcome === "Blocked") return "block";
  return "neutral";
}
