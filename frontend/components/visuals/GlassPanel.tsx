import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

type GlassPanelProps = {
  children?: ReactNode;
  className?: string;
  gradient?: string;
  glow?: boolean;
};

export function GlassPanel({
  children,
  className,
  gradient = "from-leaf/20 via-moss/10 to-transparent",
  glow = true,
}: GlassPanelProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border border-black/10 bg-gradient-to-br backdrop-blur-xl",
        gradient,
        glow && "shadow-[0_0_50px_-12px_rgba(45,106,79,0.28)]",
        className
      )}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-grid-fade bg-[length:32px_32px] opacity-30"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-leaf/15 blur-3xl"
      />
      <div className="absolute inset-0">{children}</div>
    </div>
  );
}
