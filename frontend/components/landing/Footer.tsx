"use client";

import Link from "next/link";
import { BrandLockup } from "@/components/landing/BrandMark";
import { DASHBOARD_HREF, FOOTER_COLUMNS } from "@/lib/navigation";

export function Footer() {
  return (
    <footer>
      <section className="bg-canopy px-4 py-16 text-center md:px-8">
        <h2 className="mx-auto max-w-xl text-balance font-display text-3xl font-semibold text-chalk md:text-4xl">
          Build on land you understand
        </h2>
        <p className="mx-auto mt-3 max-w-md text-[15px] text-meadow/90">
          Take one minute. Pick a place on the map. See a friendly risk picture
          of the ground beneath.
        </p>
        <div className="mt-7">
          <Link
            href={DASHBOARD_HREF}
            className="inline-flex rounded-md bg-sprout px-6 py-3.5 text-sm font-semibold text-soil transition hover:bg-leaf"
          >
            Check a location
          </Link>
        </div>
      </section>

      <div className="border-t border-meadow bg-mist px-4 py-14 md:px-8">
        <div className="mx-auto max-w-6xl">
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
