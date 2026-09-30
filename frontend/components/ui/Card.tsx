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
  core: "bg-chalk border border-black/10 text-bark",
  electric: "bg-gradient-to-br from-meadow via-chalk to-mist border border-black/10 text-bark",
  light: "bg-mist text-bark border border-black/10",
  transparent: "bg-transparent",
  earth: "bg-chalk border border-black/10 text-bark",
  canopy: "bg-canopy/90 border border-white/10 text-chalk",
};

export function Card({ children, className, tone = "core", hover = true }: CardProps) {
  return (
    <motion.div
      whileHover={hover ? { y: -2 } : undefined}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className={cn("rounded-2xl p-8 md:p-8", tones[tone], className)}
    >
      {children}
    </motion.div>
  );
}
