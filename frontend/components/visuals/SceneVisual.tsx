"use client";

import { TerrainGraphic } from "@/components/landing/TerrainGraphic";
import { GlassPanel } from "@/components/visuals/GlassPanel";
import { IconOrb } from "@/components/visuals/IconOrb";
import { MediaFallback } from "@/components/visuals/MediaFallback";
import { VISUAL_PRESETS, type VisualPresetKey } from "@/lib/visuals";
import { cn } from "@/lib/utils";

type SceneVisualProps = {
  preset?: VisualPresetKey;
  className?: string;
  height?: string;
  showTerrain?: boolean;
  showMedia?: boolean;
  terrainVariant?: "electric" | "mono";
  priority?: boolean;
};

export function SceneVisual({
  preset = "hero",
  className,
  height = "h-[280px] md:h-[360px]",
  showTerrain = true,
  showMedia = true,
  terrainVariant = "electric",
  priority = false,
}: SceneVisualProps) {
  const config = VISUAL_PRESETS[preset];
  const Icon = config.icon;

  return (
    <GlassPanel
      gradient={config.gradient}
      glow={false}
      className={cn(height, className)}
    >
      {showMedia && config.unsplash ? (
        <MediaFallback
          alt={`${preset} visual`}
          unsplash={config.unsplash}
          className="absolute inset-0"
          overlay="dark"
          priority={priority}
        />
      ) : null}

      {showTerrain && !showMedia ? (
        <TerrainGraphic
          className="absolute inset-0 opacity-80"
          variant={terrainVariant}
          scan
          interactive={false}
        />
      ) : null}

      {Icon && (
        <div className="absolute right-6 top-6 z-10">
          <IconOrb icon={Icon} size="md" tone="cyan" />
        </div>
      )}

      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-soil/85 to-transparent"
      />
    </GlassPanel>
  );
}
