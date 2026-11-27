"use client";

import { Check, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PipelineStep } from "@/lib/geologicalPresentation";

export function GeologicalPipelineStepper({
  steps,
}: {
  steps: PipelineStep[];
}) {
  return (
    <ol
      className="grid grid-cols-2 gap-3 rounded-2xl border border-meadow bg-chalk p-4 sm:grid-cols-4 lg:grid-cols-8"
      data-testid="geological-pipeline"
    >
      {steps.map((step) => (
        <li key={step.id} className="min-w-0 text-center" data-state={step.status}>
          <span
            className={cn(
              "mx-auto flex h-8 w-8 items-center justify-center rounded-full border text-xs",
              step.status === "complete" && "border-leaf bg-leaf/15 text-moss",
              step.status === "warning" && "border-amber-500 bg-amber-50 text-amber-800",
              step.status === "failed" && "border-red-400 bg-red-50 text-red-800",
              step.status === "pending" && "border-meadow bg-mist text-stone",
            )}
            aria-hidden
          >
            {step.status === "complete" ? (
              <Check className="h-4 w-4" />
            ) : step.status === "warning" || step.status === "failed" ? (
              <AlertTriangle className="h-3.5 w-3.5" />
            ) : (
              <span className="h-1.5 w-1.5 rounded-full bg-stone/40" />
            )}
          </span>
          <p className="mt-2 truncate text-[11px] font-medium text-bark">{step.label}</p>
          <p className="truncate text-[10px] text-stone" title={step.detail}>
            {step.detail}
          </p>
        </li>
      ))}
    </ol>
  );
}
