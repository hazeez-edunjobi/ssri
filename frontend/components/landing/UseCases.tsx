"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight, Building2, MapPinned, ShieldCheck } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { MediaFallback } from "@/components/visuals/MediaFallback";
import { IconOrb } from "@/components/visuals/IconOrb";

const cases = [
  {
    icon: Building2,
    title: "Infrastructure Planning & Engineering",
    body: "Screen foundations for roads, rail, and buildings against subsidence and terrain instability before ground is broken.",
    href: "/platform",
    unsplash: "landscape" as const,
    canopy: true,
  },
  {
    icon: ShieldCheck,
    title: "Insurance & Risk Underwriting",
    body: "Quantify subsurface hazard exposure across portfolios with calibrated probabilities and credible intervals.",
    href: "/hazards",
    unsplash: "geology" as const,
    canopy: false,
  },
  {
    icon: MapPinned,
    title: "Urban & Regional Planning",
    body: "Map city-scale susceptibility layers to guide zoning, resilience investment, and emergency preparedness.",
    href: "/dashboard",
    unsplash: "satellite" as const,
    canopy: false,
  },
];

export function UseCases() {
  return (
    <section className="px-4 py-24 md:px-8">
      <div className="mx-auto max-w-[1200px]">
        <div className="max-w-2xl">
          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-leaf">
            SSRI in Action
          </p>
          <h2 className="mt-4 font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-bark min-[641px]:text-[40px]">
            Use Cases
          </h2>
          <p className="mt-3 text-[15px] leading-relaxed text-stone">
            From individual construction sites to entire countries, SSRI gives
            engineers, planners, and insurers a shared, explainable view of what
            lies beneath.
          </p>
        </div>

        <div className="mt-10 grid gap-5 md:grid-cols-3">
          {cases.map((item) => (
            <motion.div
              key={item.title}
              whileHover={{ y: -8 }}
              transition={{ type: "spring", stiffness: 300, damping: 24 }}
            >
              <Card
                tone={item.canopy ? "canopy" : "core"}
                className="flex h-full flex-col overflow-hidden p-0"
              >
                <div className="p-6 md:p-8">
                  <IconOrb
                    icon={item.icon}
                    size="sm"
                    tone="emerald"
                    float={false}
                  />
                  <h3
                    className={`mt-5 font-display text-xl font-semibold tracking-tight ${
                      item.canopy ? "text-chalk" : "text-bark"
                    }`}
                  >
                    {item.title}
                  </h3>
                  <p
                    className={`mt-2 text-sm leading-relaxed ${
                      item.canopy ? "text-meadow/90" : "text-stone"
                    }`}
                  >
                    {item.body}
                  </p>
                  <Link
                    href={item.href}
                    className={`mt-5 inline-flex items-center gap-1.5 text-sm font-semibold ${
                      item.canopy
                        ? "text-sprout hover:text-meadow"
                        : "text-moss hover:text-leaf"
                    }`}
                  >
                    Learn more <ArrowUpRight className="h-3.5 w-3.5" />
                  </Link>
                </div>

                <div className="relative mt-auto h-48 overflow-hidden border-t border-black/10">
                  <MediaFallback
                    alt={item.title}
                    unsplash={item.unsplash}
                    className="absolute inset-0"
                    overlay="dark"
                  />
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
