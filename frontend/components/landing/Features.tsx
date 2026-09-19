"use client";

import { useRef } from "react";
import { Globe2, Layers, ShieldCheck, Zap } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { GlassPanel } from "@/components/visuals/GlassPanel";
import { IconOrb } from "@/components/visuals/IconOrb";
import { useScrollStagger } from "@/components/animations/ParallaxWrapper";

const features = [
  {
    icon: Globe2,
    title: "Global Coverage",
    body: "Assess any coordinate on Earth using harmonized satellite, terrain, and geophysical inputs.",
  },
  {
    icon: Layers,
    title: "13-Channel Tensor",
    body: "Every pixel carries aligned elevation, spectral, and subsurface indicators in one reproducible stack.",
  },
  {
    icon: ShieldCheck,
    title: "Explainable Uncertainty",
    body: "Hazard scores ship with credible intervals so engineers know how much to trust each prediction.",
  },
  {
    icon: Zap,
    title: "API-First Delivery",
    body: "Stream hazard probabilities into GIS, CAD, insurance, or planning tools via REST endpoints.",
  },
];

export function Features() {
  const ref = useRef<HTMLDivElement>(null);
  useScrollStagger(ref, ".feature-card");

  return (
    <section className="px-4 py-24 md:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-8 md:grid-cols-[minmax(0,320px)_1fr]">
          <h2 className="font-display text-3xl font-semibold leading-tight tracking-tight text-bark md:text-4xl">
            Built for Geospatial Risk Teams
          </h2>
          <p className="max-w-xl text-[15px] leading-relaxed text-stone">
            SSRI combines Earth observation science with production ML infrastructure —
            no missing assets, no brittle pipelines, just intelligence you can deploy.
          </p>
        </div>

        <div ref={ref} className="mt-10 grid gap-5 md:grid-cols-2">
          {features.map(({ icon, title, body }) => (
            <Card
              key={title}
              tone="core"
              className="feature-card relative overflow-hidden p-6 md:p-8"
            >
              <GlassPanel
                gradient="from-leaf/15 via-transparent to-moss/10"
                glow={false}
                className="absolute -right-8 -top-8 h-32 w-32 opacity-60"
              />
              <IconOrb icon={icon} size="sm" tone="emerald" float={false} />
              <h3 className="relative mt-4 font-display text-xl font-semibold text-bark">
                {title}
              </h3>
              <p className="relative mt-2 text-sm leading-relaxed text-stone">
                {body}
              </p>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
