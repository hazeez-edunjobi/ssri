"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PlatformShell } from "@/components/platform/PlatformShell";
import { platformGet, platformPost } from "@/lib/platformApi";

type Run = {
  id: string;
  name: string;
  status: string;
  dataset_id: string;
  dataset_version_id: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  metrics: Record<string, unknown>;
  scientific_validation_status: string;
  model_id: string | null;
};

export default function TrainingRunPage() {
  const params = useParams<{ id: string }>();
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stop = false;
    async function tick() {
      try {
        const body = await platformGet<{ training_run: Run }>(`/training/runs/${params.id}`);
        if (!stop) setRun(body.training_run);
      } catch (err) {
        if (!stop) setError(err instanceof Error ? err.message : "Could not load run");
      }
    }
    tick();
    const timer = window.setInterval(tick, 3000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [params.id]);

  const active = run && !["COMPLETED", "FAILED", "CANCELLED"].includes(run.status);

  return (
    <PlatformShell>
      <h1 className="font-display text-2xl">{run?.name || "Training run"}</h1>
      {!run && !error && <p className="mt-4 text-sm text-stone">Loading…</p>}
      {error && <p className="mt-4 text-sm text-amber-900">{error}</p>}
      {run && (
        <div className="mt-6 space-y-3 rounded-2xl border border-meadow bg-chalk p-5 text-sm">
          <p>Status: {active ? `${run.status} — training in progress…` : run.status}</p>
          <p>Scientific status: {run.scientific_validation_status}</p>
          <p className="text-stone">Dataset version {run.dataset_version_id}</p>
          {run.error_message && <p className="text-amber-900">{run.error_message}</p>}
          {Object.keys(run.metrics).length > 0 && (
            <pre className="overflow-auto rounded-xl bg-mist p-3 text-xs text-stone">
              {JSON.stringify(run.metrics, null, 2)}
            </pre>
          )}
          {active && (
            <button
              type="button"
              className="rounded-xl border border-meadow px-4 py-2"
              onClick={() => platformPost(`/training/runs/${run.id}/cancel`).then(() => undefined)}
            >
              Cancel training
            </button>
          )}
        </div>
      )}
    </PlatformShell>
  );
}
