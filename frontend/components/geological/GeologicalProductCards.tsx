"use client";

import { Download } from "lucide-react";
import type { MagneticProductEntry } from "@/lib/geologicalApi";
import {
  geotiffFilenameForProduct,
  previewFilenameForProduct,
  productDisplayBlurb,
  productDisplayTitle,
} from "@/lib/geologicalPresentation";
import { AuthenticatedDerivedImage } from "./AuthenticatedDerivedImage";

type Props = {
  geoId: string;
  products: MagneticProductEntry[];
  activeOperation: string | null;
  onSelect: (operation: string) => void;
  onDownload: (filename: string) => void;
};

export function GeologicalProductCards({
  geoId,
  products,
  activeOperation,
  onSelect,
  onDownload,
}: Props) {
  if (!products.length) {
    return (
      <div
        className="rounded-2xl border border-dashed border-meadow bg-chalk px-4 py-8 text-center text-sm text-stone"
        data-testid="geological-products-empty"
      >
        No geological products yet. Validate the survey, then process the TMI grid
        and magnetic operations.
      </div>
    );
  }

  return (
    <section data-testid="geological-products">
      <h2 className="font-display text-lg text-bark">Geological products</h2>
      <p className="mt-1 text-sm text-stone">
        Generated magnetic surfaces from this survey. Previews use authenticated
        derived files from the API.
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {products.map((product) => {
          const preview = previewFilenameForProduct(product);
          const geotiff = geotiffFilenameForProduct(product);
          const active = activeOperation === product.operation;
          return (
            <article
              key={product.operation}
              className={`overflow-hidden rounded-2xl border bg-chalk shadow-soft ${
                active ? "border-leaf" : "border-meadow"
              }`}
              data-testid={`geological-product-${product.operation}`}
            >
              <button
                type="button"
                className="block w-full text-left"
                onClick={() => onSelect(product.operation)}
              >
                <div className="aspect-[4/3] bg-mist">
                  {preview ? (
                    <AuthenticatedDerivedImage
                      geoId={geoId}
                      filename={preview}
                      alt={productDisplayTitle(product)}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center px-3 text-center text-xs text-stone">
                      No renderable preview for this product yet.
                    </div>
                  )}
                </div>
                <div className="p-3">
                  <h3 className="font-medium text-bark">
                    {productDisplayTitle(product)}
                  </h3>
                  <p className="mt-1 text-xs leading-relaxed text-stone">
                    {productDisplayBlurb(product)}
                  </p>
                  <p className="mt-2 font-mono text-[10px] uppercase tracking-wider text-leaf">
                    {product.preview_exists || product.geotiff_exists
                      ? "Available"
                      : "Pending"}
                    {product.units ? ` · ${product.units}` : ""}
                  </p>
                </div>
              </button>
              <div className="flex gap-2 border-t border-meadow/70 px-3 py-2">
                <button
                  type="button"
                  className="text-xs text-moss underline underline-offset-2"
                  onClick={() => onSelect(product.operation)}
                >
                  View on map
                </button>
                {geotiff && (
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 text-xs text-stone hover:text-moss"
                    onClick={() => onDownload(geotiff)}
                  >
                    <Download className="h-3 w-3" />
                    Download
                  </button>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
