"use client";

import Link from "next/link";
import { BrandLockup } from "@/components/landing/BrandMark";
import { FOOTER_COLUMNS, LOGIN_HREF, SIGNUP_HREF } from "@/lib/navigation";

export function Footer({ cta = true }: { cta?: boolean }) {
  return (
    <footer>
      {cta ? <section className="bg-canopy px-4 py-16 text-center md:px-8">
        <h2 className="mx-auto max-w-[18ch] text-balance font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-chalk min-[641px]:text-[40px]">
          Build on land you understand
        </h2>
        <p className="mx-auto mt-6 max-w-[70ch] font-body text-[17px] font-normal leading-[1.6] text-chalk/70">
          Take one minute. Pick a place on the map. See a friendly risk picture
          of the ground beneath.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link
            href={LOGIN_HREF}
            className="inline-flex min-h-12 items-center rounded-xl border border-black/10 bg-sprout px-6 py-4 font-body text-[17px] font-semibold leading-none text-soil transition-all duration-200 ease-[ease] hover:-translate-y-0.5 hover:bg-leaf"
          >
            Log in
          </Link>
          <Link
            href={SIGNUP_HREF}
            className="inline-flex min-h-12 items-center rounded-xl border border-white/10 px-6 py-4 font-body text-[17px] font-semibold leading-none text-chalk transition-all duration-200 ease-[ease] hover:-translate-y-0.5 hover:bg-chalk/5"
          >
            Sign up
          </Link>
        </div>
      </section> : null}

      <div className="border-t border-meadow bg-mist px-4 py-14 md:px-8">
        <div className="mx-auto max-w-[1200px]">
          <div className="grid gap-10 md:grid-cols-[1.4fr_repeat(4,1fr)]">
            <div>
              <BrandLockup />
              <p className="mt-3 max-w-xs text-sm text-stone">
                Subsurface Structural Risk Intelligence — clear maps of land
                risk for everyone.
              </p>
            </div>
            {FOOTER_COLUMNS.map((col) => (
              <div key={col.title}>
                <p className="text-[11px] font-bold uppercase tracking-widest text-stone">
                  {col.title}
                </p>
                <ul className="mt-4 space-y-2.5">
                  {col.links.map((link) => (
                    <li key={link.label}>
                      <Link
                        href={link.href}
                        className="text-sm text-bark/80 transition hover:text-moss"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="mt-14 flex flex-col items-center justify-between gap-3 border-t border-meadow pt-6 text-xs text-stone md:flex-row">
            <span>© {new Date().getFullYear()} SSRI. All rights reserved.</span>
            <span>Greener decisions start with clearer ground.</span>
          </div>
        </div>
      </div>
      <div className="h-3 bg-soil" aria-hidden />
    </footer>
  );
}
