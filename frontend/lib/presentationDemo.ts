/**
 * Presentation-demo helpers (SSRI_DEMO_MODE only).
 * Simulated stages are UX only — they do not claim live acquisition or inference.
 */

export const PRESENTATION_DEMO_DURATION_MS = 15_000;

/** Discreet UI label for demo-mode assessments. */
export const ASSESSMENT_PREVIEW_LABEL = "Assessment Preview";

/**
 * Methodology note for report metadata only — not for prominent dashboard banners.
 * Distinguishes catalogue preview scenarios from live model inference.
 */
export const ASSESSMENT_PREVIEW_METHODOLOGY_NOTE =
  "Assessment Preview: scores come from the presentation catalogue scenario, not live model inference or field-verified measurements.";

/** @deprecated Use ASSESSMENT_PREVIEW_LABEL / ASSESSMENT_PREVIEW_METHODOLOGY_NOTE. */
export const ILLUSTRATIVE_DEMO_DISCLOSURE = ASSESSMENT_PREVIEW_METHODOLOGY_NOTE;

export type DemoProgressStage = {
  id: string;
  label: string;
  /** Inclusive start offset in ms from assess click. */
  startMs: number;
  /** Exclusive end offset in ms (last stage ends at PRESENTATION_DEMO_DURATION_MS). */
  endMs: number;
};

export const DEMO_PROGRESS_STAGES: readonly DemoProgressStage[] = [
  {
    id: "validate",
    label: "Validating assessment coordinates and AOI",
    startMs: 0,
    endMs: 3000,
  },
  {
    id: "layers",
    label: "Preparing geospatial feature layers",
    startMs: 3000,
    endMs: 6000,
  },
  {
    id: "subsidence",
    label: "Evaluating subsidence susceptibility",
    startMs: 6000,
    endMs: 9000,
  },
  {
    id: "landslide-sinkhole",
    label: "Evaluating landslide and sinkhole susceptibility",
    startMs: 9000,
    endMs: 12000,
  },
  {
    id: "uncertainty",
    label: "Preparing uncertainty and confidence analytics",
    startMs: 12000,
    endMs: 14000,
  },
  {
    id: "report",
    label: "Generating assessment report",
    startMs: 14000,
    endMs: PRESENTATION_DEMO_DURATION_MS,
  },
] as const;

export type DemoScenarioSummary = {
  key: string;
  location_name: string;
  profile_label: string;
  latitude: number;
  longitude: number;
  assessment_type: string;
  summary: string;
  landslide: number;
  subsidence: number;
  sinkhole: number;
  confidence_tier: string;
  timestamp_iso: string;
  disclosure?: string;
};

export function demoStageAt(elapsedMs: number): DemoProgressStage {
  const clamped = Math.max(0, elapsedMs);
  for (const stage of DEMO_PROGRESS_STAGES) {
    if (clamped >= stage.startMs && clamped < stage.endMs) return stage;
  }
  return DEMO_PROGRESS_STAGES[DEMO_PROGRESS_STAGES.length - 1];
}

export function demoProgressPercent(elapsedMs: number): number {
  const pct = (elapsedMs / PRESENTATION_DEMO_DURATION_MS) * 100;
  return Math.max(0, Math.min(100, pct));
}

/** Group catalogue by city for the presentation picker. */
export function groupDemoScenariosByLocation(
  scenarios: DemoScenarioSummary[],
): Map<string, DemoScenarioSummary[]> {
  const map = new Map<string, DemoScenarioSummary[]>();
  for (const scenario of scenarios) {
    const list = map.get(scenario.location_name) ?? [];
    list.push(scenario);
    map.set(scenario.location_name, list);
  }
  return map;
}

export function waitForPresentationDemo(
  durationMs: number,
  signal?: AbortSignal,
): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Assessment cancelled", "AbortError"));
      return;
    }
    const timer = window.setTimeout(() => resolve(), durationMs);
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(new DOMException("Assessment cancelled", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}
