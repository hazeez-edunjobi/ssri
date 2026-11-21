/**
 * Dashboard active-model status for assessment preflight.
 * Distinguishes empty registry from auth/network failures.
 */

export type ActiveModelStatusKind =
  | "loading"
  | "available"
  | "missing"
  | "unauthorized"
  | "forbidden"
  | "error";

export type ActiveModelView = {
  kind: ActiveModelStatusKind;
  modelId: string | null;
  label: string | null;
  /** True when the API reports a readable promoted checkpoint. */
  checkpointAvailable: boolean;
};

export type ActiveModelResponseLike = {
  active?: {
    model_id?: string;
    name?: string;
  } | null;
  model_id?: string | null;
  checkpoint_path?: string | null;
  checkpoint_available?: boolean;
};

export const MISSING_MODEL_ASSESS_HINT =
  "No promoted Stage 2.5 model is currently available. Ask an operator to promote a trained model before running an assessment.";

export const UNAUTHORIZED_MODEL_STATUS =
  "Sign in is required to retrieve the promoted production model status.";

export const FORBIDDEN_MODEL_STATUS =
  "Your account does not have permission to read the promoted model status.";

export const ERROR_MODEL_STATUS =
  "Could not verify the promoted production model. Retry the status check.";

export function loadingActiveModel(): ActiveModelView {
  return {
    kind: "loading",
    modelId: null,
    label: null,
    checkpointAvailable: false,
  };
}

export function activeModelFromResponse(
  body: ActiveModelResponseLike,
): ActiveModelView {
  const available = Boolean(
    body.checkpoint_available ?? body.checkpoint_path,
  );
  const modelId = body.model_id ?? body.active?.model_id ?? null;
  const label = body.active
    ? `${body.active.name ?? "Model"} (${body.active.model_id ?? modelId ?? "unknown"})`
    : null;
  if (available && (modelId || body.active)) {
    return {
      kind: "available",
      modelId: modelId,
      label,
      checkpointAvailable: true,
    };
  }
  return {
    kind: "missing",
    modelId: modelId,
    label: null,
    checkpointAvailable: false,
  };
}

export function activeModelFromHttpStatus(status: number): ActiveModelView {
  if (status === 401) {
    return {
      kind: "unauthorized",
      modelId: null,
      label: null,
      checkpointAvailable: false,
    };
  }
  if (status === 403) {
    return {
      kind: "forbidden",
      modelId: null,
      label: null,
      checkpointAvailable: false,
    };
  }
  return {
    kind: "error",
    modelId: null,
    label: null,
    checkpointAvailable: false,
  };
}

export function activeModelFromNetworkError(): ActiveModelView {
  return {
    kind: "error",
    modelId: null,
    label: null,
    checkpointAvailable: false,
  };
}

/** Ordinary assessments need a promoted model; operators may supply a path. */
export function hasAssessmentModelAccess(
  status: ActiveModelView,
  checkpoint: string,
): boolean {
  if (checkpoint.trim()) return true;
  return status.kind === "available" && status.checkpointAvailable;
}

export function assessmentButtonDisabled(args: {
  loading: boolean;
  selectedHazardCount: number;
  status: ActiveModelView;
  checkpoint: string;
}): boolean {
  if (args.loading) return true;
  if (args.selectedHazardCount === 0) return true;
  if (!hasAssessmentModelAccess(args.status, args.checkpoint)) return true;
  return false;
}

export function modelStatusPanelMessage(status: ActiveModelView): string {
  switch (status.kind) {
    case "loading":
      return "Checking promoted production model…";
    case "available":
      return status.label
        ? `Using promoted registry model: ${status.label}`
        : "Using the promoted production model.";
    case "missing":
      return "No promoted Stage 2.5 checkpoint is configured. Assessments cannot run until an operator promotes a trained model.";
    case "unauthorized":
      return UNAUTHORIZED_MODEL_STATUS;
    case "forbidden":
      return FORBIDDEN_MODEL_STATUS;
    case "error":
      return ERROR_MODEL_STATUS;
  }
}

/** Shown near Run assessment when the control is blocked by model status. */
export function modelStatusAssessHint(status: ActiveModelView): string | null {
  if (status.kind === "available" && status.checkpointAvailable) return null;
  switch (status.kind) {
    case "loading":
      return "Waiting for promoted model status before assessment can run.";
    case "missing":
      return MISSING_MODEL_ASSESS_HINT;
    case "unauthorized":
      return UNAUTHORIZED_MODEL_STATUS;
    case "forbidden":
      return FORBIDDEN_MODEL_STATUS;
    case "error":
      return ERROR_MODEL_STATUS;
    default:
      return MISSING_MODEL_ASSESS_HINT;
  }
}
