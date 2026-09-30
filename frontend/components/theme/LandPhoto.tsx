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
  height = "h-48 md:h-64",
}: LandPhotoProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-3xl border border-black/10",
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
        <p className="absolute bottom-4 left-4 right-4 z-10 font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-chalk">
          {caption}
        </p>
      )}
    </div>
  );
}
