import Link from "next/link";

/** Hex mesh mark inspired by the green brand mark (earth / trust motif). */
export function BrandMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      className={className}
      aria-hidden
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M32 4L56 18V46L32 60L8 46V18L32 4Z"
        stroke="currentColor"
        strokeWidth="3"
        fill="currentColor"
        fillOpacity="0.12"
      />
      <circle cx="32" cy="22" r="2.2" fill="currentColor" />
      <circle cx="22" cy="34" r="2.2" fill="currentColor" />
      <circle cx="42" cy="34" r="2.2" fill="currentColor" />
      <circle cx="32" cy="44" r="2.2" fill="currentColor" />
      <path
        d="M32 22L22 34L32 44L42 34Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M20 28C26 24 38 24 44 28C40 36 36 42 32 48C28 42 24 36 20 28Z"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function BrandLockup({
  tone = "dark",
}: {
  tone?: "dark" | "light";
}) {
  const color = tone === "light" ? "text-chalk" : "text-moss";
  const sub = tone === "light" ? "text-meadow/80" : "text-stone";
  return (
    <Link href="/" className={`flex items-center gap-2.5 ${color}`}>
      <BrandMark className="h-8 w-8 shrink-0" />
      <span className="leading-tight">
        <span className="block font-body text-[15px] font-bold tracking-wide">
          SSRI
        </span>
        <span className={`block text-[11px] font-medium ${sub}`}>
          ground you can trust
        </span>
      </span>
    </Link>
  );
}
