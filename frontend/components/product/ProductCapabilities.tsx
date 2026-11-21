import Link from "next/link";
import {
  PRODUCT_GEOLOGICAL,
  PRODUCT_HAZARDS,
  PRODUCT_SAFEGUARDS,
} from "@/lib/productCapabilities";

/**
 * Client-facing capability summary grounded in the live Stage 2.5 product.
 * Does not invent accuracy metrics or claim lineaments affect live scores.
 */

type ProductCapabilitiesProps = {
  /** Compact panel for dashboard / workspace; full section for marketing. */
  variant?: "section" | "panel";
  className?: string;
};

export function ProductCapabilities({
  variant = "section",
  className = "",
}: ProductCapabilitiesProps) {
  const shell =
    variant === "section"
      ? "bg-land-wash px-4 py-20 sm:px-6 md:py-24"
      : "rounded-xl border border-meadow bg-mist px-4 py-3";
  const titleClass =
    variant === "section"
      ? "font-display text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-bark min-[641px]:text-[40px]"
      : "text-[11px] uppercase tracking-widest text-stone";
  const title =
    variant === "section" ? "What SSRI can show you today" : "Product capabilities";

  return (
    <section className={`${shell} ${className}`.trim()} data-testid="product-capabilities">
      <div className={variant === "section" ? "mx-auto max-w-[1200px]" : undefined}>
        <h2 className={titleClass}>{title}</h2>
        {variant === "section" && (
          <p className="mt-6 max-w-[70ch] font-body text-[17px] leading-[1.6] text-bark/70">
            Ground-risk assessment covers three hazards. Geological conditioning
            datasets are managed separately and are not claimed as live score drivers
            until a compatible model is trained and evaluated. Status remains
            NOT_VALIDATED.
          </p>
        )}

        <div
          className={
            variant === "section"
              ? "mt-12 grid gap-8 md:grid-cols-3"
              : "mt-3 space-y-4"
          }
        >
          <div data-testid="capabilities-hazards">
            <h3 className="font-display text-lg font-semibold text-bark">
              Ground-risk assessment
            </h3>
            <ul className="mt-3 space-y-2">
              {PRODUCT_HAZARDS.map((hazard) => (
                <li
                  key={hazard.id}
                  data-testid={`capability-hazard-${hazard.id}`}
                  className="rounded-lg border border-meadow/80 bg-chalk px-3 py-2"
                >
                  <p className="text-sm font-medium text-bark">{hazard.name}</p>
                  <p className="text-[11px] text-stone">{hazard.detail}</p>
                </li>
              ))}
            </ul>
          </div>

          <div data-testid="capabilities-geological">
            <h3 className="font-display text-lg font-semibold text-bark">
              Geological intelligence
            </h3>
            <p className="mt-1 text-[11px] text-stone">
              Conditioning capabilities — not a fourth hazard.
            </p>
            <ul className="mt-3 space-y-2">
              {PRODUCT_GEOLOGICAL.map((item) => (
                <li
                  key={item.id}
                  data-testid={`capability-geo-${item.id}`}
                  className="rounded-lg border border-meadow/80 bg-chalk px-3 py-2"
                >
                  <p className="text-sm font-medium text-bark">{item.name}</p>
                  <p className="text-[11px] text-stone">{item.status}</p>
                </li>
              ))}
            </ul>
          </div>

          <div data-testid="capabilities-safeguards">
            <h3 className="font-display text-lg font-semibold text-bark">
              Scientific and operational safeguards
            </h3>
            <ul className="mt-3 space-y-2">
              {PRODUCT_SAFEGUARDS.map((item) => (
                <li
                  key={item}
                  className="rounded-lg border border-meadow/80 bg-chalk px-3 py-2 text-sm text-bark"
                >
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {variant === "section" && (
          <p className="mt-10 text-sm text-stone">
            Explore hazards in plain language on{" "}
            <Link href="/hazards" className="font-semibold text-moss hover:text-leaf">
              /hazards
            </Link>
            , manage geological datasets on{" "}
            <Link href="/geological" className="font-semibold text-moss hover:text-leaf">
              /geological
            </Link>
            , or run an assessment on the{" "}
            <Link href="/dashboard" className="font-semibold text-moss hover:text-leaf">
              map
            </Link>
            .
          </p>
        )}
      </div>
    </section>
  );
}
