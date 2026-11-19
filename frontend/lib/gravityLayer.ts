/**
 * Client presentation helpers for the optional gravity map overlay.
 * Gravity visualization is not required to run an assessment.
 */

export type GravityLoadState = "loading" | "ready" | "unavailable";

export function gravityLoadState(args: {
  loaded: boolean;
  error: string | null;
}): GravityLoadState {
  if (args.loaded) return "ready";
  if (args.error) return "unavailable";
  return "loading";
}

/**
 * Turn API/transport errors into client-facing copy without inventing data.
 */
export function formatGravityUnavailableMessage(raw: string | null | undefined): string {
  const text = (raw || "").trim();
  if (!text) {
    return "Optional gravity map overlay is unavailable for this deployment.";
  }
  const lower = text.toLowerCase();
  if (
    lower.includes("gravity_data_path") ||
    lower.includes("geotiff not found") ||
    lower.includes("404")
  ) {
    return (
      "Optional gravity map overlay is unavailable: the regional Bouguer GeoTIFF " +
      "is not mounted on this API host. Assessment can still run without this overlay."
    );
  }
  if (lower.startsWith("could not load the gravity layer:")) {
    return formatGravityUnavailableMessage(text.replace(/^could not load the gravity layer:\s*/i, ""));
  }
  return `Optional gravity map overlay is unavailable: ${text}`;
}

export function gravityVisibilityLabel(state: GravityLoadState, visible: boolean): string {
  if (state !== "ready") return "Not on map";
  return visible ? "Shown on map" : "Hidden on map";
}
