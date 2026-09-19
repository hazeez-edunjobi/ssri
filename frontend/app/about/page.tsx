import type { Metadata } from "next";
import { SiteShell } from "@/components/layout/SiteShell";
import { PageHeader } from "@/components/pages/PageHeader";
import { PartnerLogos } from "@/components/landing/PartnerLogos";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { IconOrbStatic } from "@/components/visuals/IconOrbStatic";

export const metadata: Metadata = {
  title: "About — SSRI",
  description:
    "SSRI mission, partners, and how we help people understand the ground.",
};

const values = [
  {
    icon: "target" as const,
    title: "Mission",
    body: "Make ground-risk insight as easy to use as a map — so homes and roads are planned with eyes open.",
  },
  {
    icon: "users" as const,
    title: "Who we serve",
    body: "Planners, builders, insurers, community groups, and anyone who needs a clearer view of the land.",
  },
  {
    icon: "mail" as const,
    title: "Contact",
    body: "Write hello@ssri.io for partnerships, pilots, and team deployments.",
  },
];

export default function AboutPage() {
  return (
    <SiteShell>
      <main className="bg-mist">
        <PageHeader
          eyebrow="About SSRI"
          title="Mapping what lies below"
          description="SSRI closes the gap between what satellites see on the surface and what people need to know about the ground — in language everyone can follow."
          visual="about"
        />

        <section className="px-4 py-16 md:px-8">
          <div className="mx-auto grid max-w-6xl gap-5 md:grid-cols-3">
            {values.map(({ icon, title, body }) => (
              <Card key={title} className="relative overflow-hidden p-6">
                <div
                  aria-hidden
                  className="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-leaf/15 blur-2xl"
                />
                <IconOrbStatic
                  name={icon}
                  size="sm"
                  tone="emerald"
                  float={false}
                />
                <h2 className="mt-4 font-display text-xl font-semibold text-bark">
                  {title}
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-stone">{body}</p>
              </Card>
            ))}
          </div>
        </section>

        <section id="partners">
          <PartnerLogos />
        </section>

        <section id="contact" className="px-4 pb-20 md:px-8">
          <div className="mx-auto max-w-6xl rounded-3xl border border-meadow bg-canopy px-6 py-12 text-center shadow-soft md:px-10">
            <h2 className="font-display text-3xl font-semibold text-chalk">
              Partner with SSRI
            </h2>
            <p className="mx-auto mt-3 max-w-md text-[15px] text-meadow/90">
              Join research groups and infrastructure teams making safer places
              with clearer ground intelligence.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Button variant="primary" icon href="mailto:hello@ssri.io">
                Get in Touch
              </Button>
              <Button
                variant="outline"
                href="/dashboard"
                className="!border-meadow/50 !text-chalk hover:!border-sprout hover:!text-sprout"
              >
                Try the Dashboard
              </Button>
            </div>
          </div>
        </section>
      </main>
    </SiteShell>
  );
}
