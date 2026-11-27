"use client";

import { useEffect, useState } from "react";
import { fetchGeologicalDerived } from "@/lib/geologicalApi";
import { cn } from "@/lib/utils";

type Props = {
  geoId: string;
  filename: string;
  alt: string;
  className?: string;
};

/**
 * Loads derived PNG/JPEG via authenticated fetch (Bearer / API key).
 * Plain <img src> cannot attach Authorization headers.
 */
export function AuthenticatedDerivedImage({
  geoId,
  filename,
  alt,
  className,
}: Props) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    const timer = window.setTimeout(() => {
      setUrl(null);
      setError(null);
      void fetchGeologicalDerived(geoId, filename)
        .then((blob) => {
          if (cancelled) return;
          objectUrl = URL.createObjectURL(blob);
          setUrl(objectUrl);
        })
        .catch((err: Error) => {
          if (!cancelled) setError(err.message || "Preview unavailable");
        });
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [geoId, filename]);

  if (error) {
    return (
      <div
        className={cn(
          "flex items-center justify-center bg-mist/60 px-3 py-6 text-center text-xs text-stone",
          className,
        )}
      >
        {error}
      </div>
    );
  }

  if (!url) {
    return (
      <div
        className={cn(
          "animate-pulse bg-meadow/30",
          className,
        )}
        aria-hidden
      />
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={url} alt={alt} className={className} />
  );
}
