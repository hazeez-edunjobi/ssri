"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  LOCAL_ACCEPTANCE_EMAIL,
  localAcceptanceSessionAllowed,
} from "@/lib/localAcceptanceSession";
import {
  canAccessOperatorUi,
  configuredOperatorApiKey,
  operatorAccessDeniedReason,
} from "@/lib/operatorAccess";
import { platformGet } from "@/lib/platformApi";
import { getSupabase, supabaseConfig } from "@/lib/supabase";

type Me = { profile: { role: string } };

/**
 * Gate Stage 2.5 operator / release-shell UIs.
 * Allows: local acceptance (dev), configured operator API key, or platform admin.
 * Backend permissions remain authoritative for mutations.
 */
export function RequireOperatorAccess({
  children,
  nextPath,
}: {
  children: React.ReactNode;
  nextPath: string;
}) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [allowed, setAllowed] = useState(false);
  const [deniedReason, setDeniedReason] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const configured = supabaseConfig().configured;
  const localAcceptance = localAcceptanceSessionAllowed();
  const hasApiKey = Boolean(configuredOperatorApiKey());

  useEffect(() => {
    let cancelled = false;

    async function resolve() {
      if (localAcceptance) {
        if (!cancelled) {
          setEmail(LOCAL_ACCEPTANCE_EMAIL);
          setAllowed(true);
          setDeniedReason(null);
          setReady(true);
        }
        return;
      }

      if (hasApiKey) {
        if (!cancelled) {
          setAllowed(true);
          setDeniedReason(null);
          setReady(true);
        }
        return;
      }

      const supabase = getSupabase();
      if (!supabase) {
        if (!cancelled) {
          setAllowed(false);
          setDeniedReason(
            "Sign-in is not configured and no operator API key is set.",
          );
          setReady(true);
        }
        return;
      }

      const { data } = await supabase.auth.getSession();
      if (!data.session) {
        router.replace(`/login?next=${encodeURIComponent(nextPath)}`);
        return;
      }

      let role: string | null = null;
      try {
        const me = await platformGet<Me>("/me");
        role = me.profile.role;
      } catch {
        role = null;
      }

      const input = {
        localAcceptance: false,
        hasOperatorApiKey: false,
        hasSession: true,
        platformRole: role,
      };
      const ok = canAccessOperatorUi(input);
      if (!cancelled) {
        setEmail(data.session.user.email ?? null);
        setAllowed(ok);
        setDeniedReason(ok ? null : operatorAccessDeniedReason(input));
        setReady(true);
      }
    }

    void resolve();
    return () => {
      cancelled = true;
    };
  }, [hasApiKey, localAcceptance, nextPath, router]);

  if (!configured && !hasApiKey && !localAcceptance) {
    return (
      <main className="min-h-screen bg-mist px-6 py-16 text-bark" data-testid="operator-access-unconfigured">
        <div className="mx-auto max-w-lg rounded-2xl border border-meadow bg-chalk p-6 text-sm">
          <h1 className="font-display text-xl">Operator access is not configured</h1>
          <p className="mt-3 text-stone">
            Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY, or configure
            NEXT_PUBLIC_SSRI_API_KEY for machine operator access.
          </p>
          <Link href="/login" className="mt-4 inline-block font-semibold text-moss">
            Go to login
          </Link>
        </div>
      </main>
    );
  }

  if (!ready) {
    return (
      <main className="min-h-screen bg-mist px-6 py-16 text-sm text-stone" data-testid="operator-access-loading">
        Checking operator access…
      </main>
    );
  }

  if (!allowed) {
    return (
      <main className="min-h-screen bg-mist px-6 py-16 text-bark" data-testid="operator-access-denied">
        <div className="mx-auto max-w-lg rounded-2xl border border-meadow bg-chalk p-6 text-sm">
          <h1 className="font-display text-xl">Operator access required</h1>
          <p className="mt-3 text-stone">{deniedReason}</p>
          {email && <p className="mt-2 font-mono text-xs text-stone">Signed in as {email}</p>}
          <div className="mt-4 flex flex-wrap gap-3">
            <Link href="/workspace" className="font-semibold text-moss">
              Workspace
            </Link>
            <Link href="/dashboard" className="font-semibold text-moss">
              Assessment
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return <>{children}</>;
}
