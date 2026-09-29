import { MediaFallback } from "@/components/visuals/MediaFallback";
import type { UnsplashKey } from "@/lib/visuals";
import { cn } from "@/lib/utils";

type LandPhotoProps = {
  unsplash: UnsplashKey;
  alt: string;
  caption?: string;
  className?: string;
  height?: string;
};

export function LandPhoto({
  unsplash,
  alt,
  caption,
  className,
  height = "h-44 md:h-56",
}: LandPhotoProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-3xl border border-meadow shadow-soft",
        height,
        className
      )}
    >
      <MediaFallback
        alt={alt}
        unsplash={unsplash}
        overlay="dark"
        className="absolute inset-0"
      />
      {caption && (
        <p className="absolute bottom-4 left-5 right-5 z-10 font-display text-2xl font-semibold text-chalk">
          {caption}
        </p>
      )}
    </div>
  );
}
