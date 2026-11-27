"use client";

import { useEffect, useMemo, useState } from "react";
import type { MagneticProductEntry, TmiPreview } from "@/lib/geologicalApi";
import type { DirectionBin, LineamentFeature } from "@/lib/geologicalPresentation";
import { GeologicalLineamentPanel } from "./GeologicalLineamentPanel";
import { GeologicalSurveyMap } from "./GeologicalSurveyMap";

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
  griddingProvenance?: Record<string, unknown> | null;
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
  griddingProvenance = null,
  valueRangeLabel,
}: Props) {
  const [focusToken, setFocusToken] = useState(0);
  const [focusMode, setFocusMode] = useState<"all" | "selected">("all");

  const selected = useMemo(
    () =>
      lineamentFeatures.find((f) => f.id === selectedLineamentId) || null,
    [lineamentFeatures, selectedLineamentId],
  );

  useEffect(() => {
    // Initial fit once features/extent become available.
    if (!lineamentFeatures.length && !tmiPreview?.survey_local && !griddingProvenance) {
      return;
    }
    const timer = window.setTimeout(() => {
      setFocusMode("all");
      setFocusToken((n) => n + 1);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [lineamentFeatures.length, tmiPreview?.survey_local, griddingProvenance]);

  const handleSelect = (id: string) => {
    onSelectLineament(id);
    setFocusMode("selected");
    setFocusToken((n) => n + 1);
  };

  const handleZoomAll = () => {
    setFocusMode("all");
    setFocusToken((n) => n + 1);
  };

  return (
    <section
      className="grid gap-4 lg:grid-cols-[minmax(0,1.65fr)_minmax(17rem,0.85fr)]"
      data-testid="geological-exploration-workspace"
    >
      <GeologicalSurveyMap
        geoId={geoId}
        products={products}
        activeOperation={activeOperation}
        onChangeOperation={onChangeOperation}
        showLineaments={showLineaments}
        onToggleLineaments={onToggleLineaments}
        lineamentFeatures={lineamentFeatures}
        selectedLineamentId={selectedLineamentId}
        onSelectLineament={handleSelect}
        lineamentCrs={lineamentCrs}
        tmiPreview={tmiPreview}
        griddingProvenance={griddingProvenance}
        valueRangeLabel={valueRangeLabel}
        focusToken={focusToken}
        focusMode={focusMode}
      />

      <GeologicalLineamentPanel
        features={lineamentFeatures}
        selected={selected}
        bins={directionBins}
        onSelect={handleSelect}
        onZoomAll={handleZoomAll}
        sourceLayerLabel="Edge strength (THG)"
      />
    </section>
  );
}
