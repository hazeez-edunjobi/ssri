"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import {
  AuthScreen,
  authButtonClass,
  authErrorClass,
  authFieldClass,
  authLabelClass,
} from "@/components/auth/AuthScreen";
import { getSupabase, supabaseConfig } from "@/lib/supabase";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-soil" />}>
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
  const formOk = configured && emailOk && password.length > 0;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!formOk) return;
    const supabase = getSupabase();
    if (!supabase) return;
    setBusy(true);
    setError(null);
    const { error: authError } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    });
    setBusy(false);
    if (authError) {
      setError(authError.message);
      return;
    }
    router.replace(nextPath);
  }

  return (
    <AuthScreen
      activeStep={1}
      kicker="Welcome back"
      title="Pick up where you left off"
      subtitle="Log in to open your datasets, training runs, and the assessment map."
    >
      <form onSubmit={onSubmit} className="w-full" noValidate>
        <h1 className="text-center font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-bark">Log in</h1>
        {!configured && (
          <p className="mt-4 text-center text-sm text-canopy" role="status">
            Sign-in is not configured in this environment.
          </p>
        )}
        <div className="mt-6">
          <label className={authLabelClass} htmlFor="login-email">
            Email
          </label>
          <input
            id="login-email"
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
        <div className="mt-4">
          <label className={authLabelClass} htmlFor="login-password">
            Password
          </label>
          <div className="relative">
            <input
              id="login-password"
              className={`${authFieldClass} pr-12`}
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="Your password"
              value={password}
              aria-invalid={touched && password.length === 0}
              onChange={(event) => setPassword(event.target.value)}
            />
            <button
              type="button"
              className="absolute right-4 top-1/2 -translate-y-1/2 text-stone"
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
              onClick={() => setShowPassword((current) => !current)}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>
        {error && (
          <p className="mt-4 font-body text-sm font-medium leading-[1.5] text-canopy" role="alert">
            {error}
          </p>
        )}
        <button className={`${authButtonClass} mt-8`} type="submit" disabled={!formOk || busy}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
          {busy ? "Signing in…" : "Continue"}
        </button>
        <p className="mt-4 text-center font-body text-sm leading-[1.5] text-stone">
          New here?{" "}
          <Link href={`/signup?next=${encodeURIComponent(nextPath)}`} className="font-semibold text-moss">
            Create account
          </Link>
        </p>
        <p className="mt-4 text-center font-body text-sm leading-[1.5]">
          <Link href="/forgot-password" className="font-semibold text-moss">
            Forgot password
          </Link>
        </p>
      </form>
    </AuthScreen>
  );
}
