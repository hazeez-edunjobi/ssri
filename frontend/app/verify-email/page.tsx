"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Mail } from "lucide-react";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { FormAlert } from "@/components/auth/fields";
import { getSupabase, supabaseConfig } from "@/lib/supabase";

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-mist" />}>
      <VerifyEmail />
    </Suspense>
  );
}

function VerifyEmail() {
  const params = useSearchParams();
  const email = params.get("email")?.trim() || "";
  const nextPath = params.get("next") || "/workspace";
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sentAt, setSentAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const configured = supabaseConfig().configured;
  const remaining = sentAt ? Math.max(0, 30 - Math.floor((now - sentAt) / 1000)) : 0;

  useEffect(() => {
    if (!sentAt || remaining === 0) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [sentAt, remaining]);

  async function resend() {
    if (!email) {
      setError("We don't have an email address to resend to.");
      return;
    }
    const supabase = getSupabase();
    if (!supabase) {
      setError("Sign-in is not configured in this environment.");
      return;
    }
    setBusy(true);
    setError(null);
    const { error: authError } = await supabase.auth.resend({
      type: "signup",
      email,
      options: { emailRedirectTo: `${window.location.origin}/login?next=${encodeURIComponent(nextPath)}` },
    });
    setBusy(false);
    if (authError) {
      setError(authError.message);
      return;
    }
    setSentAt(Date.now());
    setNow(Date.now());
  }

  return (
    <AuthLayout
      panelTitle="Confirm your email"
      panelBody="The link in that message opens your account. It usually arrives within a minute."
      image="farmland"
      formTitle="Check your inbox"
      formHelper={email ? `We sent a confirmation link to ${email}.` : "We sent a confirmation link to your email."}
      align="center"
      icon={<Mail className="mx-auto h-12 w-12 text-canopy" aria-hidden />}
    >
      <div className="text-center">
        <button
          type="button"
          className="font-body text-sm font-semibold text-canopy disabled:cursor-not-allowed disabled:text-stone"
          disabled={busy || remaining > 0 || !configured || !email}
          onClick={() => void resend()}
        >
          {busy ? "Sending…" : remaining > 0 ? `Resend email in ${remaining}s` : "Resend email"}
        </button>
        {error ? <FormAlert>{error}</FormAlert> : null}
        <p className="mt-4 font-body text-sm leading-[1.5] text-stone">
          <Link href={`/signup?next=${encodeURIComponent(nextPath)}`} className="font-semibold text-canopy">
            Use a different email
          </Link>
        </p>
      </div>
    </AuthLayout>
  );
}
