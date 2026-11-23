/**
 * Local headed-browser acceptance only.
 * Never active in production builds. Requires explicit opt-in env flag.
 */

export function localAcceptanceSessionAllowed(): boolean {
  if (process.env.NODE_ENV === "production") return false;
  const flag = process.env.NEXT_PUBLIC_SSRI_LOCAL_ACCEPTANCE_SESSION?.trim().toLowerCase();
  return flag === "1" || flag === "true" || flag === "yes" || flag === "on";
}

export const LOCAL_ACCEPTANCE_EMAIL = "local-acceptance@ssri.local";
