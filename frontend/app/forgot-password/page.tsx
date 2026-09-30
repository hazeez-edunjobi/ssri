"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { AuthField, AuthSubmit, FormAlert, focusField } from "@/components/auth/fields";
import { getSupabase, supabaseConfig } from "@/lib/supabase";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [touched, setTouched] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sentAt, setSentAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const configured = supabaseConfig().configured;
  const emailOk = EMAIL.test(email.trim());
  const remaining = sentAt ? Math.max(0, 30 - Math.floor((now - sentAt) / 1000)) : 0;

  useEffect(() => {
    if (!sentAt || remaining === 0) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [sentAt, remaining]);

  async function sendLink() {
    const supabase = getSupabase();
    if (!supabase) {
      setError("Sign-in is not configured in this environment.");
      return;
    }
    setBusy(true);
    setError(null);
    const { error: authError } = await supabase.auth.resetPasswordForEmail(email.trim(), {
      redirectTo: `${window.location.origin}/reset-password`,
    });
    setBusy(false);
    if (authError) {
      setError(authError.message);
      return;
    }
    setSent(true);
    setSentAt(Date.now());
    setNow(Date.now());
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!configured) {
      setError("Sign-in is not configured in this environment.");
      return;
    }
    if (!emailOk) {
      focusField("reset-email");
      return;
    }
    await sendLink();
  }

  return (
    <AuthLayout
      panelTitle="We'll email a link, not a password."
      panelBody="If this address belongs to an account, the reset link will arrive in a few minutes."
      image="forest"
      formTitle={sent ? "Check your inbox" : "Reset your password"}
      formHelper={
        sent
          ? `If ${email.trim()} is registered, a reset link is on its way.`
          : "Enter the email on your SSRI account."
      }
    >
      {sent ? (
        <div>
          <p className="font-body text-sm leading-[1.5] text-bark/70" role="status">
            Open the message and choose a new password. You can close this page.
          </p>
          <button
            type="button"
            className="mt-6 font-body text-sm font-semibold text-canopy disabled:cursor-not-allowed disabled:text-stone"
            disabled={busy || remaining > 0 || !configured}
            onClick={() => void sendLink()}
          >
            {busy ? "Sending…" : remaining > 0 ? `Resend in ${remaining}s` : "Resend"}
          </button>
          {error ? <FormAlert>{error}</FormAlert> : null}
          <p className="mt-4 font-body text-sm leading-[1.5] text-stone">
            <Link href="/login" className="font-semibold text-canopy">
              Back to log in
            </Link>
          </p>
        </div>
      ) : (
        <form onSubmit={onSubmit} noValidate>
          <AuthField
            id="reset-email"
            label="Email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            error={touched && !emailOk ? "That email doesn't look right" : undefined}
            onChange={(event) => setEmail(event.target.value)}
          />
          {error ? <FormAlert>{error}</FormAlert> : null}
          <AuthSubmit busy={busy} busyLabel="Sending…" disabled={!configured}>
            Send reset link
          </AuthSubmit>
          <p className="mt-4 font-body text-sm leading-[1.5] text-stone">
            <Link href="/login" className="font-semibold text-canopy">
              Back to log in
            </Link>
          </p>
        </form>
      )}
    </AuthLayout>
  );
}
