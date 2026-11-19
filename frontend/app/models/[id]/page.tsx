"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PlatformShell } from "@/components/platform/PlatformShell";
import { platformGet, platformPost } from "@/lib/platformApi";

export default function ModelDetailPage() {
  const params = useParams<{ id: string }>();
  const [model, setModel] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [promoting, setPromoting] = useState(false);

  useEffect(() => {
    platformGet<{ model: Record<string, unknown> }>(`/models/${params.id}`)
      .then((body) => setModel(body.model))
      .catch((err: Error) => setError(err.message));
  }, [params.id]);

  async function onPromote() {
    setPromoting(true);
    setError(null);
    setMessage(null);
    try {
      const body = await platformPost<{
        checkpoint_path: string;
        message: string;
      }>(`/models/${params.id}/promote`);
      setMessage(`${body.message} Active path: ${body.checkpoint_path}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Promotion failed.");
    } finally {
      setPromoting(false);
    }
  }

  const metrics =
    model && typeof model.metrics === "object" && model.metrics
      ? (model.metrics as Record<string, unknown>)
      : {};

  return (
    <PlatformShell>
      <h1 className="font-display text-2xl">Model version</h1>
      <p className="mt-2 max-w-2xl text-sm text-stone">
        Training completion does not mean the model is scientifically validated.
        Promote only when you want this checkpoint prefilled on the assessment
        dashboard.
      </p>
      {error && <p className="mt-4 text-sm text-amber-900">{error}</p>}
      {message && <p className="mt-4 text-sm text-leaf">{message}</p>}
      {model && (
        <div className="mt-6 space-y-4">
          <button
            type="button"
            onClick={onPromote}
            disabled={promoting || !metrics.registry_model_id}
            className="rounded-xl border border-meadow bg-chalk px-4 py-2 text-sm text-bark disabled:opacity-50"
            data-testid="promote-model"
          >
            {promoting ? "Promoting…" : "Promote for assessment"}
          </button>
          {!metrics.registry_model_id && (
            <p className="text-xs text-stone">
              This record has no training-registry id, so it cannot be promoted.
            </p>
          )}
          <dl className="grid gap-2 text-sm text-stone sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-widest">Checkpoint</dt>
              <dd className="font-mono text-xs text-bark">{String(model.checkpoint_path || "")}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-widest">Channels</dt>
              <dd>{String(model.feature_channels ?? "—")}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-widest">Schema</dt>
              <dd>{String(metrics.channel_schema_version ?? "—")}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-widest">Validation</dt>
              <dd>{String(model.scientific_validation_status || "NOT_VALIDATED")}</dd>
            </div>
          </dl>
          <pre className="overflow-auto rounded-2xl border border-meadow bg-chalk p-4 text-xs text-stone">
            {JSON.stringify(model, null, 2)}
          </pre>
        </div>
      )}
    </PlatformShell>
  );
}
