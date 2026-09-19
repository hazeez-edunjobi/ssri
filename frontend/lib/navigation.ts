export type NavLink = {
  label: string;
  href: string;
  index: string;
};

export const NAV_LINKS: NavLink[] = [
  { label: "Platform", href: "/platform", index: "01" },
  { label: "Hazards", href: "/hazards", index: "02" },
  { label: "Developers", href: "/developers", index: "03" },
  { label: "About", href: "/about", index: "04" },
];

export const DASHBOARD_HREF = "/dashboard";
export const TRAINING_HREF = "/training";

export const FOOTER_COLUMNS = [
  {
    title: "Platform",
    links: [
      { label: "Overview", href: "/platform" },
      { label: "How It Works", href: "/platform#pipeline" },
      { label: "Dashboard", href: DASHBOARD_HREF },
      { label: "Training", href: TRAINING_HREF },
    ],
  },
  {
    title: "Hazards",
    links: [
      { label: "Subsidence", href: "/hazards#subsidence" },
      { label: "Landslides", href: "/hazards#landslide" },
      { label: "Liquefaction", href: "/hazards#liquefaction" },
    ],
  },
  {
    title: "Developers",
    links: [
      { label: "API Reference", href: "/developers" },
      { label: "Quickstart", href: "/developers#quickstart" },
      { label: "OpenAPI", href: "/developers#openapi" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "/about" },
      { label: "Partners", href: "/about#partners" },
      { label: "Contact", href: "/about#contact" },
    ],
  },
] as const;
