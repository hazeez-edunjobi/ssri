const STORIES = [
  {
    title: "Protect homes near green hills",
    body: "Families and councils check slopes that look calm — until rain makes them move.",
    tint: "from-leaf/30 to-canopy/40",
  },
  {
    title: "Plan farms and open land wisely",
    body: "Growers and land trusts see wet pockets and soft ground before investing in soil and seed.",
    tint: "from-sprout/25 to-moss/35",
  },
  {
    title: "Guide roads and town edges",
    body: "Engineers compare routes across valleys and ridges with a shared, easy-to-read risk view.",
    tint: "from-meadow/50 to-leaf/20",
  },
] as const;

export function BuiltForWork() {
  return (
    <section className="bg-chalk px-4 py-20 sm:px-6 md:py-24">
      <div className="mx-auto max-w-[1200px]">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-bark min-[641px]:text-[40px]">
            Built for real places and real people
          </h2>
          <p className="mt-6 font-body text-[17px] font-normal leading-[1.6] text-bark/70">
            From leafy neighborhoods to open farmland — SSRI is for the lands we
            live on, grow on, and pass to the next generation.
          </p>
        </div>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {STORIES.map((story) => (
            <article
              key={story.title}
              className="overflow-hidden rounded-2xl border border-meadow bg-mist"
            >
              <div
                className={`h-36 bg-gradient-to-br ${story.tint} topo-lines`}
                aria-hidden
              />
              <div className="p-5">
                <h3 className="font-display text-lg font-semibold text-bark">
                  {story.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-stone">
                  {story.body}
                </p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
