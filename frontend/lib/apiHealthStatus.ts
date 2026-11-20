/**
 * Map health + readiness outcomes for the assessment dashboard indicator.
 * Liveness (/health) and readiness (/ready) must not be conflated.
 */

export type ApiHealthStatus = "checking" | "ok" | "degraded" | "down";

export function apiHealthLabel(status: ApiHealthStatus): string {
  switch (status) {
    case "checking":
      return "checking…";
    case "ok":
      return "reachable · ready";
    case "degraded":
      return "reachable · infrastructure not ready";
    case "down":
      return "unreachable";
  }
}

export function resolveApiHealthStatus(args: {
  healthOk: boolean;
  readyOk: boolean;
}): Exclude<ApiHealthStatus, "checking"> {
  if (!args.healthOk) return "down";
  if (!args.readyOk) return "degraded";
  return "ok";
}
