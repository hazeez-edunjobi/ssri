"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

type CardProps = {
  children: ReactNode;
  className?: string;
  tone?: "core" | "electric" | "light" | "transparent" | "earth" | "canopy";
  hover?: boolean;
};

const tones = {
  core: "bg-chalk border border-meadow text-bark shadow-soft",
  electric: "bg-gradient-to-br from-meadow via-chalk to-mist border border-leaf/25 text-bark",
  light: "bg-mist text-bark border border-meadow",
  transparent: "bg-transparent",
  earth: "bg-chalk border border-meadow text-bark shadow-soft",
  canopy: "bg-canopy/90 border border-sprout/30 text-chalk",
};

export function Card({ children, className, tone = "core", hover = true }: CardProps) {
  return (
    <motion.div
      whileHover={hover ? { y: -6 } : undefined}
      transition={{ type: "spring", stiffness: 300, damping: 24 }}
      className={cn(
        "rounded-2xl p-8 md:p-10",
        hover && "hover:shadow-[0_24px_60px_-28px_rgba(45,106,79,0.35)]",
        tones[tone],
        className
      )}
    >
      {children}
    </motion.div>
  );
}
