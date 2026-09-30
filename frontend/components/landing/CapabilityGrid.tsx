import Link from "next/link";

const CAPABILITIES = [
  {
    badge: "Satellite & land",
    title: "Watch how land changes over time",
    body: "We look at green cover, bare soil, and wet areas from space so you can see stress in the landscape early.",
    meta: "Maps · Clear visuals",
    href: "/platform",
  },
  {
    badge: "Hills & water",
    title: "Understand slopes, valleys, and flow",
    body: "Elevation and terrain tools show where water runs and where hills may be less stable after storms.",
    meta: "Terrain · Everyday language",
    href: "/hazards",
  },
  {
    badge: "Ready to share",
    title: "Results you can take to a meeting",
    body: "Export a story your team can follow: what we checked, how sure we are, and what to look at next.",
    meta: "Reports · Team-friendly",
    href: "/dashboard",
  },
] as const;

export function CapabilityGrid() {
  return (
    <section className="bg-mist px-4 py-20 sm:px-6 md:py-24">
      <div className="mx-auto grid max-w-[1200px] gap-5 md:grid-cols-3">
        {CAPABILITIES.map((item) => (
          <article
            key={item.title}
            className="rounded-2xl border border-black/10 bg-chalk p-6"
          >
            <span className="inline-flex rounded-full bg-meadow px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-moss">
              {item.badge}
            </span>
            <h3 className="mt-4 font-display text-xl font-semibold text-bark">
              {item.title}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-stone">{item.body}</p>
            <p className="mt-4 text-xs font-medium text-stone/80">{item.meta}</p>
            <Link
              href={item.href}
              className="mt-4 inline-block text-sm font-semibold text-moss hover:text-leaf"
            >
              Learn more →
            </Link>
          </article>
        ))}
      </div>
    </section>
  );
}
