"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PlatformShell } from "@/components/platform/PlatformShell";
import { platformGet } from "@/lib/platformApi";

export default function ModelDetailPage() {
  const params = useParams<{ id: string }>();
  const [model, setModel] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    platformGet<{ model: Record<string, unknown> }>(`/models/${params.id}`)
      .then((body) => setModel(body.model))
      .catch((err: Error) => setError(err.message));
  }, [params.id]);

  return (
    <PlatformShell>
      <h1 className="font-display text-2xl">Model version</h1>
      {error && <p className="mt-4 text-sm text-amber-900">{error}</p>}
      {model && (
        <pre className="mt-6 overflow-auto rounded-2xl border border-meadow bg-chalk p-4 text-xs text-stone">
          {JSON.stringify(model, null, 2)}
        </pre>
      )}
    </PlatformShell>
  );
}
