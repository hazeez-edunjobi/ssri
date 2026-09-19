import { SceneVisual } from "@/components/visuals/SceneVisual";
import type { VisualPresetKey } from "@/lib/visuals";

type PageHeaderProps = {
  eyebrow: string;
  title: string;
  description: string;
  visual?: VisualPresetKey | false;
};

export function PageHeader({
  eyebrow,
  title,
  description,
  visual = false,
}: PageHeaderProps) {
  return (
    <section className="px-4 pt-10 md:px-8">
      <div className="mx-auto max-w-6xl overflow-hidden rounded-3xl border border-meadow bg-chalk shadow-soft">
        <div className="bg-earth-hero topo-lines px-6 py-14 md:px-10 md:py-16">
          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-sprout">
            {eyebrow}
          </p>
          <h1 className="mt-4 max-w-3xl text-balance font-display text-4xl font-semibold leading-[1.08] tracking-tight text-chalk md:text-5xl">
            {title}
          </h1>
          <p className="mt-5 max-w-2xl text-[15px] leading-relaxed text-meadow/95 md:text-base">
            {description}
          </p>
        </div>

        {visual && (
          <div className="border-t border-meadow bg-mist p-4 md:p-6">
            <SceneVisual
              preset={visual}
              className="w-full rounded-2xl"
              height="h-[220px] md:h-[300px]"
              priority
            />
          </div>
        )}
      </div>
    </section>
  );
}
