/**
 * Honest assessment processing presentation.
 * Stages advance only when the backend confirms progress; otherwise a single
 * indeterminate processing state is shown (no invented percentages).
 */

export type AssessmentLoadingStageId =
  | "preparing"
  | "acquiring"
  | "feature_stack"
  | "inference"
  | "spatial"
  | "evidence"
  | "processing";

export type AssessmentLoadingStage = {
  id: AssessmentLoadingStageId;
  label: string;
  description: string;
};

/** Ordered stages used when the API exposes confirmed progress milestones. */
export const ASSESSMENT_LOADING_STAGES: readonly AssessmentLoadingStage[] = [
  {
    id: "preparing",
    label: "Preparing assessment",
    description: "Validating request and resolving the active checkpoint.",
  },
  {
    id: "acquiring",
    label: "Acquiring geospatial data",
    description: "Gathering DEM, optical, and geophysics layers for the AOI.",
  },
  {
    id: "feature_stack",
    label: "Preparing the feature stack",
    description: "Assembling the 13-channel Stage 2.5 tensor.",
  },
  {
    id: "inference",
    label: "Running model inference",
    description: "Scoring relative susceptibility (NOT_VALIDATED).",
  },
  {
    id: "spatial",
    label: "Generating spatial outputs",
    description: "Writing georeferenced hazard surfaces when requested.",
  },
  {
    id: "evidence",
    label: "Saving assessment evidence",
    description: "Persisting acquisition audit artefacts when available.",
  },
] as const;

export type BackendAssessmentProgress = {
  /** Explicit stage id from the API when present. */
  stage?: string | null;
  /** Confirmed completed stage ids only — never inferred locally. */
  completed_stages?: readonly string[] | null;
  status?: string | null;
  message?: string | null;
};

export type AssessmentLoadingPresentation =
  | {
      mode: "indeterminate";
      title: string;
      description: string;
      statusLabel: string;
    }
  | {
      mode: "staged";
      title: string;
      description: string;
      currentStageId: AssessmentLoadingStageId;
      completedStageIds: AssessmentLoadingStageId[];
      stages: readonly AssessmentLoadingStage[];
    };

const STAGE_IDS = new Set<string>(ASSESSMENT_LOADING_STAGES.map((s) => s.id));

function asStageId(value: string | null | undefined): AssessmentLoadingStageId | null {
  if (!value) return null;
  return STAGE_IDS.has(value) ? (value as AssessmentLoadingStageId) : null;
}

/**
 * Map backend progress to UI presentation without inventing completion.
 * Synchronous `/assess` with no stage payload → indeterminate processing.
 */
export function presentAssessmentLoading(
  progress: BackendAssessmentProgress | null | undefined,
): AssessmentLoadingPresentation {
  const status = (progress?.status ?? "").toLowerCase();
  const message =
    progress?.message?.trim() ||
    "Geospatial acquisition and model inference can take a little while. This interface stays responsive while the request runs.";

  const current = asStageId(progress?.stage ?? undefined);
  const completedRaw = progress?.completed_stages ?? [];
  const completed: AssessmentLoadingStageId[] = [];
  for (const item of completedRaw) {
    const id = asStageId(item);
    if (id && !completed.includes(id)) completed.push(id);
  }

  if (current) {
    return {
      mode: "staged",
      title: "Assessment in progress",
      description: message,
      currentStageId: current,
      completedStageIds: completed,
      stages: ASSESSMENT_LOADING_STAGES,
    };
  }

  // Generic pending/running/empty — honest indeterminate state (no fake %).
  if (
    !progress ||
    !status ||
    status === "pending" ||
    status === "running" ||
    status === "in_progress" ||
    status === "processing"
  ) {
    return {
      mode: "indeterminate",
      title: "Acquiring geospatial intelligence",
      description: message,
      statusLabel:
        status === "pending"
          ? "Queued"
          : status === "running" || status === "in_progress" || status === "processing"
            ? "Processing"
            : "Processing geospatial request",
    };
  }

  return {
    mode: "indeterminate",
    title: "Acquiring geospatial intelligence",
    description: message,
    statusLabel: progress?.status?.trim() || "Processing geospatial request",
  };
}

export function canSubmitAssessment(options: {
  loading: boolean;
  inFlight: boolean;
}): boolean {
  return !options.loading && !options.inFlight;
}
