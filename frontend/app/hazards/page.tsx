import type { Metadata } from "next";
import { SiteShell } from "@/components/layout/SiteShell";
import { Reveal } from "@/components/animations/Reveal";
import { PageHeader } from "@/components/pages/PageHeader";
import { Card } from "@/components/ui/Card";
import { MediaFallback } from "@/components/visuals/MediaFallback";
import { IconOrbStatic } from "@/components/visuals/IconOrbStatic";
import { Button } from "@/components/ui/Button";

export const metadata: Metadata = {
  title: "Hazards",
  description:
    "Plain-language guides to landslide, sinkhole, and ground-settling risk.",
};

const hazards = [
  {
    id: "subsidence",
    icon: "activity" as const,
    unsplash: "terrain" as const,
    title: "Ground settling",
    summary:
      "When land slowly sinks — from soft soils, water pumping, or old mining — buildings and roads can crack over time.",
    indicators: [
      "Stress in green cover near towns",
      "Valley and relief patterns",
      "Density clues from gravity maps",
    ],
    output: "A settling score with a clear confidence range.",
  },
  {
    id: "landslide",
    icon: "mountain" as const,
    unsplash: "geology" as const,
    title: "Landslides",
    summary:
      "Steep or wet slopes can move after heavy rain. SSRI highlights hillsides that need a closer look.",
    indicators: [
      "How steep and curved the slope is",
      "Where water tends to gather",
      "Soil and rock surface clues",
    ],
    output: "A map of landslide chance across the area.",
  },
  {
    id: "liquefaction",
    icon: "droplets" as const,
    unsplash: "landscape" as const,
    title: "Soft, wet ground",
    summary:
      "Some soils can lose strength when shaken or saturated — especially low, wet places near rivers and coasts.",
    indicators: [
      "Low elevation and drainage patterns",
      "Surface moisture signatures",
      "Sediment thickness clues",
    ],
    output: "A soft-ground potential index for planning talks.",
  },
];

export default function HazardsPage() {
  return (
    <SiteShell>
      <main className="bg-mist">
        <PageHeader
          eyebrow="Hazards"
          title="Understand what can go wrong underfoot"
          description="SSRI looks at three kinds of ground trouble — explained in everyday words, so anyone can follow along."
          visual="hazards"
        />

        <Reveal>
        <section className="space-y-8 px-4 py-20 sm:px-6">
          {hazards.map((hazard) => (
            <article
              key={hazard.id}
              id={hazard.id}
              className="mx-auto max-w-[1200px] scroll-mt-28"
            >
              <Card className="overflow-hidden p-0">
                <div className="grid md:grid-cols-2">
                  <div className="p-8 md:p-10">
                    <IconOrbStatic
                      name={hazard.icon}
                      size="sm"
                      tone="emerald"
                      float={false}
                    />
                    <h2 className="mt-4 font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-bark min-[641px]:text-[40px]">
                      {hazard.title}
                    </h2>
                    <p className="mt-6 max-w-[70ch] font-body text-[17px] font-normal leading-[1.6] text-bark/70">
                      {hazard.summary}
                    </p>
                    <ul className="mt-6 space-y-2">
                      {hazard.indicators.map((item) => (
                        <li
                          key={item}
                          className="flex items-start gap-2 text-sm text-bark/85"
                        >
                          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-leaf" />
                          {item}
                        </li>
                      ))}
                    </ul>
                    <p className="mt-6 text-[12px] font-semibold text-moss">
                      Output: {hazard.output}
                    </p>
                    <div className="mt-6">
                      <Button variant="outline" href="/dashboard">
                        Check on the map
                      </Button>
                    </div>
                  </div>
                  <div className="relative h-64 bg-canopy md:h-80">
                    <MediaFallback
                      alt={`${hazard.title} land visual`}
                      unsplash={hazard.unsplash}
                      className="absolute inset-0"
                    />
                    <div className="absolute left-6 top-6">
                      <IconOrbStatic
                        name={hazard.icon}
                        size="md"
                        tone="emerald"
                      />
                    </div>
                  </div>
                </div>
              </Card>
            </article>
          ))}
        </section>
        </Reveal>
      </main>
    </SiteShell>
  );
}
