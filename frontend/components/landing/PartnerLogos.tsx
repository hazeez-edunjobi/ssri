"use client";

import {
  Compass,
  FlaskConical,
  Landmark,
  Mountain,
  Radar,
  Shield,
} from "lucide-react";
import { IconOrb } from "@/components/visuals/IconOrb";

const partners = [
  { name: "Continental Geoscience", icon: Compass, tone: "emerald" as const },
  { name: "Meridian Infrastructure", icon: Landmark, tone: "emerald" as const },
  { name: "Openground Survey", icon: Radar, tone: "cyan" as const },
  { name: "Basalt Analytics", icon: Mountain, tone: "emerald" as const },
  { name: "Terra Nova Labs", icon: FlaskConical, tone: "cyan" as const },
  { name: "Fault Line Partners", icon: Shield, tone: "emerald" as const },
];

export function PartnerLogos() {
  return (
    <section className="bg-mist px-4 py-16 md:px-8">
      <div className="mx-auto max-w-[1200px]">
        <p className="text-center text-[11px] font-bold uppercase tracking-[0.14em] text-stone">
          Trusted by geoscience &amp; infrastructure partners
        </p>
        <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-6">
          {partners.map(({ name, icon, tone }) => (
            <div
              key={name}
              className="flex flex-col items-center gap-3 rounded-2xl border border-meadow bg-chalk px-3 py-5 shadow-soft transition hover:border-leaf/40"
            >
              <IconOrb icon={icon} size="sm" tone={tone} float={false} />
              <span className="text-center font-display text-[11px] font-semibold leading-tight tracking-tight text-stone">
                {name}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
