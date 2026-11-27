"use client";

import { cn } from "@/lib/utils";
import type { DashboardPreparationPresentation } from "@/lib/dashboardPreparation";

function StatusDot({
  status,
}: {
  status: "pending" | "in_progress" | "completed" | "failed" | "skipped";
}) {
  return (
    <span
      className={cn(
        "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
        status === "in_progress" && "ssri-loader-pulse bg-leaf",
        status === "completed" && "bg-moss",
        status === "failed" && "bg-amber-700",
        (status === "pending" || status === "skipped") && "bg-meadow",
      )}
      aria-hidden
    />
  );
}

type DashboardPreparationProps = {
  presentation: DashboardPreparationPresentation;
  onRetry?: () => void;
  onContinue?: () => void;
  /** Use absolute fill inside a parent instead of the full viewport. */
  contained?: boolean;
  "data-testid"?: string;
};

/**
 * Full-viewport preparation experience for dashboard boot.
 * Statuses are driven by real async operations — not timers.
 */
export function DashboardPreparation({
  presentation,
  onRetry,
  onContinue,
  contained = false,
  "data-testid": testId,
}: DashboardPreparationProps) {
  return (
    <div
      className={cn(
        "flex items-center justify-center bg-land-wash px-4 py-10",
        contained ? "absolute inset-0 overflow-y-auto" : "fixed inset-0 z-40",
      )}
      role="status"
      aria-live="polite"
      aria-busy={!presentation.ready}
      data-testid={testId ?? "dashboard-preparation"}
      data-ready={presentation.ready ? "true" : "false"}
    >
      <div className="w-full max-w-xl rounded-2xl border border-meadow bg-chalk p-6 shadow-soft sm:p-8">
        <p className="font-mono text-[10px] uppercase tracking-widest text-leaf">
          SSRI preparation
        </p>
        <div className="mt-3 flex items-start gap-4">
          <span
            className="relative mt-1 inline-flex h-11 w-11 shrink-0 items-center justify-center"
            aria-hidden
          >
            <span className="absolute inset-0 rounded-full border border-meadow" />
            {!presentation.ready && (
              <span className="ssri-loader-orbit absolute inset-0 rounded-full border-2 border-transparent border-t-leaf border-r-leaf/40" />
            )}
            <span className="h-2 w-2 rounded-full bg-leaf" />
          </span>
          <div className="min-w-0">
            <h1 className="font-display text-2xl text-bark sm:text-xl">
              {presentation.title}
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-stone">
              {presentation.description}
            </p>
          </div>
        </div>

        <ol className="mt-6 space-y-1.5" data-testid="dashboard-prep-stages">
          {presentation.stages.map((stage) => (
            <li
              key={stage.id}
              className={cn(
                "flex items-start gap-2.5 rounded-xl px-2 py-1.5 text-sm",
                stage.status === "in_progress" && "bg-meadow/40",
              )}
              data-testid={`dashboard-prep-stage-${stage.id}`}
              data-state={stage.status}
            >
              <StatusDot status={stage.status} />
              <span className="min-w-0">
                <span
                  className={cn(
                    "block text-[13px]",
                    stage.status === "in_progress"
                      ? "text-moss"
                      : stage.status === "completed"
                        ? "text-bark"
                        : stage.status === "failed"
                          ? "text-amber-900"
                          : "text-stone/55",
                  )}
                >
                  {stage.label}
                </span>
                {(stage.status === "in_progress" || stage.detail) && (
                  <span className="mt-0.5 block text-[11px] text-stone">
                    {stage.detail ?? stage.description}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ol>

        <div
          className="mt-6 border-t border-meadow/80 pt-4"
          data-testid="dashboard-prep-connected"
        >
          <p className="font-mono text-[10px] uppercase tracking-widest text-leaf">
            Connected systems
          </p>
          <dl className="mt-3 grid grid-cols-1 gap-2 text-[12px] sm:grid-cols-2">
            {(
              [
                ["Workspace", presentation.connected.workspace],
                ["API", presentation.connected.api],
                ["Active model", presentation.connected.model],
                ["Hazards", presentation.connected.hazards],
                ["Geophysics", presentation.connected.geophysics],
                ["Geological", presentation.connected.geological],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="rounded-lg bg-meadow/25 px-2.5 py-2">
                <dt className="font-mono text-[10px] uppercase tracking-wider text-stone">
                  {label}
                </dt>
                <dd className="mt-0.5 text-bark">{value}</dd>
              </div>
            ))}
          </dl>
        </div>

        {presentation.blockingError && (
          <div
            className="mt-5 rounded-xl border border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-950"
            role="alert"
            data-testid="dashboard-prep-error"
          >
            <p>{presentation.blockingError}</p>
            <div className="mt-3 flex flex-wrap gap-3">
              {onRetry && (
                <button
                  type="button"
                  onClick={onRetry}
                  className="font-semibold text-moss underline underline-offset-2"
                  data-testid="dashboard-prep-retry"
                >
                  Retry preparation
                </button>
              )}
              {onContinue && (
                <button
                  type="button"
                  onClick={onContinue}
                  className="text-stone underline underline-offset-2"
                  data-testid="dashboard-prep-continue"
                >
                  Open workspace anyway
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
