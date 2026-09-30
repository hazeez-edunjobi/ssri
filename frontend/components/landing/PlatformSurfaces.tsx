import Link from "next/link";
import { Map, Building2, Users } from "lucide-react";
import { LOGIN_HREF } from "@/lib/navigation";

const SURFACES = [
  {
    icon: Map,
    title: "For map explorers",
    tag: "Free start · Map tool",
    body: "Click any place you care about. Get a clear picture of ground risk in everyday words — not a wall of technical charts.",
    href: LOGIN_HREF,
    cta: "Log in to open the map →",
  },
  {
    icon: Building2,
    title: "For planners & builders",
    tag: "Projects · Decision support",
    body: "Compare sites before you spend money. Understand where land may slide, sink, or settle — then plan safer routes and foundations.",
    href: "/platform",
    cta: "See planning uses →",
  },
  {
    icon: Users,
    title: "For communities",
    tag: "Local insight · Shared safety",
    body: "Help neighbors and local teams talk about land risk with the same simple map. Built to be useful in towns, cities, and rural valleys.",
    href: "/hazards",
    cta: "Learn about hazards →",
  },
] as const;

export function PlatformSurfaces() {
  return (
    <section className="bg-land-wash px-4 py-20 sm:px-6 md:py-24">
      <div className="mx-auto max-w-[1200px] text-center">
        <h2 className="font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-bark min-[641px]:text-[40px]">
          One clear picture. Three ways to use it.
        </h2>
        <p className="mx-auto mt-6 max-w-[70ch] font-body text-[17px] font-normal leading-[1.6] text-bark/70">
          Open for anyone who wants to understand the land. Deeper tools when you
          need them for work. Same trusted earth view underneath.
        </p>

        <div className="mt-12 grid gap-5 text-left md:grid-cols-3">
          {SURFACES.map(({ icon: Icon, title, tag, body, href, cta }) => (
            <article
              key={title}
              className="flex h-full flex-col rounded-2xl border border-black/10 bg-chalk p-6"
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-meadow text-moss">
                <Icon className="h-5 w-5" strokeWidth={2} />
              </span>
              <h3 className="mt-5 font-display text-xl font-semibold text-bark">
                {title}
              </h3>
              <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-leaf">
                {tag}
              </p>
              <p className="mt-3 flex-1 text-sm leading-relaxed text-stone">
                {body}
              </p>
              <Link
                href={href}
                className="mt-5 text-sm font-semibold text-moss transition hover:text-leaf"
              >
                {cta}
              </Link>
            </article>
          ))}
        </div>

        <div className="mt-10">
          <Link
            href="/platform"
            className="inline-flex rounded-md bg-leaf px-6 py-3.5 text-sm font-semibold text-chalk transition hover:bg-moss"
          >
            Read the full platform guide
          </Link>
        </div>
      </div>
    </section>
  );
}
