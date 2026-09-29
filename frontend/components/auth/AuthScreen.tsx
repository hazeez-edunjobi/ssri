"use client";

import { BrandLockup } from "@/components/landing/BrandMark";
import { SiteShell } from "@/components/layout/SiteShell";

const STEPS = [
  { n: 1, label: "Register your account" },
  { n: 2, label: "Set up your profile" },
  { n: 3, label: "Check the ground" },
] as const;

type AuthScreenProps = {
  children: React.ReactNode;
  activeStep?: 1 | 2 | 3;
  kicker?: string;
  title?: string;
  subtitle?: string;
};

/** Split auth card. Colors are the SSRI land theme: soil, leaf, moss, chalk. */
export function AuthScreen({
  children,
  activeStep = 1,
  kicker = "Join SSRI",
  title = "Start your journey",
  subtitle = "Create an account, then check the ground before you build.",
}: AuthScreenProps) {
  return (
    <SiteShell>
    <main className="flex items-center justify-center bg-soil px-4 py-10 md:px-8 md:py-14">
      <section className="grid w-full max-w-[1100px] overflow-hidden rounded-[32px] border-4 border-chalk bg-chalk shadow-soft md:grid-cols-2 md:border-8">
        <div className="relative m-3 overflow-hidden rounded-3xl bg-[radial-gradient(ellipse_at_top_left,rgba(82,183,136,0.95),transparent_52%),radial-gradient(ellipse_at_bottom_right,#0c1a12,transparent_58%),linear-gradient(155deg,#52B788_0%,#40916C_38%,#1B4332_72%,#14261A_100%)] p-6 text-chalk md:m-4 md:flex md:min-h-[640px] md:flex-col md:p-8">
          <BrandLockup tone="light" />
          <div className="mt-8 md:mt-auto">
            <p className="inline-flex rounded-full bg-chalk/15 px-3 py-1 text-xs font-semibold text-chalk backdrop-blur">
              {kicker}
            </p>
            <h2 className="mt-4 max-w-sm font-body text-4xl font-semibold tracking-tight text-chalk md:text-5xl">
              {title}
            </h2>
            <p className="mt-3 max-w-sm text-sm leading-relaxed text-chalk/70">{subtitle}</p>
            <ol className="mt-6 hidden gap-3 md:grid md:grid-cols-3">
              {STEPS.map((step) => {
                const active = step.n === activeStep;
                return (
                  <li
                    key={step.n}
                    className={
                      active
                        ? "flex h-28 flex-col justify-between rounded-2xl bg-chalk p-3 text-bark"
                        : "flex h-28 flex-col justify-between rounded-2xl bg-chalk/15 p-3 text-chalk/60 backdrop-blur"
                    }
                  >
                    <span
                      className={
                        active
                          ? "flex h-7 w-7 items-center justify-center rounded-full bg-leaf text-xs font-semibold text-chalk"
                          : "flex h-7 w-7 items-center justify-center rounded-full border border-chalk/50 text-xs font-semibold"
                      }
                    >
                      {step.n}
                    </span>
                    <span className="text-[11px] font-semibold leading-snug">{step.label}</span>
                  </li>
                );
              })}
            </ol>
          </div>
        </div>
        <div className="flex items-center px-6 py-8 md:px-10">{children}</div>
      </section>
    </main>
    </SiteShell>
  );
}

export const authLabelClass = "mb-1.5 block text-[13px] font-semibold text-bark";

export const authFieldClass =
  "h-12 w-full rounded-xl border-0 bg-mist px-4 text-sm text-bark outline-none placeholder:text-stone/80 focus:shadow-[0_0_0_4px_rgba(64,145,108,0.22)] focus:ring-2 focus:ring-leaf";

export const authErrorClass = "mt-1 text-[11px] font-medium text-canopy";

export const authButtonClass =
  "inline-flex h-[52px] w-full items-center justify-center gap-2 rounded-xl bg-leaf text-sm font-semibold text-chalk transition duration-200 hover:-translate-y-px hover:bg-moss disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50";
