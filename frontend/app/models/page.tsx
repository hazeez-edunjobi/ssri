"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PlatformShell } from "@/components/platform/PlatformShell";
import { platformGet } from "@/lib/platformApi";

type Model = {
  id: string;
  name: string;
  version: number;
  scientific_validation_status: string;
  training_run_id: string;
  created_at: string;
};

export default function ModelsPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    platformGet<{ models: Model[] }>("/models")
      .then((body) => setModels(body.models))
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <PlatformShell>
      <h1 className="font-display text-2xl">Models</h1>
      <p className="mt-2 text-sm text-stone">
        Each successful run creates a new version. Training success does not make a model scientifically validated, and nothing here replaces the assessment checkpoint unless you promote it from the operator tools.
      </p>
      {error && <p className="mt-4 text-sm text-amber-900">{error}</p>}
      {models.length === 0 ? (
        <p className="mt-8 text-sm text-stone">No models have been trained yet.</p>
      ) : (
        <ul className="mt-6 divide-y divide-meadow rounded-2xl border border-meadow bg-chalk">
          {models.map((model) => (
            <li key={model.id}>
              <Link href={`/models/${model.id}`} className="flex justify-between px-4 py-3 text-sm">
                <span>v{model.version} · {model.name}</span>
                <span className="text-xs text-stone">{model.scientific_validation_status}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </PlatformShell>
  );
}
