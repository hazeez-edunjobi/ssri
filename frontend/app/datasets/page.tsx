"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { PlatformShell } from "@/components/platform/PlatformShell";
import { platformGet, platformPost } from "@/lib/platformApi";

type Dataset = { id: string; name: string; validation_status: string | null; created_at: string };

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  function reload() {
    platformGet<{ datasets: Dataset[] }>("/datasets")
      .then((body) => setDatasets(body.datasets))
      .catch((err: Error) => setError(err.message));
  }

  useEffect(() => {
    reload();
  }, []);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await platformPost("/datasets", { name, description });
      setName("");
      setDescription("");
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create dataset");
    }
  }

  return (
    <PlatformShell>
      <h1 className="font-display text-2xl">Datasets</h1>
      <form onSubmit={onCreate} className="mt-6 grid gap-3 rounded-2xl border border-meadow bg-chalk p-5 md:grid-cols-2">
        <label className="text-xs">
          Name
          <input className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2" value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label className="text-xs">
          Description
          <input className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <button className="rounded-xl bg-leaf px-4 py-2 text-sm text-chalk md:col-span-2 md:w-fit" type="submit">
          Add dataset
        </button>
      </form>
      {error && <p className="mt-4 text-sm text-amber-900">{error}</p>}
      {datasets.length === 0 ? (
        <p className="mt-8 text-sm text-stone">No datasets yet. Add a dataset, then upload a Stage 2.5 zip.</p>
      ) : (
        <ul className="mt-6 divide-y divide-meadow rounded-2xl border border-meadow bg-chalk">
          {datasets.map((dataset) => (
            <li key={dataset.id}>
              <Link href={`/datasets/${dataset.id}`} className="flex items-center justify-between px-4 py-3 text-sm hover:bg-meadow/70">
                <span>{dataset.name}</span>
                <span className="text-xs text-stone">{dataset.validation_status || "no upload"}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </PlatformShell>
  );
}
