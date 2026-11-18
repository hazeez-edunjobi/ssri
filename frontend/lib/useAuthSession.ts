"use client";

import { useEffect, useState } from "react";
import { getSupabase, supabaseConfig } from "@/lib/supabase";

export type AuthStatus = "loading" | "in" | "out" | "unconfigured";

export function useAuthSession() {
  const [status, setStatus] = useState<AuthStatus>(() =>
    supabaseConfig().configured ? "loading" : "unconfigured",
  );
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) {
      // Sign-in is not configured in this environment. The initial status
      // above already reflects that, so there is nothing to synchronise.
      return;
    }

    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      const sessionEmail = data.session?.user.email ?? null;
      setEmail(sessionEmail);
      setStatus(data.session ? "in" : "out");
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!active) return;
      setEmail(session?.user.email ?? null);
      setStatus(session ? "in" : "out");
    });

    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, []);

  return { status, email };
}
