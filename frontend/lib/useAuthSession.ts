"use client";

import { useEffect, useState } from "react";
import { getSupabase, supabaseConfig } from "@/lib/supabase";

export type AuthStatus = "loading" | "in" | "out" | "unconfigured";

export function useAuthSession() {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    if (!supabaseConfig().configured) {
      setStatus("unconfigured");
      return;
    }
    const supabase = getSupabase();
    if (!supabase) {
      setStatus("unconfigured");
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
