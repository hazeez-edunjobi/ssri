/**
 * Client-side operator / admin access helpers.
 * Backend RBAC remains authoritative. This only gates UI surfaces.
 *
 * Platform profiles expose `user` | `admin` only. ADMIN maps to full Stage 2.5
 * operator permissions server-side. Machine operators use NEXT_PUBLIC_SSRI_API_KEY.
 */

export type PlatformProfileRole = "user" | "admin" | string;

export function configuredOperatorApiKey(
  env: NodeJS.ProcessEnv | Record<string, string | undefined> = process.env,
): string | null {
  const key = env.NEXT_PUBLIC_SSRI_API_KEY?.trim();
  return key ? key : null;
}

export function canAccessOperatorUi(input: {
  localAcceptance: boolean;
  hasOperatorApiKey: boolean;
  hasSession: boolean;
  platformRole: PlatformProfileRole | null;
}): boolean {
  if (input.localAcceptance) return true;
  if (input.hasOperatorApiKey) return true;
  if (input.hasSession && input.platformRole === "admin") return true;
  return false;
}

export function canAccessAdminUi(input: {
  localAcceptance: boolean;
  hasSession: boolean;
  platformRole: PlatformProfileRole | null;
}): boolean {
  // Local acceptance is not an admin role substitute.
  if (input.localAcceptance) return false;
  return input.hasSession && input.platformRole === "admin";
}

export function operatorAccessDeniedReason(input: {
  localAcceptance: boolean;
  hasOperatorApiKey: boolean;
  hasSession: boolean;
  platformRole: PlatformProfileRole | null;
}): string | null {
  if (canAccessOperatorUi(input)) return null;
  if (!input.hasSession && !input.hasOperatorApiKey) {
    return "Sign in, or configure an operator API key (NEXT_PUBLIC_SSRI_API_KEY), to open operator tools.";
  }
  return (
    "Operator tools require a platform admin profile or a configured operator API key. " +
    "Ordinary user accounts can run assessments but cannot open this interface. " +
    "API permission checks still apply after the UI opens."
  );
}
