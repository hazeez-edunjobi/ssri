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

function OrbitMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "relative inline-flex h-9 w-9 items-center justify-center",
        className,
      )}
      aria-hidden
    >
      <span className="absolute inset-0 rounded-full border border-meadow" />
      <span className="ssri-loader-orbit absolute inset-0 rounded-full border-2 border-transparent border-t-leaf border-r-leaf/40" />
      <span className="h-2 w-2 rounded-full bg-leaf" />
    </span>
  );
}

function InlinePulse({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "ssri-loader-pulse inline-block h-1.5 w-1.5 rounded-full bg-leaf",
        className,
      )}
      aria-hidden
    />
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
    <div className="space-y-5" data-testid="assessment-loader-body">
      <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-start">
        <OrbitMark className="mt-1 h-11 w-11 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[10px] uppercase tracking-widest text-leaf">
            Assessment in progress
          </p>
          <h3 className="mt-1 font-display text-xl text-bark sm:text-lg">
            {presentation.title}
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-stone">
            {presentation.description}
          </p>
          {presentation.mode === "indeterminate" && (
            <p
              className="mt-3 font-mono text-xs text-moss"
              data-testid="assessment-loader-status"
            >
              {presentation.statusLabel}
            </p>
          )}
        </div>
      </div>

      {presentation.mode === "staged" ? (
        <ol className="space-y-2" data-testid="assessment-loader-stages">
          {presentation.stages.map((stage) => {
            const done = presentation.completedStageIds.includes(stage.id);
            const current = presentation.currentStageId === stage.id;
            return (
              <li
                key={stage.id}
                className={cn(
                  "flex items-start gap-2.5 rounded-xl px-2 py-1.5 text-sm",
                  current && "bg-meadow/40",
                )}
                data-testid={`assessment-loader-stage-${stage.id}`}
                data-state={current ? "current" : done ? "done" : "pending"}
              >
                <span
                  className={cn(
                    "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                    current && "ssri-loader-pulse bg-leaf",
                    done && !current && "bg-moss",
                    !done && !current && "bg-meadow",
                  )}
                />
                <span className="min-w-0">
                  <span
                    className={cn(
                      "block text-[13px]",
                      current ? "text-moss" : done ? "text-stone" : "text-stone/55",
                    )}
                  >
                    {stage.label}
                  </span>
                  {current && (
                    <span className="mt-0.5 block text-[11px] text-stone">
                      {stage.description}
                    </span>
                  )}
                </span>
              </li>
            );
          })}
        </ol>
      ) : (
        <ul
          className="space-y-1.5 border-t border-meadow/80 pt-4"
          data-testid="assessment-loader-honest-stages"
        >
          {ASSESSMENT_LOADING_STAGES.map((stage) => (
            <li
              key={stage.id}
              className="flex items-center gap-2 text-[11px] text-stone/70"
            >
              <InlinePulse className="opacity-40" />
              <span>{stage.label}</span>
            </li>
          ))}
          <li className="pt-1 text-[11px] text-stone">
            Stages remain unconfirmed until the API reports progress. No completion
            is assumed.
          </li>
        </ul>
      )}

      {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          className="text-[11px] text-moss underline underline-offset-2"
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
    variant === "assessment"
      ? presentAssessmentLoading(progress)
      : null;

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
            className="mt-2 font-semibold text-moss underline"
            data-testid="loader-retry"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  const resolvedTitle =
    title ??
    (variant === "assessment"
      ? presentation?.title
      : variant === "page"
        ? "Loading"
        : "Loading");
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
          variant === "inline" && "items-center",
          variant !== "inline" && "flex-col items-center text-center",
          variant === "page" && "justify-center",
        )}
      >
        {variant === "inline" ? <InlinePulse /> : <OrbitMark />}
        <div className={cn(variant === "inline" && "min-w-0")}>
          {stage && (
            <p className="font-mono text-[10px] uppercase tracking-widest text-leaf">
              {stage}
            </p>
          )}
          {resolvedTitle && (
            <p
              className={cn(
                "text-sm text-bark",
                variant === "page" && "font-display text-lg",
                variant === "inline" && "font-mono text-xs text-stone",
              )}
            >
              {resolvedTitle}
            </p>
          )}
          {resolvedDescription && (
            <p className="mt-1 max-w-md text-xs leading-relaxed text-stone">
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
        variant === "section" && "w-full py-8",
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
          className="h-16 animate-pulse rounded-2xl border border-meadow/70 bg-meadow/30"
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
      <div className="space-y-2 text-center">
        <OrbitMark className="mx-auto" />
        <p className="font-mono text-[10px] uppercase tracking-widest text-stone">
          Preparing map
        </p>
      </div>
    </div>
  );
}
