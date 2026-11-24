import type { Metadata } from "next";
import { SiteShell } from "@/components/layout/SiteShell";
import { Reveal } from "@/components/animations/Reveal";
import { PageHeader } from "@/components/pages/PageHeader";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { BentoGrid } from "@/components/landing/BentoGrid";
import { Card } from "@/components/ui/Card";
import { IconOrbStatic } from "@/components/visuals/IconOrbStatic";
import {
  AVAILABLE_API_CAPABILITIES,
  ROADMAP_API_ITEMS,
} from "@/lib/marketingApiCopy";

export const metadata: Metadata = {
  title: "Platform",
  description:
    "How SSRI turns satellite views of land into clear ground-risk answers.",
};

const stack = [
  {
    icon: "globe2" as const,
    title: "Satellite & land data",
    body: "We gather space photos, elevation, and deep-ground signals for the place you pick.",
  },
  {
    icon: "database" as const,
    title: "One clear land picture",
    body: "Everything lines up into a single view of the ground — ready to score.",
  },
  {
    icon: "cpu" as const,
    title: "Smart risk reading",
    body: "The model looks for patterns linked to slides, sinks, and settling.",
  },
  {
    icon: "server" as const,
    title: "Map & API delivery",
    body: "See results on the dashboard or pull them into your own tools.",
  },
];

export default function PlatformPage() {
  return (
    <SiteShell>
      <main className="bg-mist">
        <PageHeader
          eyebrow="Platform"
          title="How SSRI reads the land"
          description="From a map click to a friendly risk picture — built for planners, builders, and communities who need clear answers about the ground."
          visual="platform"
          secondaryHref="#pipeline"
        />

        <Reveal>
        <section id="pipeline" className="scroll-mt-24 px-4 py-20 sm:px-6">
          <HowItWorks />
        </section>
        </Reveal>

        <Reveal>
        <section className="bg-land-wash px-4 py-20 sm:px-6">
          <div className="mx-auto max-w-[1200px]">
            <h2 className="font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-bark min-[641px]:text-[40px]">
              What powers each check
            </h2>
            <p className="mt-6 max-w-[70ch] font-body text-[17px] font-normal leading-[1.6] text-bark/70">
              Real Earth data, lined up carefully, then turned into scores you can
              understand and share.
            </p>
            <div className="mt-10 grid gap-5 md:grid-cols-2">
              {stack.map(({ icon, title, body }) => (
                <Card key={title} className="relative overflow-hidden p-6">
                  <div
                    aria-hidden
                    className="pointer-events-none absolute -right-8 -top-8 h-28 w-28 rounded-full bg-leaf/15 blur-2xl"
                  />
                  <IconOrbStatic name={icon} size="sm" tone="emerald" float={false} />
                  <h3 className="mt-4 font-display text-xl font-semibold text-bark">
                    {title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-stone">{body}</p>
                </Card>
              ))}
            </div>
          </div>
        </section>
        </Reveal>

        <Reveal>
        <section className="px-4 py-20 sm:px-6">
          <div className="mx-auto max-w-[1200px] rounded-3xl border border-black/10 bg-chalk p-6 md:p-8">
            <h2 className="font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-bark min-[641px]:text-[40px]">
              For developers
            </h2>
            <p className="mt-3 max-w-xl text-[15px] text-stone">
              Plug ground-risk checks into planning tools with the live REST assessment
              route. Results remain research-ready and NOT_VALIDATED unless independently
              validated.
            </p>
            <p className="mt-6 text-xs font-semibold uppercase tracking-widest text-stone">
              Available now
            </p>
            <ul className="mt-3 space-y-3 font-mono text-[13px]" data-testid="platform-available-api">
              {AVAILABLE_API_CAPABILITIES.map((item) => (
                <li
                  key={item.route}
                  className="rounded-xl border border-meadow bg-mist px-4 py-3 text-stone"
                >
                  <span className="font-semibold text-moss">{item.route}</span>
                  <span className="mt-1 block font-sans text-xs leading-relaxed">
                    {item.summary}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-8 text-xs font-semibold uppercase tracking-widest text-stone">
              Roadmap / not shipped
            </p>
            <ul className="mt-3 space-y-3 text-[13px]" data-testid="platform-roadmap-api">
              {ROADMAP_API_ITEMS.map((item) => (
                <li
                  key={item.label}
                  className="rounded-xl border border-dashed border-meadow bg-mist/60 px-4 py-3 text-stone"
                >
                  <span className="font-medium text-bark">{item.label}</span>
                  <span className="mt-1 block text-xs leading-relaxed">{item.note}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
        </Reveal>

        <Reveal>
          <BentoGrid />
        </Reveal>
      </main>
    </SiteShell>
  );
}
