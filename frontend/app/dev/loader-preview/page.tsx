"use client";

import { ContentSkeleton, Loader, MapSkeleton } from "@/components/ui/loader";

/**
 * Local visual review surface for loader variants.
 * Not linked from production navigation.
 */
export default function LoaderPreviewPage() {
  return (
    <main className="min-h-screen bg-land-wash px-4 py-10 text-bark sm:px-8">
      <div className="mx-auto max-w-5xl space-y-10">
        <header>
          <p className="font-mono text-[10px] uppercase tracking-widest text-leaf">
            Visual review
          </p>
          <h1 className="mt-2 font-display text-3xl">SSRI loader variants</h1>
          <p className="mt-2 max-w-2xl text-sm text-stone">
            Assessment uses an honest indeterminate state when the API does not
            confirm stages. Staged mode appears only with confirmed backend progress.
          </p>
        </header>

        <section className="rounded-2xl border border-meadow bg-chalk p-5 shadow-soft">
          <h2 className="font-display text-lg">Assessment — indeterminate</h2>
          <Loader
            variant="assessment"
            progress={{ status: "running" }}
            onCancel={() => undefined}
            data-testid="preview-assessment-indeterminate"
          />
        </section>

        <section className="rounded-2xl border border-meadow bg-chalk p-5 shadow-soft">
          <h2 className="font-display text-lg">Assessment — staged (API-confirmed)</h2>
          <Loader
            variant="assessment"
            progress={{
              status: "running",
              stage: "acquiring",
              completed_stages: ["preparing"],
              message:
                "Geospatial acquisition and feature preparation take time. Thank you for your patience.",
            }}
            onCancel={() => undefined}
            data-testid="preview-assessment-staged"
          />
        </section>

        <section className="grid gap-6 md:grid-cols-2">
          <div className="rounded-2xl border border-meadow bg-chalk p-5 shadow-soft">
            <h2 className="font-display text-lg">Section + skeleton</h2>
            <Loader
              variant="section"
              title="Loading assessment history"
              description="Fetching the operational archive of persisted assessments."
              skeleton={<ContentSkeleton rows={3} />}
            />
          </div>
          <div className="rounded-2xl border border-meadow bg-chalk p-5 shadow-soft">
            <h2 className="font-display text-lg">Inline / map / error</h2>
            <div className="space-y-4">
              <Loader variant="inline" title="Refreshing catalogue" />
              <div className="h-40 overflow-hidden rounded-xl border border-meadow">
                <MapSkeleton />
              </div>
              <Loader
                variant="section"
                error="Assessment timed out waiting for geospatial acquisition."
                onRetry={() => undefined}
              />
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
