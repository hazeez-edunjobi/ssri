"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { AuthSubmit, FormAlert, PasswordField, focusField, passwordRules } from "@/components/auth/fields";
import { getSupabase, supabaseConfig } from "@/lib/supabase";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [hasSession, setHasSession] = useState(false);
  const [checked, setChecked] = useState(false);
  const configured = supabaseConfig().configured;
  const rules = passwordRules(password);
  const passwordOk = rules.every((rule) => rule.ok);
  const confirmOk = confirm.length > 0 && confirm === password;
  const met = rules.filter((rule) => rule.ok).length;

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) {
      setChecked(true);
      return;
    }
    const { data: subscription } = supabase.auth.onAuthStateChange((event, session) => {
      if (session || event === "PASSWORD_RECOVERY") setHasSession(true);
      setChecked(true);
    });
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) setHasSession(true);
      setChecked(true);
    });
    return () => subscription.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!done) return;
    const id = window.setTimeout(() => router.replace("/login"), 1600);
    return () => window.clearTimeout(id);
  }, [done, router]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    setError(null);
    if (!configured) {
      setError("Sign-in is not configured in this environment.");
      return;
    }
    if (!passwordOk) {
      focusField("new-password");
      return;
    }
    if (!confirmOk) {
      focusField("confirm-password");
      return;
    }
    const supabase = getSupabase();
    if (!supabase || !hasSession) {
      setError("This reset link is missing or has expired. Request a new one.");
      return;
    }
    setBusy(true);
    const { error: authError } = await supabase.auth.updateUser({ password });
    setBusy(false);
    if (authError) {
      setError(authError.message);
      return;
    }
    setDone(true);
  }

  return (
    <AuthLayout
      panelTitle="Choose a new password"
      panelBody="Use a password you have not used on another site. We'll send you back to log in once it is saved."
      image="geology"
      formTitle={done ? "Password updated" : "Update password"}
      formHelper={
        done
          ? "Your new password is saved. Taking you to log in."
          : "Enter it twice so a typo does not lock you out."
      }
    >
      {done ? (
        <p className="font-body text-sm leading-[1.5] text-moss" role="status">
          Password updated.{" "}
          <Link href="/login" className="font-semibold text-canopy">
            Log in
          </Link>
        </p>
      ) : (
        <form onSubmit={onSubmit} noValidate>
          {checked && configured && !hasSession ? (
            <FormAlert>This reset link is missing or has expired. Request a new one.</FormAlert>
          ) : null}
          <PasswordField
            id="new-password"
            label="New password"
            autoComplete="new-password"
            placeholder="New password"
            value={password}
            shown={showPassword}
            onToggle={() => setShowPassword((current) => !current)}
            aria-describedby="new-password-strength"
            error={touched && !passwordOk ? "Choose a password that meets every rule." : undefined}
            onChange={(event) => setPassword(event.target.value)}
          />
          <div id="new-password-strength" className="mt-2" aria-live="polite">
            <div className="flex gap-1" aria-hidden>
              {rules.map((rule) => (
                <span key={rule.id} className={`h-1 flex-1 rounded-full ${rule.ok ? "bg-moss" : "bg-black/10"}`} />
              ))}
            </div>
            <p className="mt-2 font-body text-xs leading-[1.5] text-stone">
              {met} of {rules.length} rules met
            </p>
          </div>
          <PasswordField
            id="confirm-password"
            label="Confirm password"
            autoComplete="new-password"
            placeholder="Repeat the new password"
            value={confirm}
            shown={showConfirm}
            onToggle={() => setShowConfirm((current) => !current)}
            error={touched && !confirmOk ? "Those passwords don't match." : undefined}
            onChange={(event) => setConfirm(event.target.value)}
          />
          {error ? <FormAlert>{error}</FormAlert> : null}
          <AuthSubmit busy={busy} busyLabel="Updating…" disabled={!configured}>
            Update password
          </AuthSubmit>
          <p className="mt-4 font-body text-sm leading-[1.5] text-stone">
            <Link href="/forgot-password" className="font-semibold text-canopy">
              Request a new link
            </Link>
          </p>
        </form>
      )}
    </AuthLayout>
  );
}
