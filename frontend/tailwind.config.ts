import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: "#05070C",
        panel: "#0C0F18",
        "panel-2": "#10131F",
        core: "#151928",
        line: "#212636",
        electric: "#3EA6FF",
        cyan: "#22D3EE",
        emerald: "#34D399",
        ink: "#E9EDF5",
        muted: "#7C8699",
        haze: "#E6EAF8",
        // Earth / greenery marketing theme (Whitebox-like structure)
        soil: "#14261A",
        canopy: "#1B4332",
        moss: "#2D6A4F",
        leaf: "#40916C",
        sprout: "#52B788",
        mist: "#F4F7F2",
        chalk: "#FFFFFF",
        bark: "#1A1F1C",
        stone: "#5C6B60",
        meadow: "#D8E8D4",
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        body: ["var(--font-body)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      borderRadius: {
        xl2: "28px",
        xl3: "32px",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(62,166,255,0.15), 0 20px 60px -20px rgba(62,166,255,0.25)",
        card: "0 30px 80px -40px rgba(0,0,0,0.6)",
        soft: "0 18px 50px -28px rgba(20, 38, 26, 0.35)",
      },
      backgroundImage: {
        "grid-fade":
          "linear-gradient(to bottom, rgba(233,237,245,0.06) 1px, transparent 1px), linear-gradient(to right, rgba(233,237,245,0.06) 1px, transparent 1px)",
        "earth-hero":
          "radial-gradient(ellipse 80% 60% at 50% 40%, rgba(64,145,108,0.35), transparent 70%), linear-gradient(160deg, #0F2418 0%, #1B4332 45%, #08140E 100%)",
        "land-wash":
          "linear-gradient(180deg, #F4F7F2 0%, #EAF3E6 100%)",
      },
    },
  },
  plugins: [],
};

export default config;
