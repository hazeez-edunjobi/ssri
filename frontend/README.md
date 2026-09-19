# SSRI — Subsurface Structural Risk Intelligence

Next.js 14 (App Router) + TypeScript + Tailwind marketing site and dashboard shell,
built from the SSRI brief and the reference layout (pill nav, rounded card canvas,
3-column bento grid, split use-case section).

## Run it

```bash
npm install
npm run dev
```

Open http://localhost:3000 for the landing page, http://localhost:3000/dashboard
for the map-first dashboard shell.

> First build needs internet access once, to fetch Space Grotesk / Inter / IBM
> Plex Mono via `next/font/google`. If you're building somewhere offline, swap
> those imports in `app/layout.tsx` for local font files.

## Design system

- **Palette:** void `#05070C`, panel `#0C0F18`, core `#151928`, electric
  `#3EA6FF`, cyan `#22D3EE`, emerald `#34D399`, ink `#E9EDF5`, muted `#7C8699`.
- **Type:** Space Grotesk (display), Inter (body), IBM Plex Mono (data / labels,
  coordinates, API snippets — a nod to instrument readouts).
- **Signature element:** `TerrainGraphic`, a layered SVG topographic contour
  with an animated scan-line sweep, standing in for the elevation + subsurface
  data SSRI actually ingests. Reused in the hero, the susceptibility-scoring
  bento card, and the use-case panel so it reads as a motif, not a one-off.
- **Motion:** GSAP + ScrollTrigger (`components/animations/ParallaxWrapper.tsx`)
  drives the hero terrain parallax and the staggered bento/step-card reveals.
  Framer Motion handles micro-interactions — button press states, card lift on
  hover, and the sliding nav-pill indicator (`layoutId="nav-pill"`).

## Structure

```
app/
 ├── layout.tsx        Root layout, font variables
 ├── page.tsx           Landing page composition
 └── dashboard/
      └── page.tsx       MapLibre-based risk analytics dashboard shell
components/
 ├── landing/            Navbar, Hero, BentoGrid, PartnerLogos, HowItWorks, UseCases, Footer
 ├── ui/                  Button, Card
 └── animations/          ParallaxWrapper + useScrollStagger
lib/
 ├── gsap-config.ts       Client-side GSAP plugin registration
 └── utils.ts             cn() class merge helper
```

## Notes / next steps

- `/dashboard` wires up a real MapLibre map (`demotiles.maplibre.org` style) with
  a hazard-layer sidebar; swap the style URL and add a `/v1/hazard` fetch when
  the API is live.
- Partner names, statistics, and case-study copy are placeholders per the brief
  — swap in real backers and figures before launch.
- Pricing, testimonials, and FAQ sections from the brief aren't built yet; the
  section shape in `HowItWorks.tsx` / `BentoGrid.tsx` gives a pattern to extend.
