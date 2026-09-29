"use client";

import { useEffect, useState } from "react";
import { PlatformShell } from "@/components/platform/PlatformShell";
import { platformGet } from "@/lib/platformApi";

type Overview = {
  counts: Record<string, number>;
  recent_activity: Array<{ id: string; action: string; created_at: string }>;
};
type UserRow = { id: string; email: string; created_at: string; datasets: number; training_runs: number };

export default function AdminPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    platformGet<Overview>("/admin/overview")
      .then(setOverview)
      .catch((err: Error) => setError(err.message));
    platformGet<{ users: UserRow[] }>("/admin/users")
      .then((body) => setUsers(body.users))
      .catch(() => undefined);
  }, []);

  return (
    <PlatformShell admin>
      <h1 className="font-display text-2xl">Admin</h1>
      <p className="mt-2 text-sm text-stone">Platform counts come from stored records. Admin access is a profile role, not an email address.</p>
      {error && <p className="mt-4 text-sm text-amber-900">{error}</p>}
      {overview && (
        <div className="mt-6 grid gap-4 md:grid-cols-4">
          {Object.entries(overview.counts).map(([key, value]) => (
            <div key={key} className="rounded-2xl border border-meadow bg-chalk p-4">
              <div className="text-xs text-stone">{key.replaceAll("_", " ")}</div>
              <div className="font-display text-2xl">{value}</div>
            </div>
          ))}
        </div>
      )}
      <section className="mt-8">
        <h2 className="font-display text-lg">Users</h2>
        {users.length === 0 ? (
          <p className="mt-3 text-sm text-stone">No users to show.</p>
        ) : (
          <table className="mt-3 w-full text-left text-sm">
            <thead className="text-xs text-stone"><tr><th>Email</th><th>Datasets</th><th>Runs</th></tr></thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-t border-meadow">
                  <td className="py-2">{user.email}</td>
                  <td>{user.datasets}</td>
                  <td>{user.training_runs}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </PlatformShell>
  );
}
