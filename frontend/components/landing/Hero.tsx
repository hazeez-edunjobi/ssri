"use client";

import Image from "next/image";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { DASHBOARD_HREF } from "@/lib/navigation";

/** Curated Unsplash geography imagery (satellite / aerial land). */
export const HERO_GEOGRAPHY_IMAGE = {
  src: "https://images.unsplash.com/photo-1744968777239-aed5c5ff1224?auto=format&fit=crop&w=2000&q=80",
  alt: "Aerial satellite view of green mountain ranges and valleys",
  credit: "Geography stock via Unsplash (Landsat-style land cover)",
  href: "https://unsplash.com/photos/aerial-view-of-rugged-vegetated-mountain-ranges-p05veeLv9WM",
};

export function Hero() {
  return (
    <section className="relative isolate overflow-hidden bg-soil">
      <div className="absolute inset-0">
        <Image
          src={HERO_GEOGRAPHY_IMAGE.src}
          alt={HERO_GEOGRAPHY_IMAGE.alt}
          fill
          priority
          sizes="100vw"
          className="object-cover object-center"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-soil/75 via-canopy/70 to-soil/90" />
        <div className="absolute inset-0 topo-lines opacity-40" aria-hidden />
      </div>

      <div className="relative mx-auto max-w-4xl px-4 py-20 text-center md:px-8 md:py-28">
        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mx-auto inline-flex items-center rounded-full border border-sprout/40 bg-soil/50 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-meadow backdrop-blur"
        >
          Now available — check any place on the map
        </motion.p>

        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="mt-7 text-balance font-display text-4xl font-semibold leading-[1.08] tracking-tight text-chalk md:text-6xl"
        >
          See the ground before you build
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12 }}
          className="mx-auto mt-5 max-w-2xl text-pretty text-base leading-relaxed text-meadow/95 md:text-lg"
        >
          SSRI turns satellite pictures of hills, soil, and land into a simple risk
          picture — so families, planners, and builders can spot landslide,
          sinkhole, and settling danger early, without needing a geology degree.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.18 }}
          className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row"
        >
          <Link
            href={DASHBOARD_HREF}
            className="inline-flex items-center gap-2 rounded-md bg-sprout px-6 py-3.5 text-sm font-semibold text-soil shadow-soft transition hover:bg-leaf"
          >
            Check a location on the map
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href="/platform"
            className="inline-flex items-center gap-2 rounded-md border border-meadow/50 bg-soil/30 px-6 py-3.5 text-sm font-semibold text-chalk backdrop-blur transition hover:border-sprout hover:bg-chalk/5"
          >
            How it works
          </Link>
        </motion.div>

        <p className="mt-8 text-[11px] text-meadow/70">
          Hero geography imagery:{" "}
          <a
            href={HERO_GEOGRAPHY_IMAGE.href}
            className="underline decoration-sprout/50 underline-offset-2 hover:text-sprout"
            target="_blank"
            rel="noreferrer"
          >
            vegetated mountain ranges (Unsplash)
          </a>
        </p>
      </div>
    </section>
  );
}
