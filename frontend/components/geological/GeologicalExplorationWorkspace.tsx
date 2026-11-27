"use client";

import { useMemo } from "react";
import type { MagneticProductEntry } from "@/lib/geologicalApi";
import type { DirectionBin, LineamentFeature } from "@/lib/geologicalPresentation";
import {
  previewFilenameForProduct,
  productDisplayTitle,
} from "@/lib/geologicalPresentation";
import { AuthenticatedDerivedImage } from "./AuthenticatedDerivedImage";
import { GeologicalLineamentCanvas } from "./GeologicalLineamentCanvas";
import { GeologicalLineamentPanel } from "./GeologicalLineamentPanel";
import { TmiSurveyPreview } from "./TmiSurveyPreview";
import type { TmiPreview } from "@/lib/geologicalApi";

type Props = {
  geoId: string;
  products: MagneticProductEntry[];
  activeOperation: string;
  onChangeOperation: (operation: string) => void;
  showLineaments: boolean;
  onToggleLineaments: (value: boolean) => void;
  lineamentFeatures: LineamentFeature[];
  selectedLineamentId: string | null;
  onSelectLineament: (id: string) => void;
  directionBins: DirectionBin[];
  lineamentCrs: string | null;
  tmiPreview: TmiPreview | null;
  valueRangeLabel: string | null;
};

export function GeologicalExplorationWorkspace({
  geoId,
  products,
  activeOperation,
  onChangeOperation,
  showLineaments,
  onToggleLineaments,
  lineamentFeatures,
  selectedLineamentId,
  onSelectLineament,
  directionBins,
  lineamentCrs,
  tmiPreview,
  valueRangeLabel,
}: Props) {
  const activeProduct = products.find((p) => p.operation === activeOperation);
  const previewFile = activeProduct
    ? previewFilenameForProduct(activeProduct)
    : null;
  const selected = useMemo(
    () =>
      lineamentFeatures.find((f) => f.id === selectedLineamentId) || null,
    [lineamentFeatures, selectedLineamentId],
  );

  const layerOptions = products.filter(
    (p) => p.preview_exists || p.operation === activeOperation,
  );

  return (
    <section
      className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(18rem,0.9fr)]"
      data-testid="geological-exploration-workspace"
    >
      <div className="relative min-h-[22rem] overflow-hidden rounded-2xl border border-meadow bg-mist">
        <div className="absolute left-3 top-3 z-10 max-w-[14rem] space-y-1 rounded-xl border border-meadow/80 bg-chalk/95 p-2 shadow-soft">
          <p className="px-1 font-mono text-[9px] uppercase tracking-wider text-leaf">
            Map layers
          </p>
          {layerOptions.map((product) => (
            <label
              key={product.operation}
              className="flex cursor-pointer items-center gap-2 rounded-lg px-1.5 py-1 text-[11px] text-bark hover:bg-mist"
            >
              <input
                type="radio"
                name="geological-layer"
                checked={activeOperation === product.operation}
                onChange={() => onChangeOperation(product.operation)}
              />
              <span>{productDisplayTitle(product)}</span>
            </label>
          ))}
          <label className="flex cursor-pointer items-center gap-2 rounded-lg px-1.5 py-1 text-[11px] text-bark hover:bg-mist">
            <input
              type="checkbox"
              checked={showLineaments}
              onChange={(e) => onToggleLineaments(e.target.checked)}
            />
            <span>
              Candidate lineaments
              {lineamentFeatures.length
                ? ` · ${lineamentFeatures.length}`
                : ""}
            </span>
          </label>
        </div>

        {showLineaments && lineamentFeatures.length > 0 ? (
          <GeologicalLineamentCanvas
            features={lineamentFeatures}
            selectedId={selectedLineamentId}
            onSelect={onSelectLineament}
            crsLabel={lineamentCrs}
          />
        ) : previewFile ? (
          <AuthenticatedDerivedImage
            geoId={geoId}
            filename={previewFile}
            alt={productDisplayTitle(activeProduct || { operation: activeOperation })}
            className="h-full min-h-[22rem] w-full object-contain bg-[#eef3ea]"
          />
        ) : tmiPreview?.ok ? (
          <div className="h-full min-h-[22rem] p-3">
            <TmiSurveyPreview preview={tmiPreview} />
          </div>
        ) : (
          <div className="flex h-full min-h-[22rem] items-center justify-center px-6 text-center text-sm text-stone">
            No spatial preview is available yet. Declare metadata, validate, and
            process the grid to generate map products.
          </div>
        )}

        {valueRangeLabel && !showLineaments && (
          <div className="absolute bottom-3 left-3 rounded-lg border border-meadow/80 bg-chalk/95 px-3 py-2 text-[10px] text-stone">
            <p className="font-medium text-bark">
              {productDisplayTitle(activeProduct || { operation: "tmi" })}
            </p>
            <p>{valueRangeLabel}</p>
          </div>
        )}
      </div>

      <GeologicalLineamentPanel
        features={lineamentFeatures}
        selected={selected}
        bins={directionBins}
        onSelect={onSelectLineament}
        onZoomAll={() => {
          if (lineamentFeatures[0]) onSelectLineament(lineamentFeatures[0].id);
        }}
        sourceLayerLabel={
          activeProduct
            ? productDisplayTitle(activeProduct)
            : "Edge strength"
        }
      />
    </section>
  );
}
