import Link from "next/link";

const POINTS = [
  {
    title: "Reads hills, rivers, and soil from space",
    body: "We bring together satellite photos, elevation, and deep-earth signals so you see the land as a whole — not just the surface.",
  },
  {
    title: "Explains risk in plain language",
    body: "Scores are turned into everyday words: higher or lower chance of landslide, sinkhole, or ground settling — with honest confidence notes.",
  },
  {
    title: "Works where you already look",
    body: "Pick a point or draw an area on the map. Get a result you can share with a neighbor, a client, or a city team.",
  },
  {
    title: "Built for trust, not hype",
    body: "We show what the model used and when we are less sure. No hidden “black box” promises about the ground.",
  },
] as const;

export function CorePlatform() {
  return (
    <section className="bg-soil px-4 py-20 text-chalk sm:px-6 md:py-24">
      <div className="mx-auto max-w-[1200px]">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] min-[641px]:text-[40px]">
            A fresh look at land safety
          </h2>
          <p className="mt-6 max-w-[70ch] font-body text-[17px] font-normal leading-[1.6] text-chalk/70">
            SSRI was built so anyone can ask a simple question: “Is this ground a
            wise place to live, build, or plant?” The answer comes from maps of
            real lands — forests, slopes, valleys, and towns — not guesswork.
          </p>
        </div>

        <div className="mt-12 grid gap-4 md:grid-cols-2">
          {POINTS.map((item) => (
            <article
              key={item.title}
              className="rounded-2xl border border-sprout/25 bg-canopy/40 p-6 shadow-[inset_1px_0_0_rgba(82,183,136,0.35)]"
            >
              <h3 className="font-display text-lg font-semibold text-chalk">
                {item.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-meadow/85">
                {item.body}
              </p>
            </article>
          ))}
        </div>

        <p className="mt-10 text-center text-sm text-meadow/80">
          One map for people, planners, and builders —{" "}
          <Link href="/about" className="font-semibold text-sprout hover:underline">
            our story →
          </Link>
        </p>
      </div>
    </section>
  );
}
