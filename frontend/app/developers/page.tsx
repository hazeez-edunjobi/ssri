import type { Metadata } from "next";
import { SiteShell } from "@/components/layout/SiteShell";
import { PageHeader } from "@/components/pages/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { IconOrbStatic } from "@/components/visuals/IconOrbStatic";

export const metadata: Metadata = {
  title: "Developers — SSRI",
  description: "SSRI API documentation, SDK quickstarts, and OpenAPI reference.",
};

const quickstartSteps = [
  {
    title: "Get an API key",
    body: "Register in the developer portal and add SSRI_API_KEY to your environment.",
  },
  {
    title: "Submit a check",
    body: "POST an area and date range to /v1/assessments to start a land-risk job.",
  },
  {
    title: "Collect results",
    body: "GET /v1/assessments/{id} until complete, then download maps or arrays.",
  },
];

export default function DevelopersPage() {
  return (
    <SiteShell>
      <main className="bg-mist">
        <PageHeader
          eyebrow="Developers"
          title="Build with ground intelligence"
          description="Add SSRI risk scores to your apps with a REST API, typed SDKs, and OpenAPI docs."
          visual="developers"
        />

        <section id="quickstart" className="px-4 py-16 md:px-8">
          <div className="mx-auto max-w-6xl">
            <div className="flex items-center gap-3">
              <IconOrbStatic
                name="terminal"
                size="sm"
                tone="emerald"
                float={false}
              />
              <h2 className="font-display text-3xl font-semibold text-bark">
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

            <Card tone="electric" className="mt-8 p-6 font-mono text-[13px]">
              <p className="text-stone"># Example: point hazard query</p>
              <p className="mt-2 text-moss">
                curl -H &quot;Authorization: Bearer $SSRI_API_KEY&quot; \
              </p>
              <p className="text-bark">
                &quot;https://api.ssri.io/v1/hazard?lat=6.52&amp;lon=3.38&quot;
              </p>
              <p className="mt-3 text-stone">
                {`{ "subsidence": 0.12, "landslide": 0.34, "liquefaction": 0.08 }`}
              </p>
            </Card>
          </div>
        </section>

        <section id="openapi" className="bg-land-wash px-4 py-16 md:px-8">
          <div className="mx-auto grid max-w-6xl gap-6 md:grid-cols-2">
            <Card className="p-8">
              <IconOrbStatic
                name="code2"
                size="sm"
                tone="emerald"
                float={false}
              />
              <h2 className="mt-4 font-display text-2xl font-semibold text-bark">
                SDKs
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-stone">
                Official client libraries for Python and TypeScript with typed
                models and helpers.
              </p>
              <ul className="mt-4 space-y-2 font-mono text-[12px] text-stone">
                <li>pip install ssri-python</li>
                <li>npm install @ssri/sdk</li>
              </ul>
            </Card>

            <Card className="p-8">
              <IconOrbStatic
                name="bookOpen"
                size="sm"
                tone="emerald"
                float={false}
              />
              <h2 className="mt-4 font-display text-2xl font-semibold text-bark">
                OpenAPI reference
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-stone">
                Full schemas for assessments, hazard queries, layer downloads,
                and webhooks.
              </p>
              <div className="mt-6">
                <Button variant="primary" icon href="/developers#openapi">
                  View OpenAPI Spec
                </Button>
              </div>
            </Card>
          </div>
        </section>
      </main>
    </SiteShell>
  );
}
