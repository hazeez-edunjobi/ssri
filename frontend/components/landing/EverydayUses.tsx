const USES = [
  {
    title: "Safer hillsides and valleys",
    body: "Spot slopes that may move after heavy rain — before homes or roads are placed in harm’s way.",
  },
  {
    title: "Smarter building sites",
    body: "Compare plots for settling or sinkhole concern so foundations and budgets match the land.",
  },
  {
    title: "Clearer community talks",
    body: "Share a simple risk map in meetings so everyone sees the same picture of local ground.",
  },
] as const;

export function EverydayUses() {
  return (
    <section className="bg-chalk px-4 py-20 md:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-bark md:text-4xl">
            What people use SSRI for — free to try
          </h2>
          <p className="mt-3 text-[15px] leading-relaxed text-stone">
            Everyday questions about land and safety. No special software training
            required to start.
          </p>
        </div>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {USES.map((item) => (
            <article
              key={item.title}
              className="rounded-2xl border border-meadow bg-mist p-6"
            >
              <h3 className="font-display text-lg font-semibold text-bark">
                {item.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-stone">{item.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
