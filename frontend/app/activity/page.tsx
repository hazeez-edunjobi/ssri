"use client";

import { useEffect, useState } from "react";
import { PlatformShell } from "@/components/platform/PlatformShell";
import { platformGet } from "@/lib/platformApi";

type Activity = {
  id: string;
  action: string;
  resource_type: string;
  created_at: string;
  metadata: { name?: string };
};

export default function ActivityPage() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    platformGet<{ activities: Activity[] }>("/activity?limit=50")
      .then((body) => setActivities(body.activities))
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <PlatformShell>
      <h1 className="font-display text-2xl">Activity</h1>
      {error && <p className="mt-4 text-sm text-amber-900">{error}</p>}
      {activities.length === 0 ? (
        <p className="mt-8 text-sm text-stone">No activity yet.</p>
      ) : (
        <ul className="mt-6 space-y-2 text-sm">
          {activities.map((item) => (
            <li key={item.id} className="rounded-xl border border-meadow bg-chalk px-4 py-3">
              {item.action.replaceAll("_", " ")}
              {item.metadata?.name ? ` · ${item.metadata.name}` : ""}
              <div className="text-xs text-stone">{item.created_at}</div>
            </li>
          ))}
        </ul>
      )}
    </PlatformShell>
  );
}
