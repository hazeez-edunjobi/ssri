"use client";

import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export type IconOrbProps = {
  icon: LucideIcon;
  className?: string;
  size?: "sm" | "md" | "lg";
  tone?: "electric" | "cyan" | "emerald" | "muted";
  float?: boolean;
};

const sizes = {
  sm: { orb: "h-10 w-10", icon: "h-4 w-4" },
  md: { orb: "h-14 w-14", icon: "h-6 w-6" },
  lg: { orb: "h-20 w-20", icon: "h-9 w-9" },
};

const tones = {
  electric: "from-leaf/35 to-leaf/5 text-leaf shadow-[0_0_40px_-8px_rgba(64,145,108,0.45)] border-leaf/20",
  cyan: "from-sprout/30 to-sprout/5 text-moss shadow-[0_0_40px_-8px_rgba(82,183,136,0.4)] border-sprout/20",
  emerald: "from-moss/30 to-meadow/40 text-moss shadow-[0_0_40px_-8px_rgba(45,106,79,0.35)] border-meadow",
  muted: "from-meadow/40 to-mist text-stone shadow-none border-meadow",
};

export function IconOrb({
  icon: Icon,
  className,
  size = "md",
  tone = "electric",
  float = true,
}: IconOrbProps) {
  const s = sizes[size];

  return (
    <motion.div
      animate={float ? { y: [0, -6, 0] } : undefined}
      transition={float ? { duration: 4, repeat: Infinity, ease: "easeInOut" } : undefined}
      className={cn(
        "relative flex items-center justify-center rounded-full border bg-gradient-to-br backdrop-blur-xl",
        s.orb,
        tones[tone],
        className
      )}
    >
      <Icon className={s.icon} strokeWidth={1.75} />
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-full bg-[radial-gradient(circle_at_30%_20%,rgba(255,255,255,0.12),transparent_55%)]"
      />
    </motion.div>
  );
}
