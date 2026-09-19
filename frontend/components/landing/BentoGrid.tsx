"use client";

import { useRef } from "react";
import { Layers, Radio, Gauge } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { IconOrb } from "@/components/visuals/IconOrb";
import { useScrollStagger } from "@/components/animations/ParallaxWrapper";

export function BentoGrid() {
  const containerRef = useRef<HTMLDivElement>(null);
  useScrollStagger(containerRef, ".bento-card");

  return (
    <section className="bg-land-wash px-4 py-16 md:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-8 md:grid-cols-[minmax(0,320px)_1fr]">
          <h2 className="font-display text-3xl font-semibold leading-tight tracking-tight text-bark md:text-4xl">
            What is SSRI?
          </h2>
          <p className="max-w-xl text-[15px] leading-relaxed text-stone">
            SSRI looks at hills, soil, and satellite views of the land, then turns
            them into a simple risk picture — so you can see where ground may
            slide, sink, or settle before you build.
          </p>
        </div>

        <div ref={containerRef} className="mt-10 grid gap-5 md:grid-cols-3">
          <Card className="bento-card flex min-h-[280px] flex-col justify-between p-6">
            <div>
              <IconOrb icon={Layers} size="sm" tone="emerald" float={false} />
              <h3 className="mt-4 font-display text-xl font-semibold text-bark">
                Clear ground scores
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-stone">
                Every patch of land gets an easy-to-read score for landslide,
                sinkhole, and settling concern.
              </p>
            </div>
          </Card>

          <Card className="bento-card flex min-h-[280px] flex-col justify-between p-6">
            <div>
              <IconOrb icon={Radio} size="sm" tone="emerald" float={false} />
              <h3 className="mt-4 font-display text-xl font-semibold text-bark">
                Fast map checks
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-stone">
                Click a place on the map and get a result you can share with a
                team, client, or community.
              </p>
            </div>
          </Card>

          <Card className="bento-card flex min-h-[280px] flex-col justify-between p-6">
            <div>
              <IconOrb icon={Gauge} size="sm" tone="emerald" float={false} />
              <h3 className="mt-4 font-display text-xl font-semibold text-bark">
                Honest confidence
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-stone">
                We show how sure the model is — so decisions stay grounded, not
                oversold.
              </p>
            </div>
          </Card>
        </div>
      </div>
    </section>
  );
}
