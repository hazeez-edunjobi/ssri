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

function passwordRules(password: string) {
  return [
    { id: "length", label: "12 to 20 characters", ok: password.length >= 12 && password.length <= 20 },
    { id: "upper", label: "An uppercase letter", ok: /[A-Z]/.test(password) },
    { id: "lower", label: "A lowercase letter", ok: /[a-z]/.test(password) },
    { id: "number", label: "A number", ok: /\d/.test(password) },
    { id: "symbol", label: "A symbol", ok: /[^A-Za-z0-9]/.test(password) },
  ];
}

export default function SignupPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-soil" />}>
      <SignupForm />
    </Suspense>
  );
}

function SignupForm() {
  const router = useRouter();
  const params = useSearchParams();
  const nextPath = params.get("next") || "/workspace";
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [touched, setTouched] = useState({ name: false, email: false, password: false });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const configured = supabaseConfig().configured;

  const rules = passwordRules(password);
  const emailOk = EMAIL.test(email.trim());
  const nameOk = displayName.trim().length >= 2;
  const passwordOk = rules.every((rule) => rule.ok);
  const formOk = configured && emailOk && nameOk && passwordOk;
  const activeStep: 1 | 2 | 3 = !emailOk || !passwordOk ? 1 : !nameOk ? 2 : 3;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched({ name: true, email: true, password: true });
    if (!formOk) return;
    const supabase = getSupabase();
    if (!supabase) return;
    setBusy(true);
    setError(null);
    const { data, error: authError } = await supabase.auth.signUp({
      email: email.trim(),
      password,
      options: { data: { display_name: displayName.trim() } },
    });
    setBusy(false);
    if (authError) {
      setError(authError.message);
      return;
    }
    if (data.session) {
      router.replace(nextPath);
      return;
    }
    setMessage("Account created. Check your email if confirmation is required, then log in.");
  }

  return (
    <AuthScreen
      activeStep={message ? 3 : activeStep}
      kicker="Join SSRI"
      title="Start your journey"
      subtitle="Follow these steps to set up your account and check the ground."
    >
      <form onSubmit={onSubmit} className="w-full" noValidate>
        <h1 className="text-center font-body text-[28px] font-medium text-bark">Join us</h1>
        {!configured && (
          <p className="mt-4 text-center text-sm text-canopy" role="status">
            Sign-in is not configured in this environment.
          </p>
        )}

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className={authLabelClass} htmlFor="signup-email">
              Email
            </label>
            <input
              id="signup-email"
              className={authFieldClass}
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              aria-invalid={touched.email && !emailOk}
              onBlur={() => setTouched((current) => ({ ...current, email: true }))}
              onChange={(event) => setEmail(event.target.value)}
            />
            {touched.email && !emailOk && <p className={authErrorClass}>Enter a valid email address.</p>}
          </div>
          <div className="sm:col-span-2">
            <label className={authLabelClass} htmlFor="signup-name">
              Full name
            </label>
            <input
              id="signup-name"
              className={authFieldClass}
              autoComplete="name"
              placeholder="Ada Okonkwo"
              value={displayName}
              aria-invalid={touched.name && !nameOk}
              onBlur={() => setTouched((current) => ({ ...current, name: true }))}
              onChange={(event) => setDisplayName(event.target.value)}
            />
            {touched.name && !nameOk && <p className={authErrorClass}>Enter the name we should show on your account.</p>}
          </div>
        </div>

        <div className="mt-4">
          <label className={authLabelClass} htmlFor="signup-password">
            Password
          </label>
          <div className="relative">
            <input
              id="signup-password"
              className={`${authFieldClass} pr-12`}
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              placeholder="Create a password"
              value={password}
              aria-invalid={touched.password && !passwordOk}
              aria-describedby="signup-password-rules"
              onBlur={() => setTouched((current) => ({ ...current, password: true }))}
              onChange={(event) => setPassword(event.target.value)}
            />
            <button
              type="button"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-stone"
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
              onClick={() => setShowPassword((current) => !current)}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          <ul id="signup-password-rules" className="mt-2 space-y-0.5 text-[11px]">
            {rules.map((rule) => (
              <li key={rule.id} className={rule.ok ? "text-moss" : "text-stone"}>
                {rule.ok ? "Met" : "Needs"}: {rule.label}
              </li>
            ))}
          </ul>
        </div>

        {error && (
          <p className="mt-3 text-[11px] font-medium text-canopy" role="alert">
            {error}
          </p>
        )}
        {message && (
          <p className="mt-3 text-sm text-moss" role="status">
            {message}
          </p>
        )}

        <button className={`${authButtonClass} mt-5`} type="submit" disabled={!formOk || busy}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
          {busy ? "Creating account…" : "Continue"}
        </button>

        <p className="mt-4 text-center text-[13px] text-stone">
          Already have an account?{" "}
          <Link href={`/login?next=${encodeURIComponent(nextPath)}`} className="font-semibold text-moss">
            Log in
          </Link>
        </p>
        <p className="mt-6 text-center text-[11px] leading-relaxed text-stone">
          By signing up you agree to use SSRI for ground-risk checks on the places you care about.
        </p>
      </form>
    </AuthScreen>
  );
}
