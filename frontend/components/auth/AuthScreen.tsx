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
      <main className="flex items-center justify-center bg-soil px-4 py-16 sm:px-6 md:py-20">
        <section className="grid w-full max-w-[1200px] overflow-hidden rounded-3xl border border-white/10 bg-chalk md:grid-cols-2">
          <div className="relative m-4 overflow-hidden rounded-2xl bg-[radial-gradient(ellipse_at_top_left,rgba(82,183,136,0.95),transparent_52%),radial-gradient(ellipse_at_bottom_right,#0c1a12,transparent_58%),linear-gradient(155deg,#52B788_0%,#40916C_38%,#1B4332_72%,#14261A_100%)] p-6 text-chalk md:m-6 md:flex md:min-h-[640px] md:flex-col md:p-8">
            <BrandLockup tone="light" />
            <div className="mt-8 md:mt-auto">
              <p className="inline-flex rounded-xl bg-chalk/15 px-4 py-2 font-body text-sm font-semibold leading-[1.4] tracking-[-0.01em] text-chalk/70 backdrop-blur">
                {kicker}
              </p>
              <h2 className="mt-6 max-w-[16ch] font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-chalk min-[641px]:text-[40px]">
                {title}
              </h2>
              <p className="mt-6 max-w-[70ch] font-body text-[17px] font-normal leading-[1.6] text-chalk/70">{subtitle}</p>
              <ol className="mt-8 hidden gap-4 md:grid md:grid-cols-3">
                {STEPS.map((step) => {
                  const active = step.n === activeStep;
                  return (
                    <li
                      key={step.n}
                      className={
                        active
                          ? "flex h-32 flex-col justify-between rounded-2xl bg-chalk p-4 text-bark"
                          : "flex h-32 flex-col justify-between rounded-2xl bg-chalk/15 p-4 text-chalk/70 backdrop-blur"
                      }
                    >
                      <span
                        className={
                          active
                            ? "flex h-8 w-8 items-center justify-center rounded-lg bg-leaf text-xs font-semibold text-chalk"
                            : "flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 text-xs font-semibold"
                        }
                      >
                        {step.n}
                      </span>
                      <span className="font-body text-xs font-semibold leading-[1.4]">{step.label}</span>
                    </li>
                  );
                })}
              </ol>
            </div>
          </div>
          <div className="flex items-center px-6 py-8 md:px-8">{children}</div>
        </section>
      </main>
    </SiteShell>
  );
}

export const authLabelClass = "mb-2 block font-body text-sm font-semibold leading-[1.4] text-bark";

export const authFieldClass =
  "h-12 w-full rounded-xl border border-black/10 bg-mist px-4 font-body text-[17px] leading-[1.5] text-bark outline-none placeholder:text-stone/80 focus:shadow-[0_0_0_4px_rgba(64,145,108,0.22)] focus:ring-2 focus:ring-leaf";

export const authErrorClass = "mt-2 font-body text-xs font-medium leading-[1.5] text-canopy";

export const authButtonClass =
  "inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl border border-black/10 bg-leaf px-6 font-body text-[17px] font-semibold leading-none text-chalk transition-all duration-200 ease-[ease] hover:-translate-y-0.5 hover:bg-moss disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50";
