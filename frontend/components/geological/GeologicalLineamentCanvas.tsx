"use client";

import { GeologicalSurveyMap } from "./GeologicalSurveyMap";
import type { MagneticProductEntry, TmiPreview } from "@/lib/geologicalApi";
import type { LineamentFeature } from "@/lib/geologicalPresentation";

type LegacyProps = {
  features: LineamentFeature[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  crsLabel?: string | null;
  geoId?: string;
  products?: MagneticProductEntry[];
  activeOperation?: string;
  onChangeOperation?: (operation: string) => void;
  showLineaments?: boolean;
  onToggleLineaments?: (value: boolean) => void;
  tmiPreview?: TmiPreview | null;
  griddingProvenance?: Record<string, unknown> | null;
  valueRangeLabel?: string | null;
};

/**
 * Legacy entry point — delegates to GeologicalSurveyMap.
 * New code should import GeologicalSurveyMap directly.
 */
export function GeologicalLineamentCanvas({
  features,
  selectedId,
  onSelect,
  crsLabel,
  geoId = "",
  products = [],
  activeOperation = "tmi",
  onChangeOperation = () => undefined,
  showLineaments = true,
  onToggleLineaments = () => undefined,
  tmiPreview = null,
  griddingProvenance = null,
  valueRangeLabel = null,
}: LegacyProps) {
  return (
    <GeologicalSurveyMap
      geoId={geoId}
      products={products}
      activeOperation={activeOperation}
      onChangeOperation={onChangeOperation}
      showLineaments={showLineaments}
      onToggleLineaments={onToggleLineaments}
      lineamentFeatures={features}
      selectedLineamentId={selectedId}
      onSelectLineament={onSelect}
      lineamentCrs={crsLabel ?? null}
      tmiPreview={tmiPreview}
      griddingProvenance={griddingProvenance}
      valueRangeLabel={valueRangeLabel}
    />
  );
}
