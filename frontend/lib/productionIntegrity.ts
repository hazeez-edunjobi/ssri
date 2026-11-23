/**
 * Production data-integrity gates for the client-facing app.
 *
 * Presentation / Assessment Preview UI must never activate in a production
 * Next.js build. Local walkthroughs require an explicit opt-in flag in
 * addition to server SSRI_DEMO_MODE.
 */

/**
 * True only when the browser build is allowed to surface presentation-demo UI.
 * Production builds always return false (no silent activation).
 */
export function clientAllowsPresentationDemo(): boolean {
  if (process.env.NODE_ENV === "production") {
    return false;
  }
  const flag = process.env.NEXT_PUBLIC_SSRI_ALLOW_PRESENTATION_DEMO?.trim().toLowerCase();
  return flag === "1" || flag === "true" || flag === "yes" || flag === "on";
}

/**
 * Local headed-acceptance session bypass must never ship in production builds.
 */
export function clientAllowsLocalAcceptanceSession(): boolean {
  if (process.env.NODE_ENV === "production") {
    return false;
  }
  const flag = process.env.NEXT_PUBLIC_SSRI_LOCAL_ACCEPTANCE_SESSION?.trim().toLowerCase();
  return flag === "1" || flag === "true" || flag === "yes" || flag === "on";
}

/**
 * Combine server readiness with client production gates.
 * A misconfigured production API with demo_mode=true must not enable fake UI.
 */
export function resolvePresentationDemoActive(serverDemoMode: boolean | undefined): boolean {
  return Boolean(serverDemoMode) && clientAllowsPresentationDemo();
}

/** Operator-facing notice when a production client sees a demo-enabled API. */
export function demoMisconfigurationNotice(
  serverDemoMode: boolean | undefined,
): string | null {
  if (!serverDemoMode) return null;
  if (clientAllowsPresentationDemo()) return null;
  return (
    "The API reports presentation demo mode, but this client build will not " +
    "display Assessment Preview or catalogue scores. Set SSRI_DEMO_MODE=false " +
    "on the API for production integrity."
  );
}
