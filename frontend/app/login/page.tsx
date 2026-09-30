"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { AuthField, AuthSubmit, FormAlert, PasswordField, focusField } from "@/components/auth/fields";
import { getSupabase, supabaseConfig } from "@/lib/supabase";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-mist" />}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const nextPath = params.get("next") || "/workspace";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const configured = supabaseConfig().configured;
  const emailOk = EMAIL.test(email.trim());
  const passwordOk = password.length > 0;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    setError(null);
    if (!configured) {
      setError("Sign-in is not configured in this environment.");
      return;
    }
    if (!emailOk) {
      focusField("login-email");
      return;
    }
    if (!passwordOk) {
      focusField("login-password");
      return;
    }
    const supabase = getSupabase();
    if (!supabase) {
      setError("Sign-in is not configured in this environment.");
      return;
    }
    setBusy(true);
    const { error: authError } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    });
    setBusy(false);
    if (authError) {
      setError(
        /invalid login credentials/i.test(authError.message)
          ? "Those details didn't match. Check the email and password and try again."
          : authError.message,
      );
      return;
    }
    router.replace(nextPath);
  }

  return (
    <AuthLayout
      panelTitle="Pick up where you left off"
      panelBody="Your datasets, training runs, and the assessment map are still here."
      image="landscape"
      formTitle="Log in"
      formHelper="Use the email and password for your SSRI account."
    >
      <form onSubmit={onSubmit} noValidate>
        {/* Google sign-in slot: render a button and an "or" divider here when OAuth is added. */}
        <AuthField
          id="login-email"
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          error={touched && !emailOk ? "That email doesn't look right" : undefined}
          onChange={(event) => setEmail(event.target.value)}
        />
        <PasswordField
          id="login-password"
          label="Password"
          labelExtra={
            <Link href="/forgot-password" className="font-body text-sm font-semibold text-canopy">
              Forgot password?
            </Link>
          }
          autoComplete="current-password"
          placeholder="Your password"
          value={password}
          shown={showPassword}
          onToggle={() => setShowPassword((current) => !current)}
          error={touched && !passwordOk ? "Enter your password" : undefined}
          onChange={(event) => setPassword(event.target.value)}
        />
        {error ? <FormAlert>{error}</FormAlert> : null}
        <AuthSubmit busy={busy} busyLabel="Logging in…" disabled={!configured}>
          Log in
        </AuthSubmit>
        <p className="mt-4 font-body text-sm leading-[1.5] text-stone">
          New to SSRI?{" "}
          <Link href={`/signup?next=${encodeURIComponent(nextPath)}`} className="font-semibold text-canopy">
            Create account
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}
