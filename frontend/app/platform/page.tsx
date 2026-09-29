import type { Metadata } from "next";
import { SiteShell } from "@/components/layout/SiteShell";
import { PageHeader } from "@/components/pages/PageHeader";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { BentoGrid } from "@/components/landing/BentoGrid";
import { Card } from "@/components/ui/Card";
import { IconOrbStatic } from "@/components/visuals/IconOrbStatic";

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

const apiEndpoints = [
  "POST /v1/assessments — submit an area and receive a job ID",
  "GET /v1/assessments/{id} — check status and get outputs",
  "GET /v1/hazard?lat={lat}&lon={lon} — quick point risk query",
  "GET /v1/layers/{id}/geotiff — download map layers",
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
        />

        <section id="pipeline" className="px-4 py-16 md:px-8">
          <HowItWorks />
        </section>

        <section className="bg-land-wash px-4 py-16 md:px-8">
          <div className="mx-auto max-w-6xl">
            <h2 className="font-display text-3xl font-semibold tracking-tight text-bark md:text-4xl">
              What powers each check
            </h2>
            <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-stone">
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

        <section className="px-4 py-16 md:px-8">
          <div className="mx-auto max-w-6xl rounded-3xl border border-meadow bg-chalk p-6 shadow-soft md:p-10">
            <h2 className="font-display text-3xl font-semibold tracking-tight text-bark">
              For developers
            </h2>
            <p className="mt-3 max-w-xl text-[15px] text-stone">
              Plug ground-risk checks into planning, GIS, or insurance tools with
              the SSRI API.
            </p>
            <ul className="mt-8 space-y-3 font-mono text-[13px]">
              {apiEndpoints.map((endpoint) => (
                <li
                  key={endpoint}
                  className="rounded-xl border border-meadow bg-mist px-4 py-3 text-stone"
                >
                  <span className="font-semibold text-moss">
                    {endpoint.split(" — ")[0]}
                  </span>
                  {endpoint.includes(" — ") && (
                    <span> — {endpoint.split(" — ")[1]}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <BentoGrid />
      </main>
    </SiteShell>
  );
}
