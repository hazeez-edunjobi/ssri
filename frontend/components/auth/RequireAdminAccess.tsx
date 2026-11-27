"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { localAcceptanceSessionAllowed } from "@/lib/localAcceptanceSession";
import { canAccessAdminUi } from "@/lib/operatorAccess";
import { platformGet } from "@/lib/platformApi";
import { getSupabase, supabaseConfig } from "@/lib/supabase";
import { PlatformShell } from "@/components/platform/PlatformShell";
import { Loader } from "@/components/ui/loader";

type Me = { profile: { role: string; email?: string; display_name?: string } };

/**
 * Client gate for /admin. Backend admin checks remain authoritative.
 */
export function RequireAdminAccess({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [allowed, setAllowed] = useState(false);
  const [role, setRole] = useState<string | null>(null);
  const configured = supabaseConfig().configured;
  const localAcceptance = localAcceptanceSessionAllowed();

  useEffect(() => {
    let cancelled = false;

    async function resolve() {
      if (localAcceptance) {
        if (!cancelled) {
          setAllowed(false);
          setRole(null);
          setReady(true);
        }
        return;
      }

      const supabase = getSupabase();
      if (!supabase) {
        if (!cancelled) {
          setAllowed(false);
          setReady(true);
        }
        return;
      }

      const { data } = await supabase.auth.getSession();
      if (!data.session) {
        router.replace(`/login?next=${encodeURIComponent("/admin")}`);
        return;
      }

      let profileRole: string | null = null;
      try {
        const me = await platformGet<Me>("/me");
        profileRole = me.profile.role;
      } catch {
        profileRole = null;
      }

      const ok = canAccessAdminUi({
        localAcceptance: false,
        hasSession: true,
        platformRole: profileRole,
      });
      if (!cancelled) {
        setRole(profileRole);
        setAllowed(ok);
        setReady(true);
      }
    }

    void resolve();
    return () => {
      cancelled = true;
    };
  }, [localAcceptance, router]);

  if (!configured && !localAcceptance) {
    return (
      <main className="min-h-screen bg-mist px-6 py-16 text-bark" data-testid="admin-access-unconfigured">
        <div className="mx-auto max-w-lg rounded-2xl border border-meadow bg-chalk p-6 text-sm">
          <h1 className="font-display text-xl">Sign-in is not configured</h1>
          <p className="mt-3 text-stone">
            Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY before opening admin.
          </p>
        </div>
      </main>
    );
  }

  if (!ready) {
    return (
      <PlatformShell>
        <Loader
          variant="section"
          title="Checking admin access"
          description="Confirming profiles.role = admin before opening this page."
          data-testid="admin-access-loading"
        />
      </PlatformShell>
    );
  }

  if (!allowed) {
    return (
      <PlatformShell>
        <div data-testid="admin-access-denied" className="rounded-2xl border border-meadow bg-chalk p-6 text-sm">
          <h1 className="font-display text-2xl">Admin access required</h1>
          <p className="mt-3 text-stone">
            This page is limited to profiles with <code>role = admin</code> (set in the
            database, not by matching an email in the client). The API remains the
            authority for admin operations.
          </p>
          {role && (
            <p className="mt-2 font-mono text-xs text-stone">Current profile role: {role}</p>
          )}
          <Link href="/workspace" className="mt-4 inline-block font-semibold text-moss">
            Back to workspace
          </Link>
        </div>
      </PlatformShell>
    );
  }

  return <>{children}</>;
}
