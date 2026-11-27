"use client";

import { cn } from "@/lib/utils";
import {
  presentAssessmentExecution,
  type AssessmentClientPhase,
} from "@/lib/assessmentExecution";
import type { BackendAssessmentProgress } from "@/lib/assessmentLoading";
import { Loader } from "@/components/ui/loader";

type AssessmentExecutionLoaderProps = {
  phase: AssessmentClientPhase;
  backendProgress?: BackendAssessmentProgress | null;
  onCancel?: () => void;
  "data-testid"?: string;
};

/**
 * Live assessment execution UI.
 * Marks only client-confirmed request phases complete; lists expected server
 * work as unconfirmed unless the API supplies stage progress.
 */
export function AssessmentExecutionLoader({
  phase,
  backendProgress = null,
  onCancel,
  "data-testid": testId,
}: AssessmentExecutionLoaderProps) {
  const presentation = presentAssessmentExecution({
    phase,
    backendProgress,
  });

  if (presentation.backendPresentation.mode === "staged") {
    return (
      <Loader
        variant="assessment"
        progress={backendProgress}
        onCancel={onCancel}
        data-testid={testId ?? "assess-result-loading"}
      />
    );
  }

  return (
    <div
      className="mt-5 w-full space-y-5"
      role="status"
      aria-live="polite"
      aria-busy="true"
      data-testid={testId ?? "assess-result-loading"}
      data-phase={phase}
    >
      <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-start">
        <span
          className="relative mt-1 inline-flex h-11 w-11 shrink-0 items-center justify-center"
          aria-hidden
        >
          <span className="absolute inset-0 rounded-full border border-meadow" />
          <span className="ssri-loader-orbit absolute inset-0 rounded-full border-2 border-transparent border-t-leaf border-r-leaf/40" />
          <span className="h-2 w-2 rounded-full bg-leaf" />
        </span>
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
          <p
            className="mt-3 font-mono text-xs text-moss"
            data-testid="assessment-execution-status"
          >
            {presentation.statusLabel}
          </p>
        </div>
      </div>

      <ol className="space-y-2" data-testid="assessment-client-phases">
        {presentation.clientPhases.map((item) => (
          <li
            key={item.id}
            className={cn(
              "flex items-start gap-2.5 rounded-xl px-2 py-1.5 text-sm",
              item.status === "in_progress" && "bg-meadow/40",
            )}
            data-testid={`assessment-client-phase-${item.id}`}
            data-state={item.status}
          >
            <span
              className={cn(
                "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                item.status === "in_progress" && "ssri-loader-pulse bg-leaf",
                item.status === "completed" && "bg-moss",
                item.status === "failed" && "bg-amber-700",
                item.status === "pending" && "bg-meadow",
              )}
            />
            <span className="min-w-0">
              <span
                className={cn(
                  "block text-[13px]",
                  item.status === "in_progress"
                    ? "text-moss"
                    : item.status === "completed"
                      ? "text-bark"
                      : "text-stone/55",
                )}
              >
                {item.label}
              </span>
              {item.status === "in_progress" && (
                <span className="mt-0.5 block text-[11px] text-stone">
                  {item.description}
                </span>
              )}
            </span>
          </li>
        ))}
      </ol>

      <div
        className="border-t border-meadow/80 pt-4"
        data-testid="assessment-expected-server-work"
      >
        <p className="font-mono text-[10px] uppercase tracking-widest text-leaf">
          Expected server work
        </p>
        <ul className="mt-2 space-y-1.5">
          {presentation.expectedServerWork.map((item) => (
            <li
              key={item.id}
              className="flex items-center gap-2 text-[11px] text-stone/70"
            >
              <span className="ssri-loader-pulse inline-block h-1.5 w-1.5 rounded-full bg-leaf opacity-40" />
              <span>{item.label}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11px] text-stone">
          Server stages stay unconfirmed while the synchronous assess request is
          in flight. No completion percentage is invented.
        </p>
      </div>

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
