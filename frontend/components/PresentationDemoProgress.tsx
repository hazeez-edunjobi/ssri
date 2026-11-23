"use client";

import { useEffect, useState } from "react";
import {
  ASSESSMENT_PREVIEW_LABEL,
  DEMO_PROGRESS_STAGES,
  PRESENTATION_DEMO_DURATION_MS,
  demoProgressPercent,
  demoStageAt,
} from "@/lib/presentationDemo";

type Props = {
  active: boolean;
  onCancel?: () => void;
};

/**
 * Simulated 15s presentation progress for Assessment Preview workflows.
 * Only mounts the animated tracker while ``active`` so we never reset state
 * synchronously inside an effect when inactive.
 */
export function PresentationDemoProgress({ active, onCancel }: Props) {
  if (!active) return null;
  return <PresentationDemoProgressActive onCancel={onCancel} />;
}

function PresentationDemoProgressActive({ onCancel }: { onCancel?: () => void }) {
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    const started = performance.now();
    let frame = 0;
    const tick = () => {
      const next = Math.min(
        PRESENTATION_DEMO_DURATION_MS,
        performance.now() - started,
      );
      setElapsedMs(next);
      if (next < PRESENTATION_DEMO_DURATION_MS) {
        frame = window.requestAnimationFrame(tick);
      }
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const stage = demoStageAt(elapsedMs);
  const percent = demoProgressPercent(elapsedMs);

  return (
    <div
      className="mt-5 space-y-4"
      data-testid="presentation-demo-progress"
      aria-live="polite"
    >
      <p className="font-mono text-[10px] uppercase tracking-widest text-leaf">
        {ASSESSMENT_PREVIEW_LABEL}
      </p>
      <div className="h-1.5 overflow-hidden rounded-full bg-meadow/60">
        <div
          className="h-full rounded-full bg-leaf transition-[width] duration-150 ease-out"
          style={{ width: `${percent}%` }}
          data-testid="presentation-demo-progress-bar"
        />
      </div>
      <p
        className="font-mono text-sm text-bark"
        data-testid="presentation-demo-stage"
      >
        {stage.label}…
      </p>
      <ol className="space-y-1.5">
        {DEMO_PROGRESS_STAGES.map((item) => {
          const done = elapsedMs >= item.endMs;
          const current = stage.id === item.id;
          return (
            <li
              key={item.id}
              className={`flex items-center gap-2 text-[11px] ${
                current
                  ? "text-moss"
                  : done
                    ? "text-stone"
                    : "text-stone/60"
              }`}
              data-testid={`presentation-demo-stage-${item.id}`}
              data-state={current ? "current" : done ? "done" : "pending"}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  current ? "animate-pulse bg-leaf" : done ? "bg-moss" : "bg-meadow"
                }`}
              />
              {item.label}
            </li>
          );
        })}
      </ol>
      {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          className="text-[11px] text-moss underline"
          data-testid="presentation-demo-cancel"
        >
          Cancel assessment
        </button>
      )}
    </div>
  );
}
