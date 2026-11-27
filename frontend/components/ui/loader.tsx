"use client";

import type { ReactNode } from "react";
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

function AssessmentBody({
  presentation,
  onCancel,
}: {
  presentation: AssessmentLoadingPresentation;
  onCancel?: () => void;
}) {
  return (
    <div
      className="space-y-5 rounded-2xl border border-meadow bg-white/60 p-5"
      data-testid="assessment-loader-body"
    >
      <div className="flex items-start gap-4">
        <Spinner className="mt-0.5 shrink-0" />
        <div className="min-w-0 flex-1">
          <h3 className="font-display text-lg text-bark">
            {presentation.title}
          </h3>
          <p className="mt-1 text-sm leading-relaxed text-stone">
            {presentation.description}
          </p>
          {presentation.mode === "indeterminate" && (
            <p
              className="mt-2 text-sm text-moss"
              data-testid="assessment-loader-status"
            >
              {presentation.statusLabel}
            </p>
          )}
        </div>
      </div>

      {presentation.mode === "staged" ? (
        <ol className="space-y-0.5" data-testid="assessment-loader-stages">
          {presentation.stages.map((stage) => {
            const done = presentation.completedStageIds.includes(stage.id);
            const current = presentation.currentStageId === stage.id;
            return (
              <li
                key={stage.id}
                className={cn(
                  "flex items-start gap-3 rounded-xl px-3 py-2",
                  current && "bg-meadow/50",
                )}
                data-testid={`assessment-loader-stage-${stage.id}`}
                data-state={current ? "current" : done ? "done" : "pending"}
              >
                <span
                  className={cn(
                    "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                    current && "bg-leaf animate-pulse motion-reduce:animate-none",
                    done && !current && "bg-moss",
                    !done && !current && "bg-meadow",
                  )}
                  aria-hidden
                />
                <span className="min-w-0">
                  <span
                    className={cn(
                      "block text-sm",
                      current
                        ? "font-medium text-bark"
                        : done
                          ? "text-moss"
                          : "text-stone/60",
                    )}
                  >
                    {stage.label}
                  </span>
                  {current && (
                    <span className="mt-0.5 block text-xs text-stone">
                      {stage.description}
                    </span>
                  )}
                </span>
              </li>
            );
          })}
        </ol>
      ) : (
        <div className="space-y-3" data-testid="assessment-loader-honest-stages">
          <IndeterminateBar />
          <p className="text-xs text-stone">
            {ASSESSMENT_LOADING_STAGES.map((s) => s.label).join(", ")}
          </p>
        </div>
      )}

      {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md text-sm text-moss underline underline-offset-2 hover:text-bark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-leaf"
          data-testid="assessment-loader-cancel"
        >
          Cancel assessment
        </button>
      )}
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
        variant === "assessment" && "mt-5 w-full",
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