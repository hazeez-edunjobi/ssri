"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  LOCAL_ACCEPTANCE_EMAIL,
  localAcceptanceSessionAllowed,
} from "@/lib/localAcceptanceSession";
import { getSupabase, supabaseConfig } from "@/lib/supabase";

type SessionValue = { email: string | null };

const SessionContext = createContext<SessionValue>({ email: null });

export function useRequiredSession() {
  return useContext(SessionContext);
}

export function RequireSession({
  children,
  nextPath,
}: {
  children: React.ReactNode;
  nextPath: string;
}) {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const configured = supabaseConfig().configured;
  const localAcceptance = localAcceptanceSessionAllowed();

  useEffect(() => {
    if (localAcceptance) {
      setEmail(LOCAL_ACCEPTANCE_EMAIL);
      setReady(true);
      return;
    }
    const supabase = getSupabase();
    if (!supabase) {
      // Unconfigured environments render the "Sign-in is not configured"
      // panel below before `ready` is ever consulted, so nothing to sync.
      return;
    }
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.replace(`/login?next=${encodeURIComponent(nextPath)}`);
        return;
      }
      setEmail(data.session.user.email ?? null);
      setReady(true);
    });
  }, [nextPath, router, localAcceptance]);

  if (!configured) {
    return (
      <main className="min-h-screen bg-mist px-6 py-16 text-bark">
        <div className="mx-auto max-w-lg rounded-2xl border border-meadow bg-chalk p-6 text-sm">
          <h1 className="font-display text-xl">Sign-in is not configured</h1>
          <p className="mt-3 text-stone">
            Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY before opening an assessment.
          </p>
        </div>
      </main>
    );
  }

  if (!ready) {
    return (
      <main className="min-h-screen bg-mist px-6 py-16 text-sm text-stone">Loading session…</main>
    );
  }

  return <SessionContext.Provider value={{ email }}>{children}</SessionContext.Provider>;
}
