"use client";

import { useRef } from "react";
import {
  Box,
  Brain,
  Download,
  MapPin,
  Satellite,
  Sparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { IconOrb } from "@/components/visuals/IconOrb";
import { useScrollStagger } from "@/components/animations/ParallaxWrapper";

const steps: { n: string; icon: LucideIcon; title: string; body: string }[] = [
  {
    n: "01",
    icon: MapPin,
    title: "Pick a place",
    body: "Click the map or draw an area — a plot, a town edge, or a hillside you care about.",
  },
  {
    n: "02",
    icon: Satellite,
    title: "Gather Earth pictures",
    body: "We pull satellite views, elevation, and deep-ground signals for that place automatically.",
  },
  {
    n: "03",
    icon: Sparkles,
    title: "Read the land clues",
    body: "Slope, moisture, green cover, and other clues are measured for every small patch of ground.",
  },
  {
    n: "04",
    icon: Box,
    title: "Stack everything together",
    body: "All those clues line up into one clear picture of the land — ready for the model.",
  },
  {
    n: "05",
    icon: Brain,
    title: "Score the risk",
    body: "The model estimates landslide, sinkhole, and settling chances in plain language.",
  },
  {
    n: "06",
    icon: Download,
    title: "Share the answer",
    body: "Get a map and summary you can take to a meeting, a plan review, or a neighbor.",
  },
];

export function HowItWorks() {
  const ref = useRef<HTMLDivElement>(null);
  useScrollStagger(ref, ".step-card");

  return (
    <div className="mx-auto max-w-[1200px] rounded-3xl border border-black/10 bg-chalk p-6 md:p-8">
      <h2 className="font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-bark min-[641px]:text-[40px]">
        How it works
      </h2>
      <p className="mt-3 max-w-md text-[15px] leading-relaxed text-stone">
        Six simple steps from a map click to a clear picture of ground risk.
      </p>

      <div ref={ref} className="mt-10 grid gap-4 md:grid-cols-3">
        {steps.map((s) => (
          <div
            key={s.n}
            className="step-card rounded-2xl border border-meadow bg-mist p-6 transition-colors hover:border-leaf/50"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-leaf">{s.n}</span>
              <IconOrb icon={s.icon} size="sm" tone="emerald" float={false} />
            </div>
            <h3 className="mt-3 font-display text-lg font-semibold text-bark">
              {s.title}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-stone">{s.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
