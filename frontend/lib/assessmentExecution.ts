/**
 * Assessment execution presentation for the live synchronous POST /api/v1/assess path.
 *
 * The API does not stream mid-request stages. Client phases below are the only
 * statuses that may be marked completed from the browser. Expected server work
 * is listed as unconfirmed until a future API progress envelope arrives.
 */

import {
  ASSESSMENT_LOADING_STAGES,
  presentAssessmentLoading,
  type AssessmentLoadingPresentation,
  type BackendAssessmentProgress,
} from "./assessmentLoading.ts";

/** Client-confirmed phases for a live assess request. */
export type AssessmentClientPhase =
  | "idle"
  | "validating"
  | "submitting"
  | "awaiting_response"
  | "complete"
  | "failed"
  | "cancelled";

export type AssessmentClientPhaseView = {
  id: AssessmentClientPhase;
  label: string;
  description: string;
  status: "pending" | "in_progress" | "completed" | "failed";
};

export type AssessmentExecutionPresentation = {
  title: string;
  description: string;
  statusLabel: string;
  clientPhases: AssessmentClientPhaseView[];
  /** Expected server pipeline — never marked complete without backend confirmation. */
  expectedServerWork: ReadonlyArray<{ id: string; label: string }>;
  /** When the API later emits stage progress, reuse the staged loader body. */
  backendPresentation: AssessmentLoadingPresentation;
  live: boolean;
};

type ActiveClientPhase = "validating" | "submitting" | "awaiting_response";

const CLIENT_PHASE_ORDER: readonly ActiveClientPhase[] = [
  "validating",
  "submitting",
  "awaiting_response",
] as const;

const CLIENT_META: Record<ActiveClientPhase, { label: string; description: string }> = {
  validating: {
    label: "Validating assessment request",
    description: "Checking AOI, model access, and request guards locally.",
  },
  submitting: {
    label: "Submitting assessment request",
    description: "Sending POST /api/v1/assess to the SSRI API.",
  },
  awaiting_response: {
    label: "Awaiting geospatial processing",
    description:
      "Waiting for acquisition, feature-stack preparation, inference, and persistence to finish on the server.",
  },
};

function clientPhaseStatus(
  phase: ActiveClientPhase,
  current: AssessmentClientPhase,
): AssessmentClientPhaseView["status"] {
  if (current === "failed" && phase === "awaiting_response") return "failed";
  if (current === "cancelled") {
    if (phase === "validating") return "completed";
    return "failed";
  }
  if (current === "complete") return "completed";
  if (current === "idle") return "pending";

  const orderedCurrent: ActiveClientPhase =
    current === "failed" ? "awaiting_response" : current;
  const currentIdx = CLIENT_PHASE_ORDER.indexOf(orderedCurrent);
  const phaseIdx = CLIENT_PHASE_ORDER.indexOf(phase);
  if (phaseIdx < 0 || currentIdx < 0) return "pending";
  if (phaseIdx < currentIdx) return "completed";
  if (phaseIdx === currentIdx) return "in_progress";
  return "pending";
}

/**
 * Build an honest assessment-execution view from client phase + optional API progress.
 * Does not invent percentages or mark server stages complete without confirmation.
 */
export function presentAssessmentExecution(options: {
  phase: AssessmentClientPhase;
  backendProgress?: BackendAssessmentProgress | null;
  errorMessage?: string | null;
}): AssessmentExecutionPresentation {
  const { phase, backendProgress = null, errorMessage = null } = options;
  const backendPresentation = presentAssessmentLoading(backendProgress);

  const clientPhases: AssessmentClientPhaseView[] = CLIENT_PHASE_ORDER.map(
    (id) => ({
      id,
      label: CLIENT_META[id].label,
      description: CLIENT_META[id].description,
      status: clientPhaseStatus(id, phase),
    }),
  );

  if (phase === "complete") {
    return {
      title: "Assessment complete",
      description: "Results are ready for review.",
      statusLabel: "Complete",
      clientPhases,
      expectedServerWork: ASSESSMENT_LOADING_STAGES.map((s) => ({
        id: s.id,
        label: s.label,
      })),
      backendPresentation,
      live: false,
    };
  }

  if (phase === "failed") {
    return {
      title: "Assessment failed",
      description:
        errorMessage?.trim() ||
        "The assessment request did not complete successfully.",
      statusLabel: "Failed",
      clientPhases,
      expectedServerWork: ASSESSMENT_LOADING_STAGES.map((s) => ({
        id: s.id,
        label: s.label,
      })),
      backendPresentation,
      live: false,
    };
  }

  if (phase === "cancelled") {
    return {
      title: "Assessment cancelled",
      description: "The in-flight assessment request was cancelled.",
      statusLabel: "Cancelled",
      clientPhases,
      expectedServerWork: ASSESSMENT_LOADING_STAGES.map((s) => ({
        id: s.id,
        label: s.label,
      })),
      backendPresentation,
      live: false,
    };
  }

  if (backendPresentation.mode === "staged") {
    return {
      title: backendPresentation.title,
      description: backendPresentation.description,
      statusLabel: "API-confirmed stage progress",
      clientPhases,
      expectedServerWork: ASSESSMENT_LOADING_STAGES.map((s) => ({
        id: s.id,
        label: s.label,
      })),
      backendPresentation,
      live: true,
    };
  }

  const statusLabel =
    phase === "validating"
      ? "Validating request"
      : phase === "submitting"
        ? "Submitting request"
        : "Waiting for assessment response";

  return {
    title: "Running ground-risk assessment",
    description:
      "The live assess API processes the request synchronously. Mid-request server stages are not streamed, so only client request phases are marked complete.",
    statusLabel,
    clientPhases,
    expectedServerWork: ASSESSMENT_LOADING_STAGES.map((s) => ({
      id: s.id,
      label: s.label,
    })),
    backendPresentation,
    live: true,
  };
}
