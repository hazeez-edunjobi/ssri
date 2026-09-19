import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Building2,
  Cpu,
  Globe2,
  Layers,
  Mountain,
  ShieldCheck,
} from "lucide-react";

/**
 * Curated Unsplash geography imagery (satellite / aerial land).
 * Prefer Landsat-style and vegetated terrain for SSRI brand fit.
 */
export const UNSPLASH = {
  /** Landsat-style vegetated mountain ranges */
  terrain: "photo-1744968777239-aed5c5ff1224",
  /** Alpine / geology ridges */
  geology: "photo-1506905925346-21bda4d32df4",
  abstract3d: "photo-1618005182384-a83a8bd57fbe",
  /** Satellite view of snowy mountains and green valleys (Landsat) */
  satellite: "photo-1744968777047-92694d6a0b08",
  /** Green landscape valleys */
  landscape: "photo-1501785888041-af3ef285b470",
  data: "photo-1551288049-bebda4e38f71",
} as const;

export type UnsplashKey = keyof typeof UNSPLASH;

export function unsplashUrl(key: UnsplashKey, width = 1200) {
  const id = UNSPLASH[key];
  return `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${width}&q=80`;
}

export type VisualPreset = {
  unsplash?: UnsplashKey;
  icon?: LucideIcon;
  gradient: string;
  glow: string;
};

export const VISUAL_PRESETS = {
  hero: {
    unsplash: "terrain",
    icon: Globe2,
    gradient: "from-leaf/25 via-moss/10 to-transparent",
    glow: "shadow-[0_0_80px_-20px_rgba(64,145,108,0.4)]",
  },
  platform: {
    unsplash: "satellite",
    icon: Cpu,
    gradient: "from-moss/20 via-leaf/10 to-transparent",
    glow: "shadow-[0_0_50px_-12px_rgba(45,106,79,0.3)]",
  },
  hazards: {
    unsplash: "geology",
    icon: Mountain,
    gradient: "from-leaf/20 via-sprout/10 to-transparent",
    glow: "shadow-[0_0_50px_-12px_rgba(82,183,136,0.25)]",
  },
  developers: {
    unsplash: "data",
    icon: Layers,
    gradient: "from-moss/20 via-meadow/15 to-transparent",
    glow: "shadow-[0_0_50px_-12px_rgba(45,106,79,0.28)]",
  },
  about: {
    unsplash: "satellite",
    icon: ShieldCheck,
    gradient: "from-sprout/20 via-leaf/10 to-transparent",
    glow: "shadow-[0_0_50px_-12px_rgba(82,183,136,0.25)]",
  },
  infrastructure: {
    unsplash: "landscape",
    icon: Building2,
    gradient: "from-leaf/20 via-transparent to-moss/10",
    glow: "shadow-[0_0_40px_-12px_rgba(64,145,108,0.3)]",
  },
  subsidence: {
    unsplash: "terrain",
    icon: Activity,
    gradient: "from-soil/20 via-leaf/10 to-transparent",
    glow: "shadow-[0_0_40px_-12px_rgba(88,129,87,0.25)]",
  },
} as const satisfies Record<string, VisualPreset>;

export type VisualPresetKey = keyof typeof VISUAL_PRESETS;
