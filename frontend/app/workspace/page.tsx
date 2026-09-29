"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PlatformShell } from "@/components/platform/PlatformShell";
import { platformGet } from "@/lib/platformApi";

type Me = {
  profile: { display_name: string; email: string; role: string };
  counts: { datasets: number; training_runs: number; models: number };
};

type Activity = { id: string; action: string; metadata: { name?: string }; created_at: string };

export default function WorkspacePage() {
  const [me, setMe] = useState<Me | null>(null);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    platformGet<Me>("/me")
      .then(setMe)
      .catch((err: Error) => setError(err.message));
    platformGet<{ activities: Activity[] }>("/activity?limit=6")
      .then((body) => setActivity(body.activities))
      .catch(() => undefined);
  }, []);

  return (
    <PlatformShell admin={me?.profile.role === "admin"}>
      <h1 className="font-display text-2xl">
        {me ? `Welcome, ${me.profile.display_name}` : "Dashboard"}
      </h1>
      <p className="mt-2 text-sm text-stone">Your datasets, training runs, and model versions.</p>
      {error && <p className="mt-4 text-sm text-amber-900">{error}</p>}
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        {[
          ["Datasets", me?.counts.datasets ?? "—", "/datasets"],
          ["Training runs", me?.counts.training_runs ?? "—", "/training"],
          ["Models", me?.counts.models ?? "—", "/models"],
        ].map(([label, value, href]) => (
          <Link key={label} href={String(href)} className="rounded-2xl border border-meadow bg-chalk p-5">
            <div className="text-xs text-stone">{label}</div>
            <div className="mt-2 font-display text-3xl">{value}</div>
          </Link>
        ))}
      </div>
      <section className="mt-8 rounded-2xl border border-meadow bg-chalk p-5">
        <h2 className="font-display text-lg">Recent activity</h2>
        {activity.length === 0 ? (
          <p className="mt-3 text-sm text-stone">No activity yet.</p>
        ) : (
          <ul className="mt-3 space-y-2 text-sm">
            {activity.map((item) => (
              <li key={item.id}>
                {item.action.replaceAll("_", " ")}
                {item.metadata?.name ? ` · ${item.metadata.name}` : ""}
              </li>
            ))}
          </ul>
        )}
      </section>
    </PlatformShell>
  );
}
