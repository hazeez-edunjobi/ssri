"use client";

import Image from "next/image";
import { Check, MapPin } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { HERO_GEOGRAPHY_IMAGE } from "@/components/landing/Hero";
import { DASHBOARD_HREF } from "@/lib/navigation";
import { unsplashUrl, VISUAL_PRESETS, type VisualPresetKey } from "@/lib/visuals";

type PageHeaderProps = {
  eyebrow: string;
  title: string;
  description: string;
  visual?: VisualPresetKey | false;
  primaryHref?: string;
  secondaryHref?: string;
};

const CHECKS = ["Landslide", "Sinkhole", "Settling"] as const;

const HEADER_ALT: Record<VisualPresetKey, string> = {
  hero: HERO_GEOGRAPHY_IMAGE.alt,
  platform: "Satellite view of snow-covered ridges and green valleys",
  hazards: "Steep mountain ridges where slopes can fail",
  developers: "Analytics dashboard for reading land-risk data",
  about: "Rolling green hills under an open sky",
  infrastructure: "Green valley landscape used for planning routes",
  subsidence: "Vegetated mountain terrain where ground can settle",
};

export function PageHeader({
  eyebrow,
  title,
  description,
  visual = "platform",
  primaryHref = DASHBOARD_HREF,
  secondaryHref = "/platform#pipeline",
}: PageHeaderProps) {
  const preset = visual ? VISUAL_PRESETS[visual] : VISUAL_PRESETS.platform;
  const imageKey = preset.unsplash ?? "landscape";
  const imageAlt = visual ? HEADER_ALT[visual] : HEADER_ALT.platform;
  return (
    <section className="bg-mist px-4 py-16 sm:px-6 md:py-20">
      <div className="mx-auto grid max-w-[1200px] items-center gap-8 lg:grid-cols-2 lg:gap-16">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-meadow px-4 py-2 font-body text-sm font-semibold leading-none text-canopy">
            <MapPin className="h-4 w-4" aria-hidden />
            {eyebrow}
          </p>
          <h1 className="mt-6 max-w-[16ch] text-balance font-display text-[32px] font-semibold leading-[1.15] tracking-[-0.02em] text-bark md:text-[40px] lg:text-[48px]">
            {title}
          </h1>
          <p className="mt-6 max-w-[70ch] font-body text-[17px] font-normal leading-[1.6] text-bark/70">
            {description}
          </p>
          <div className="mt-8 flex flex-col gap-4 sm:flex-row">
            <Button
              href={primaryHref}
              className="rounded-xl bg-canopy px-6 py-4 text-[17px] text-chalk shadow-none hover:bg-soil"
            >
              Try the map
            </Button>
            <Button
              href={secondaryHref}
              variant="outline"
              className="rounded-xl border-canopy/20 px-6 py-4 text-[17px] hover:border-canopy"
            >
              See how it works
            </Button>
          </div>
          <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2">
            {CHECKS.map((item) => (
              <li key={item} className="inline-flex items-center gap-2 font-body text-sm leading-[1.5] text-bark/70">
                <Check className="h-4 w-4 text-canopy" aria-hidden />
                {item}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative pb-8 lg:pb-4">
          <div className="relative aspect-[5/4] overflow-hidden rounded-2xl">
            <Image
              src={unsplashUrl(imageKey, 1600)}
              alt={imageAlt}
              fill
              priority
              sizes="(max-width: 1024px) 100vw, 560px"
              className="object-cover object-center"
            />
          </div>
          <div
            role="img"
            aria-label="Sample result. Landslide risk is moderate, with high confidence."
            className="relative z-10 mx-4 -mt-10 rounded-lg border border-black/[0.08] bg-chalk p-4 lg:absolute lg:-bottom-4 lg:-left-4 lg:mx-0 lg:mt-0 lg:w-72"
          >
            <p className="font-body text-xs font-semibold leading-[1.4] text-stone">Sample result</p>
            <div className="mt-2 flex items-center justify-between gap-4">
              <p className="font-body text-sm font-semibold leading-[1.4] text-bark">Landslide risk</p>
              <span className="inline-flex rounded-full bg-amber-100 px-2 py-1 font-body text-xs font-semibold leading-none text-amber-800">
                Moderate
              </span>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-black/10" aria-hidden>
              <div className="h-full w-[48%] rounded-full bg-amber-600" />
            </div>
            <p className="mt-2 font-body text-xs leading-[1.4] text-stone">Confidence: high</p>
          </div>
        </div>
      </div>
    </section>
  );
}
