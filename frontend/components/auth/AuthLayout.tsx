import Image from "next/image";
import Link from "next/link";
import { BrandLockup } from "@/components/landing/BrandMark";
import { Footer } from "@/components/landing/Footer";
import { unsplashUrl, type UnsplashKey } from "@/lib/visuals";
import type { ReactNode } from "react";

type AuthLayoutProps = {
  panelTitle: string;
  panelBody: string;
  bullets?: string[];
  image: UnsplashKey;
  formTitle: string;
  formHelper: string;
  /** Only sign-up and onboarding pass a step. */
  step?: 1 | 2 | 3;
  align?: "start" | "center";
  icon?: ReactNode;
  children: ReactNode;
};

const STEPS = ["Account", "Profile", "Check the ground"] as const;

function StepIndicator({ step }: { step: 1 | 2 | 3 }) {
  return (
    <ol className="mt-8 flex gap-4" aria-label="Account setup">
      {STEPS.map((label, index) => {
        const number = index + 1;
        const active = number === step;
        const done = number < step;
        return (
          <li key={label} className="min-w-0 flex-1" aria-current={active ? "step" : undefined}>
            <span className={`block h-1 rounded-full ${active || done ? "bg-canopy" : "bg-black/10"}`} />
            <span
              className={`mt-2 block font-body text-sm leading-[1.5] ${
                active ? "font-semibold text-bark" : "text-bark/70"
              }`}
            >
              {label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export function AuthLayout({
  panelTitle,
  panelBody,
  bullets,
  image,
  formTitle,
  formHelper,
  step,
  align = "start",
  icon,
  children,
}: AuthLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col bg-chalk">
      <div className="lg:grid lg:min-h-screen lg:flex-1 lg:grid-cols-[minmax(0,45%)_minmax(0,55%)]">
        <aside className="relative sticky top-0 hidden h-screen overflow-hidden lg:block">
          <Image
            src={unsplashUrl(image, 1600)}
            alt=""
            fill
            priority
            className="object-cover"
            sizes="45vw"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/35 to-black/25" aria-hidden />
          <div className="relative flex h-full flex-col px-8 py-8 text-chalk xl:px-12 xl:py-12">
            <BrandLockup tone="light" />
            <div className="mt-auto max-w-[36ch] pb-8">
              <h2 className="font-display text-[32px] font-semibold leading-[1.15] tracking-[-0.02em] text-chalk xl:text-[40px]">
                {panelTitle}
              </h2>
              <p className="mt-4 font-body text-[17px] font-normal leading-[1.6] text-chalk/70">{panelBody}</p>
              {bullets && bullets.length > 0 && (
                <ul className="mt-6 space-y-2 font-body text-[17px] leading-[1.6] text-chalk/70">
                  {bullets.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </aside>

        <div className="flex min-h-screen flex-col bg-chalk">
          <header className="flex items-center justify-end px-4 py-4 sm:px-6">
            <Link href="/" className="ml-auto font-body text-sm font-semibold leading-[1.5] text-bark">
              Back to site
            </Link>
          </header>
          <div className="flex flex-1 justify-center px-4 py-8 sm:px-6 lg:py-16">
            <div className="m-auto w-full max-w-[400px]">
              <div className="mb-8 flex justify-center lg:hidden">
                <BrandLockup />
              </div>
              <div
                className={`rounded-2xl border border-black/10 p-6 lg:rounded-none lg:border-0 lg:p-0 ${
                  align === "center" ? "text-center" : ""
                }`}
              >
                {icon ? <div className="mb-4">{icon}</div> : null}
                <h1 className="font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-bark min-[641px]:text-[32px]">
                  {formTitle}
                </h1>
                <p className="mt-4 font-body text-[17px] font-normal leading-[1.6] text-bark/70">{formHelper}</p>
                {step ? <StepIndicator step={step} /> : null}
                <div className="mt-8">{children}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <Footer cta={false} />
    </div>
  );
}
