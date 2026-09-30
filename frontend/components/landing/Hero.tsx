"use client";

import Image from "next/image";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { ParallaxWrapper } from "@/components/animations/ParallaxWrapper";
import { DASHBOARD_HREF, LOGIN_HREF, SIGNUP_HREF } from "@/lib/navigation";
import { useAuthSession } from "@/lib/useAuthSession";

/** Curated Unsplash geography imagery (satellite / aerial land). */
export const HERO_GEOGRAPHY_IMAGE = {
  src: "https://images.unsplash.com/photo-1744968777239-aed5c5ff1224?auto=format&fit=crop&w=2000&q=80",
  alt: "Aerial satellite view of green mountain ranges and valleys",
  credit: "Geography stock via Unsplash (Landsat-style land cover)",
  href: "https://unsplash.com/photos/aerial-view-of-rugged-vegetated-mountain-ranges-p05veeLv9WM",
};

export function Hero() {
  const { status } = useAuthSession();
  const signedIn = status === "in";

  return (
    <section className="relative isolate overflow-hidden bg-soil">
      <div className="absolute inset-0 overflow-hidden">
        <ParallaxWrapper speed={-12} className="absolute inset-x-0 -top-16 h-[calc(100%+8rem)]">
          <div className="relative h-full w-full">
            <Image
              src={HERO_GEOGRAPHY_IMAGE.src}
              alt={HERO_GEOGRAPHY_IMAGE.alt}
              fill
              priority
              sizes="100vw"
              className="object-cover object-center"
            />
          </div>
        </ParallaxWrapper>
        <div className="absolute inset-0 bg-gradient-to-b from-soil/75 via-canopy/70 to-soil/90" />
        <div className="absolute inset-0 topo-lines opacity-40" aria-hidden />
      </div>

      <div className="relative mx-auto w-full max-w-[1200px] px-4 py-20 text-center sm:px-6 md:py-24 lg:py-[120px]">
        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mx-auto inline-flex items-center rounded-xl border border-white/10 bg-soil/50 px-4 py-2 font-body text-sm font-semibold leading-[1.4] tracking-[-0.01em] text-chalk/70 backdrop-blur"
        >
          Now available — check any place on the map
        </motion.p>

        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="mx-auto mt-8 max-w-[16ch] text-balance font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-chalk min-[420px]:text-[34px] min-[641px]:text-[40px] min-[1069px]:text-[56px]"
        >
          See the ground before you build
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12 }}
          className="mx-auto mt-6 max-w-[70ch] text-pretty font-body text-[17px] font-normal leading-[1.6] text-chalk/70"
        >
          SSRI turns satellite pictures of hills, soil, and land into a simple risk
          picture — so families, planners, and builders can spot landslide,
          sinkhole, and settling danger early, without needing a geology degree.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.18 }}
          className="mt-12 flex flex-col items-center justify-center gap-4 sm:flex-row"
        >
          {signedIn ? (
            <Link
              href={DASHBOARD_HREF}
              className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-black/10 bg-sprout px-6 py-4 font-body text-[17px] font-semibold leading-none text-soil transition-all duration-200 ease-[ease] hover:-translate-y-0.5 hover:bg-leaf"
            >
              Check a location on the map
              <ArrowRight className="h-4 w-4" />
            </Link>
          ) : (
            <>
              <Link
                href={LOGIN_HREF}
                className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-black/10 bg-sprout px-6 py-4 font-body text-[17px] font-semibold leading-none text-soil transition-all duration-200 ease-[ease] hover:-translate-y-0.5 hover:bg-leaf"
              >
                Log in to check a location
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href={SIGNUP_HREF}
                className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-white/10 bg-soil/30 px-6 py-4 font-body text-[17px] font-semibold leading-none text-chalk backdrop-blur transition-all duration-200 ease-[ease] hover:-translate-y-0.5 hover:bg-chalk/5"
              >
                Create an account
              </Link>
            </>
          )}
          <Link
            href="/platform"
            className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-white/10 bg-soil/30 px-6 py-4 font-body text-[17px] font-semibold leading-none text-chalk backdrop-blur transition-all duration-200 ease-[ease] hover:-translate-y-0.5 hover:bg-chalk/5"
          >
            How it works
          </Link>
        </motion.div>

        <p className="mx-auto mt-8 max-w-[70ch] font-body text-xs leading-[1.5] text-chalk/70">
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
