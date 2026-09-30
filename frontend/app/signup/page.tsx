"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";
import { Check } from "lucide-react";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { AuthField, AuthSubmit, FormAlert, PasswordField, focusField, passwordRules } from "@/components/auth/fields";
import { getSupabase, supabaseConfig } from "@/lib/supabase";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function SignupPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-mist" />}>
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
  const [accepted, setAccepted] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [touched, setTouched] = useState({ name: false, email: false, password: false, terms: false });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const configured = supabaseConfig().configured;

  const rules = passwordRules(password);
  const emailOk = EMAIL.test(email.trim());
  const nameOk = displayName.trim().length >= 2;
  const passwordOk = rules.every((rule) => rule.ok);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched({ name: true, email: true, password: true, terms: true });
    setError(null);
    if (!configured) {
      setError("Sign-in is not configured in this environment.");
      return;
    }
    if (!nameOk) {
      focusField("signup-name");
      return;
    }
    if (!emailOk) {
      focusField("signup-email");
      return;
    }
    if (!passwordOk) {
      focusField("signup-password");
      return;
    }
    if (!accepted) {
      focusField("signup-terms");
      return;
    }
    const supabase = getSupabase();
    if (!supabase) {
      setError("Sign-in is not configured in this environment.");
      return;
    }
    setBusy(true);
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
    router.push(`/verify-email?email=${encodeURIComponent(email.trim())}&next=${encodeURIComponent(nextPath)}`);
  }

  return (
    <AuthLayout
      panelTitle="Start reading the ground"
      panelBody="Create an account, then check a place before you build on it."
      bullets={["Clear ground scores", "Fast map checks", "Honest confidence"]}
      image="fields"
      formTitle="Create account"
      formHelper="Tell us who you are. We'll send a confirmation if this project requires one."
      step={1}
    >
      <form onSubmit={onSubmit} noValidate>
        {/* Google sign-in slot: render a button and an "or" divider here when OAuth is added. */}
        <AuthField
          id="signup-name"
          label="Name"
          autoComplete="name"
          placeholder="Ada Okonkwo"
          value={displayName}
          error={touched.name && !nameOk ? "Enter the name we should show on your account." : undefined}
          onBlur={() => setTouched((current) => ({ ...current, name: true }))}
          onChange={(event) => setDisplayName(event.target.value)}
        />
        <AuthField
          id="signup-email"
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          error={touched.email && !emailOk ? "That email doesn't look right" : undefined}
          onBlur={() => setTouched((current) => ({ ...current, email: true }))}
          onChange={(event) => setEmail(event.target.value)}
        />
        <PasswordField
          id="signup-password"
          label="Password"
          autoComplete="new-password"
          placeholder="Create a password"
          value={password}
          shown={showPassword}
          onToggle={() => setShowPassword((current) => !current)}
          aria-describedby="signup-password-rules"
          error={touched.password && !passwordOk ? "Choose a password that meets every rule." : undefined}
          onBlur={() => setTouched((current) => ({ ...current, password: true }))}
          onChange={(event) => setPassword(event.target.value)}
        />
        <ul id="signup-password-rules" className="mt-2 space-y-1 font-body text-xs leading-[1.5]">
          {rules.map((rule) => (
            <li
              key={rule.id}
              aria-label={rule.ok ? `Met: ${rule.label}` : `Not yet met: ${rule.label}`}
              className={`flex items-center gap-2 ${rule.ok ? "text-moss" : "text-stone"}`}
            >
              <Check className={`h-3.5 w-3.5 ${rule.ok ? "opacity-100" : "opacity-30"}`} aria-hidden />
              <span>{rule.label}</span>
            </li>
          ))}
        </ul>
        <div className="mt-4">
          <label className="flex items-start gap-3 font-body text-sm leading-[1.5] text-bark" htmlFor="signup-terms">
            <input
              id="signup-terms"
              type="checkbox"
              className="mt-1 h-4 w-4 accent-canopy"
              checked={accepted}
              aria-invalid={touched.terms && !accepted}
              aria-describedby={touched.terms && !accepted ? "signup-terms-error" : undefined}
              onChange={(event) => setAccepted(event.target.checked)}
            />
            <span>I agree to use SSRI for ground-risk checks on the places I care about.</span>
          </label>
          {touched.terms && !accepted ? (
            <p id="signup-terms-error" className="mt-2 font-body text-sm leading-[1.5] text-red-700" role="alert">
              Confirm this before creating an account.
            </p>
          ) : null}
        </div>
        {error ? <FormAlert>{error}</FormAlert> : null}
        <AuthSubmit busy={busy} busyLabel="Creating account…" disabled={!configured}>
          Create account
        </AuthSubmit>
        <p className="mt-4 font-body text-sm leading-[1.5] text-stone">
          Already have an account?{" "}
          <Link href={`/login?next=${encodeURIComponent(nextPath)}`} className="font-semibold text-canopy">
            Log in
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}
