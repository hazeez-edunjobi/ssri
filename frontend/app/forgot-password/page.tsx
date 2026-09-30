"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { Loader2 } from "lucide-react";
import {
  AuthScreen,
  authButtonClass,
  authErrorClass,
  authFieldClass,
  authLabelClass,
} from "@/components/auth/AuthScreen";
import { getSupabase, supabaseConfig } from "@/lib/supabase";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [touched, setTouched] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const configured = supabaseConfig().configured;
  const emailOk = EMAIL.test(email.trim());

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!configured || !emailOk) return;
    const supabase = getSupabase();
    if (!supabase) return;
    setBusy(true);
    setError(null);
    const { error: authError } = await supabase.auth.resetPasswordForEmail(email.trim(), {
      redirectTo: `${window.location.origin}/login`,
    });
    setBusy(false);
    if (authError) {
      setError(authError.message);
      return;
    }
    setMessage("If that email is registered, a reset link is on its way.");
  }

  return (
    <AuthScreen
      activeStep={1}
      kicker="Reset access"
      title="Get back into your account"
      subtitle="We will email a link if this address already belongs to an SSRI account."
    >
      <form onSubmit={onSubmit} className="w-full" noValidate>
        <h1 className="text-center font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-bark">Reset password</h1>
        {!configured && (
          <p className="mt-4 text-center text-sm text-canopy" role="status">
            Sign-in is not configured in this environment.
          </p>
        )}
        <div className="mt-6">
          <label className={authLabelClass} htmlFor="reset-email">
            Email
          </label>
          <input
            id="reset-email"
            className={authFieldClass}
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            aria-invalid={touched && !emailOk}
            onChange={(event) => setEmail(event.target.value)}
          />
          {touched && !emailOk && <p className={authErrorClass}>Enter a valid email address.</p>}
        </div>
        {error && (
          <p className="mt-4 font-body text-sm font-medium leading-[1.5] text-canopy" role="alert">
            {error}
          </p>
        )}
        {message && (
          <p className="mt-4 font-body text-sm leading-[1.5] text-moss" role="status">
            {message}
          </p>
        )}
        <button className={`${authButtonClass} mt-8`} type="submit" disabled={!configured || !emailOk || busy}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
          {busy ? "Sending…" : "Continue"}
        </button>
        <p className="mt-4 text-center font-body text-sm leading-[1.5] text-stone">
          <Link href="/login" className="font-semibold text-moss">
            Back to log in
          </Link>
        </p>
      </form>
    </AuthScreen>
  );
}
