import type { Metadata } from "next";
import { SiteShell } from "@/components/layout/SiteShell";
import { Reveal } from "@/components/animations/Reveal";
import { PageHeader } from "@/components/pages/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { IconOrbStatic } from "@/components/visuals/IconOrbStatic";
import {
  ASSESS_CURL_EXAMPLE,
  AVAILABLE_API_CAPABILITIES,
  LIVE_ASSESS_ROUTE,
  ROADMAP_API_ITEMS,
} from "@/lib/marketingApiCopy";

export const metadata: Metadata = {
  title: "Developers",
  description:
    "SSRI REST API notes for the live assessment route and related readiness endpoints.",
};

const quickstartSteps = [
  {
    title: "Authenticate",
    body: "Use a Stage 2.5 API key or a signed-in session token as Bearer auth against your API origin.",
  },
  {
    title: "Submit an assessment",
    body: `Call ${LIVE_ASSESS_ROUTE} with a WGS84 point or polygon. Live map assessment uses the promoted 13-channel Stage 2.5 checkpoint.`,
  },
  {
    title: "Read the response",
    body: "Hazard rankings, confidence notes, and conditioning analytics return in the same response. Status remains NOT_VALIDATED unless independently validated.",
  },
];

export default function DevelopersPage() {
  return (
    <SiteShell>
      <main className="bg-mist">
        <PageHeader
          eyebrow="Developers"
          title="Build with ground intelligence"
          description="Use the live SSRI REST assessment API. SDKs and alternate public hazard URLs are roadmap items, not shipped packages."
          visual="developers"
        />

        <Reveal>
        <section id="quickstart" className="px-4 py-20 sm:px-6">
          <div className="mx-auto max-w-[1200px]">
            <div className="flex items-center gap-3">
              <IconOrbStatic
                name="terminal"
                size="sm"
                tone="emerald"
                float={false}
              />
              <h2 className="font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-bark min-[641px]:text-[40px]">
                Quickstart
              </h2>
            </div>
            <div className="mt-8 grid gap-5 md:grid-cols-3">
              {quickstartSteps.map((step, index) => (
                <Card key={step.title} className="p-6">
                  <span className="text-xs font-bold text-leaf">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <h3 className="mt-3 font-display text-lg font-semibold text-bark">
                    {step.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-stone">
                    {step.body}
                  </p>
                </Card>
              ))}
            </div>

            <Card
              tone="electric"
              className="mt-8 p-6 font-mono text-[13px]"
              data-testid="developers-assess-example"
            >
              <p className="text-stone"># Live assessment (implemented)</p>
              <pre className="mt-2 whitespace-pre-wrap text-bark">{ASSESS_CURL_EXAMPLE}</pre>
              <p className="mt-3 text-stone">
                Response includes subsidence, landslide, and sinkhole rankings plus
                provenance notes. Not geological ground truth.
              </p>
            </Card>
          </div>
        </section>
        </Reveal>

        <Reveal>
        <section id="openapi" className="bg-land-wash px-4 py-20 sm:px-6">
          <div className="mx-auto grid max-w-[1200px] gap-6 md:grid-cols-2">
            <Card className="p-8" data-testid="developers-available-api">
              <IconOrbStatic
                name="code2"
                size="sm"
                tone="emerald"
                float={false}
              />
              <h2 className="mt-4 font-display text-2xl font-semibold text-bark">
                Available today
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-stone">
                Implemented FastAPI routes under <code>/api/v1</code>. Prefer your
                deployed API origin (local or hosted) — not fictional public hosts.
              </p>
              <ul className="mt-4 space-y-3 text-sm text-stone">
                {AVAILABLE_API_CAPABILITIES.map((item) => (
                  <li key={item.route}>
                    <span className="font-mono text-moss">{item.route}</span>
                    <span className="mt-1 block text-xs leading-relaxed">{item.summary}</span>
                  </li>
                ))}
              </ul>
            </Card>

            <Card className="p-8" data-testid="developers-roadmap-api">
              <IconOrbStatic
                name="bookOpen"
                size="sm"
                tone="emerald"
                float={false}
              />
              <h2 className="mt-4 font-display text-2xl font-semibold text-bark">
                Roadmap / not shipped
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-stone">
                These items are not available as installable packages or live public
                endpoints. Do not treat them as product capabilities yet.
              </p>
              <ul className="mt-4 space-y-3 text-sm text-stone">
                {ROADMAP_API_ITEMS.map((item) => (
                  <li key={item.label}>
                    <span className="font-medium text-bark">{item.label}</span>
                    <span className="mt-1 block text-xs leading-relaxed">{item.note}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-6">
                <Button variant="primary" icon href="/dashboard">
                  Open assessment map
                </Button>
              </div>
            </Card>
          </div>
        </section>
        </Reveal>
      </main>
    </SiteShell>
  );
}
