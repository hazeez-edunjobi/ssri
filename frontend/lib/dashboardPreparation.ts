/**
 * Dashboard preparation presentation driven by real client async operations.
 * Stages advance only from observed application state — never from timers.
 */

import type { ActiveModelView } from "./activeModelStatus";
import type { ApiHealthStatus } from "./apiHealthStatus";

export type PrepStageId =
  | "workspace"
  | "session"
  | "api_connectivity"
  | "backend_readiness"
  | "active_model"
  | "hazard_categories"
  | "map_environment"
  | "geophysics_layer"
  | "geological_catalogue";

export type PrepStageStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "failed"
  | "skipped";

export type PrepStageView = {
  id: PrepStageId;
  label: string;
  description: string;
  status: PrepStageStatus;
  detail: string | null;
  /** When true, readiness waits for a terminal status (completed/failed/skipped). */
  blocking: boolean;
};

export type OptionalLayerStatus = "pending" | "in_progress" | "available" | "unavailable";

export type HazardRegistryStatus = "pending" | "in_progress" | "loaded" | "fallback";

export type DashboardPreparationInput = {
  sessionEmail: string | null;
  apiStatus: ApiHealthStatus;
  modelStatus: ActiveModelView;
  hazardRegistry: HazardRegistryStatus;
  hazards: readonly string[];
  mapLoaded: boolean;
  mapFailed?: boolean;
  geophysics: OptionalLayerStatus;
  geological: OptionalLayerStatus;
  geologicalCount: number;
  registryReadyDetail?: string | null;
};

export type ConnectedSystemsView = {
  api: string;
  model: string;
  hazards: string;
  geophysics: string;
  geological: string;
  workspace: string;
};

export type DashboardPreparationPresentation = {
  title: string;
  description: string;
  stages: PrepStageView[];
  connected: ConnectedSystemsView;
  /** All blocking stages have left pending/in_progress. */
  ready: boolean;
  /** Terminal failure that should surface a retry affordance. */
  blockingError: string | null;
};

const STAGE_META: Record<
  PrepStageId,
  { label: string; description: string; blocking: boolean }
> = {
  workspace: {
    label: "Initialising SSRI workspace",
    description: "Opening the assessment workspace shell.",
    blocking: true,
  },
  session: {
    label: "Verifying authentication session",
    description: "Confirming the signed-in workspace identity.",
    blocking: true,
  },
  api_connectivity: {
    label: "Checking API connectivity",
    description: "Calling the SSRI health endpoint.",
    blocking: true,
  },
  backend_readiness: {
    label: "Verifying backend readiness",
    description: "Confirming infrastructure readiness for assessments.",
    blocking: true,
  },
  active_model: {
    label: "Checking model availability",
    description: "Reading the promoted Stage 2.5 production checkpoint.",
    blocking: true,
  },
  hazard_categories: {
    label: "Loading available hazard categories",
    description: "Reading the release-shell hazard registry when available.",
    blocking: false,
  },
  map_environment: {
    label: "Initialising the assessment map",
    description: "Loading MapLibre and the basemap style.",
    blocking: true,
  },
  geophysics_layer: {
    label: "Connecting geophysical data",
    description: "Loading the optional gravity overlay for the product region.",
    blocking: false,
  },
  geological_catalogue: {
    label: "Connecting geological data sources",
    description: "Loading optional geological dataset footprints.",
    blocking: false,
  },
};

function stage(
  id: PrepStageId,
  status: PrepStageStatus,
  detail: string | null = null,
): PrepStageView {
  const meta = STAGE_META[id];
  return {
    id,
    label: meta.label,
    description: meta.description,
    status,
    detail,
    blocking: meta.blocking,
  };
}

function modelDetail(model: ActiveModelView): string {
  if (model.kind === "loading") return "Checking promoted checkpoint…";
  if (model.kind === "available") {
    return model.label ?? model.modelId ?? "Promoted Stage 2.5 model available";
  }
  if (model.kind === "missing") return "No promoted Stage 2.5 model is available";
  if (model.kind === "unauthorized") return "Sign-in required to read model status";
  if (model.kind === "forbidden") return "Account cannot read promoted model status";
  return "Could not verify promoted model status";
}

/**
 * Map live dashboard async state into an honest preparation presentation.
 */
export function presentDashboardPreparation(
  input: DashboardPreparationInput,
): DashboardPreparationPresentation {
  const sessionOk = Boolean(input.sessionEmail);

  const apiConnectivity: PrepStageView =
    input.apiStatus === "checking"
      ? stage("api_connectivity", "in_progress")
      : input.apiStatus === "down"
        ? stage("api_connectivity", "failed", "SSRI API did not respond")
        : stage(
            "api_connectivity",
            "completed",
            input.apiStatus === "ok"
              ? "API reachable"
              : "API reachable (readiness degraded)",
          );

  const backendReadiness: PrepStageView =
    input.apiStatus === "checking"
      ? stage("backend_readiness", "pending")
      : input.apiStatus === "down"
        ? stage("backend_readiness", "failed", "Skipped — API unreachable")
        : input.apiStatus === "degraded"
          ? stage(
              "backend_readiness",
              "failed",
              "Backend readiness check failed (Redis/queue or dependent services)",
            )
          : stage(
              "backend_readiness",
              "completed",
              input.registryReadyDetail?.trim() || "Backend reported ready",
            );

  const activeModel: PrepStageView =
    input.modelStatus.kind === "loading"
      ? stage("active_model", "in_progress")
      : input.modelStatus.kind === "available"
        ? stage("active_model", "completed", modelDetail(input.modelStatus))
        : input.modelStatus.kind === "missing"
          ? stage("active_model", "failed", modelDetail(input.modelStatus))
          : stage("active_model", "failed", modelDetail(input.modelStatus));

  const hazards: PrepStageView =
    input.hazardRegistry === "pending" || input.hazardRegistry === "in_progress"
      ? stage(
          "hazard_categories",
          input.hazardRegistry === "pending" ? "pending" : "in_progress",
        )
      : input.hazardRegistry === "loaded"
        ? stage(
            "hazard_categories",
            "completed",
            input.hazards.length
              ? input.hazards.join(", ")
              : "Registry returned no hazard names",
          )
        : stage(
            "hazard_categories",
            "completed",
            `Using product defaults: ${input.hazards.join(", ") || "subsidence, landslide, sinkhole"}`,
          );

  const mapEnv: PrepStageView = input.mapFailed
    ? stage("map_environment", "failed", "Map initialisation failed")
    : input.mapLoaded
      ? stage("map_environment", "completed", "Assessment map ready")
      : stage("map_environment", "in_progress");

  const geophysics: PrepStageView =
    input.geophysics === "pending"
      ? stage("geophysics_layer", "pending")
      : input.geophysics === "in_progress"
        ? stage("geophysics_layer", "in_progress")
        : input.geophysics === "available"
          ? stage("geophysics_layer", "completed", "Gravity overlay connected")
          : stage(
              "geophysics_layer",
              "failed",
              "Gravity overlay unavailable (optional)",
            );

  const geological: PrepStageView =
    input.geological === "pending"
      ? stage("geological_catalogue", "pending")
      : input.geological === "in_progress"
        ? stage("geological_catalogue", "in_progress")
        : input.geological === "available"
          ? stage(
              "geological_catalogue",
              "completed",
              `${input.geologicalCount} dataset footprint${input.geologicalCount === 1 ? "" : "s"}`,
            )
          : stage(
              "geological_catalogue",
              "failed",
              "Geological catalogue unavailable (optional)",
            );

  const stages: PrepStageView[] = [
    stage("workspace", "completed", "Assessment workspace mounted"),
    stage(
      "session",
      sessionOk ? "completed" : "failed",
      sessionOk
        ? `Signed in as ${input.sessionEmail}`
        : "Session could not be verified",
    ),
    apiConnectivity,
    backendReadiness,
    activeModel,
    hazards,
    mapEnv,
    geophysics,
    geological,
  ];

  const blockingPending = stages.some(
    (s) => s.blocking && (s.status === "pending" || s.status === "in_progress"),
  );
  // Optional layers may still be in flight after map ready; keep overlay until
  // they settle so connected-system details are truthful, without inventing success.
  const optionalPending = stages.some(
    (s) =>
      !s.blocking && (s.status === "pending" || s.status === "in_progress"),
  );

  let blockingError: string | null = null;
  if (input.apiStatus === "down") {
    blockingError =
      "Could not reach the SSRI API. Check connectivity and retry preparation.";
  } else if (!sessionOk) {
    blockingError = "The authentication session could not be verified.";
  }

  // Ready means checks settled and there is no terminal blocking failure.
  // API-down / missing session keep the preparation surface visible for retry.
  const ready =
    !blockingPending && !optionalPending && blockingError == null;

  const connected: ConnectedSystemsView = {
    api:
      input.apiStatus === "ok"
        ? "Connected"
        : input.apiStatus === "degraded"
          ? "Degraded"
          : input.apiStatus === "down"
            ? "Unavailable"
            : "Checking…",
    model:
      input.modelStatus.kind === "available"
        ? input.modelStatus.modelId ?? "Available"
        : input.modelStatus.kind === "loading"
          ? "Checking…"
          : input.modelStatus.kind === "missing"
            ? "None promoted"
            : "Unavailable",
    hazards:
      input.hazards.length > 0
        ? input.hazards.join(", ")
        : "Defaults pending",
    geophysics:
      input.geophysics === "available"
        ? "Gravity connected"
        : input.geophysics === "unavailable"
          ? "Not connected"
          : "Checking…",
    geological:
      input.geological === "available"
        ? `${input.geologicalCount} footprint${input.geologicalCount === 1 ? "" : "s"}`
        : input.geological === "unavailable"
          ? "Not connected"
          : "Checking…",
    workspace: sessionOk ? "Verified" : "Unverified",
  };

  return {
    title: ready ? "Dashboard ready" : "Preparing assessment workspace",
    description: ready
      ? "Workspace checks finished. You can select an AOI and run a ground-risk assessment when a model is available."
      : "SSRI is verifying session, API, model, and map prerequisites before the dashboard becomes interactive.",
    stages,
    connected,
    ready,
    blockingError,
  };
}
