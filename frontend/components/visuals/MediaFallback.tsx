"use client";

import { useState } from "react";
import Image from "next/image";
import type { LucideIcon } from "lucide-react";
import { ImageOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { unsplashUrl, type UnsplashKey } from "@/lib/visuals";
import { IconOrb } from "@/components/visuals/IconOrb";

type MediaFallbackProps = {
  alt: string;
  className?: string;
  /** Optional local path — falls back to Unsplash if missing or broken. */
  src?: string;
  unsplash?: UnsplashKey;
  icon?: LucideIcon;
  gradient?: string;
  priority?: boolean;
  overlay?: "dark" | "light" | "none";
};

export function MediaFallback({
  alt,
  className,
  src,
  unsplash = "terrain",
  icon,
  gradient = "from-leaf/25 via-moss/15 to-canopy",
  priority = false,
  overlay = "dark",
}: MediaFallbackProps) {
  const [localFailed, setLocalFailed] = useState(false);
  const remoteSrc = unsplashUrl(unsplash, 1400);
  const useRemote = !src || localFailed;
  const imageSrc = useRemote ? remoteSrc : src;
  const showGradientOnly = localFailed && !unsplash;

  return (
    <div className={cn("relative overflow-hidden bg-canopy", className)}>
      {!showGradientOnly ? (
        <>
          <Image
            key={imageSrc}
            src={imageSrc}
            alt={alt}
            fill
            priority={priority}
            sizes="(max-width: 768px) 100vw, 50vw"
            className="object-cover"
            onError={() => setLocalFailed(true)}
          />
          {overlay === "dark" && (
            <div className="absolute inset-0 bg-gradient-to-t from-soil via-canopy/50 to-soil/20" />
          )}
          {overlay === "light" && (
            <div className="absolute inset-0 bg-gradient-to-br from-chalk/20 to-transparent" />
          )}
        </>
      ) : (
        <div
          className={cn(
            "absolute inset-0 bg-gradient-to-br backdrop-blur-xl",
            gradient
          )}
        />
      )}

      {icon && (
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <IconOrb icon={icon} size="lg" tone="emerald" />
        </div>
      )}

      {!icon && showGradientOnly && (
        <div className="absolute inset-0 flex items-center justify-center">
          <IconOrb icon={ImageOff} size="md" tone="muted" float={false} />
        </div>
      )}

      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_70%_20%,rgba(82,183,136,0.14),transparent_50%)]"
      />
    </div>
  );
}
