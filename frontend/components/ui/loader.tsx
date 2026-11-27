"use client";

import { useEffect, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import {
  ASSESSMENT_LOADING_STAGES,
  presentAssessmentLoading,
  type AssessmentLoadingPresentation,
  type BackendAssessmentProgress,
} from "@/lib/assessmentLoading";

export type LoaderVariant = "inline" | "section" | "page" | "assessment";

export type LoaderProps = {
  variant?: LoaderVariant;
  title?: string;
  description?: string;
  stage?: string;
  className?: string;
  /** Optional skeleton placeholder under the loader (known layouts). */
  skeleton?: ReactNode;
  /** Assessment-only: backend progress envelope (no invented percentages). */
  progress?: BackendAssessmentProgress | null;
  onCancel?: () => void;
  onRetry?: () => void;
  /** Assessment-only: small popup in the bottom-right corner (default true). */
  floating?: boolean;
  error?: string | null;
  "data-testid"?: string;
};

/** One simple ring. Respects reduced motion (falls back to a static arc). */
function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-block h-7 w-7 rounded-full border-[3px] border-meadow border-t-leaf",
        "animate-spin motion-reduce:animate-none",
        className,
      )}
      style={{ animationDuration: "0.9s" }}
      aria-hidden
    />
  );
}

function InlineDot({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-block h-2 w-2 rounded-full bg-leaf",
        "animate-pulse motion-reduce:animate-none",
        className,
      )}
      aria-hidden
    />
  );
}

/** Slim indeterminate bar: says "working" without implying a percentage. */
function IndeterminateBar() {
  return (
    <div
      className="relative h-1 w-full overflow-hidden rounded-full bg-meadow"
      aria-hidden
    >
      <span className="absolute inset-y-0 left-0 w-2/5 animate-pulse rounded-full bg-leaf motion-reduce:animate-none" />
    </div>
  );
}

/** Shows ONE step at a time, then moves to the next. */
function AssessmentBody({
  presentation,
  onCancel,
}: {
  presentation: AssessmentLoadingPresentation;
  onCancel?: () => void;
}) {
  const [tick, setTick] = useState(0);

  // No backend progress yet: walk through the steps one by one and rest on the last.
  useEffect(() => {
    if (presentation.mode !== "indeterminate") return;
    const last = ASSESSMENT_LOADING_STAGES.length - 1;
    const id = setInterval(() => setTick((t) => Math.min(t + 1, last)), 2500);
    return () => clearInterval(id);
  }, [presentation.mode]);

  let label: string;
  let detail: string | undefined;
  let position: string | undefined;

  if (presentation.mode === "staged") {
    const idx = Math.max(
      0,
      presentation.stages.findIndex((st) => st.id === presentation.currentStageId),
    );
    const current = presentation.stages[idx];
    label = current?.label ?? presentation.title;
    detail = current?.description;
    position = `${idx + 1} of ${presentation.stages.length}`;
  } else {
    const current = ASSESSMENT_LOADING_STAGES[tick];
    label = current?.label ?? presentation.title;
    position = `${tick + 1} of ${ASSESSMENT_LOADING_STAGES.length}`;
  }

  return (
    <div
      className="flex items-center gap-3 rounded-2xl border border-meadow bg-white px-4 py-3 shadow-lg"
      data-testid="assessment-loader-body"
    >
      <Spinner className="h-5 w-5 shrink-0 border-2" />
      <div className="min-w-0 flex-1">
        <p
          key={label}
          className="ssri-step truncate text-sm font-medium text-bark"
          data-testid="assessment-loader-status"
        >
          {label}
        </p>
        {detail && <p className="truncate text-xs text-stone">{detail}</p>}
      </div>
      <span className="shrink-0 text-xs text-stone/70">{position}</span>
      {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          aria-label="Cancel assessment"
          className="shrink-0 rounded-md px-1 text-lg leading-none text-stone hover:text-bark focus-visible:outline focus-visible:outline-2 focus-visible:outline-leaf"
          data-testid="assessment-loader-cancel"
        >
          ×
        </button>
      )}
      <style>{`
        @keyframes ssri-step-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
        .ssri-step { animation: ssri-step-in .25s ease-out; }
        @media (prefers-reduced-motion: reduce) { .ssri-step { animation: none; } }
      `}</style>
    </div>
  );
}

/**
 * Reusable SSRI loader for inline, section, page, and assessment contexts.
 */
export function Loader({
  variant = "section",
  title,
  description,
  stage,
  className,
  skeleton,
  progress,
  onCancel,
  onRetry,
  floating = true,
  error,
  "data-testid": testId,
}: LoaderProps) {
  const presentation =
    variant === "assessment" ? presentAssessmentLoading(progress) : null;

  if (error) {
    return (
      <div
        className={cn(
          "rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950",
          className,
        )}
        role="alert"
        data-testid={testId ?? "loader-error"}
      >
        <p>{error}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-2 font-semibold text-moss underline hover:text-bark"
            data-testid="loader-retry"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  const resolvedTitle =
    title ?? (variant === "assessment" ? presentation?.title : "Loading");
  const resolvedDescription =
    description ??
    (variant === "assessment" ? presentation?.description : undefined);

  const body =
    variant === "assessment" && presentation ? (
      <AssessmentBody presentation={presentation} onCancel={onCancel} />
    ) : (
      <div
        className={cn(
          "flex gap-3",
          variant === "inline"
            ? "items-center"
            : "flex-col items-center text-center",
        )}
      >
        {variant === "inline" ? <InlineDot /> : <Spinner />}
        <div className="min-w-0">
          {stage && <p className="text-xs font-medium text-leaf">{stage}</p>}
          {resolvedTitle && (
            <p
              className={cn(
                "text-sm text-bark",
                variant === "page" && "font-display text-lg",
                variant === "inline" && "text-xs text-stone",
              )}
            >
              {resolvedTitle}
            </p>
          )}
          {resolvedDescription && (
            <p className="mt-1 max-w-md text-sm leading-relaxed text-stone">
              {resolvedDescription}
            </p>
          )}
        </div>
      </div>
    );

  return (
    <div
      className={cn(
        "ssri-loader",
        variant === "page" &&
          "flex min-h-[40vh] w-full flex-col items-center justify-center px-6 py-16",
        variant === "section" && "flex w-full justify-center py-10",
        variant === "inline" && "inline-flex items-center",
        variant === "assessment" &&
          (floating
            ? "fixed bottom-4 right-4 z-50 w-[calc(100%-2rem)] max-w-sm"
            : "mt-5 w-full max-w-sm"),
        className,
      )}
      role="status"
      aria-live="polite"
      aria-busy="true"
      data-testid={testId ?? `loader-${variant}`}
      data-variant={variant}
    >
      {body}
      {skeleton ? <div className="mt-6 w-full">{skeleton}</div> : null}
    </div>
  );
}

export function ContentSkeleton({
  rows = 3,
  className,
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div
      className={cn("space-y-3", className)}
      data-testid="content-skeleton"
      aria-hidden
    >
      {Array.from({ length: rows }, (_, index) => (
        <div
          key={index}
          className="h-16 animate-pulse rounded-2xl bg-meadow/40 motion-reduce:animate-none"
        />
      ))}
    </div>
  );
}

export function MapSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex h-full min-h-[12rem] w-full items-center justify-center bg-meadow/20",
        className,
      )}
      data-testid="map-skeleton"
      aria-hidden
    >
      <div className="flex flex-col items-center gap-2">
        <Spinner />
        <p className="text-sm text-stone">Preparing map</p>
      </div>
    </div>
  );
}