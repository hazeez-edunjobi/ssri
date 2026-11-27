"use client";

import type { DirectionBin, LineamentFeature } from "@/lib/geologicalPresentation";
import {
  formatAzimuthLabel,
  formatLengthKm,
} from "@/lib/geologicalPresentation";

type Props = {
  features: LineamentFeature[];
  selected: LineamentFeature | null;
  bins: DirectionBin[];
  onSelect: (id: string) => void;
  onZoomAll: () => void;
  sourceLayerLabel: string;
};

export function GeologicalLineamentPanel({
  features,
  selected,
  bins,
  onSelect,
  onZoomAll,
  sourceLayerLabel,
}: Props) {
  const maxBin = Math.max(1, ...bins.map((b) => b.count));

  return (
    <aside
      className="flex h-full flex-col gap-4 rounded-2xl border border-meadow bg-chalk p-4"
      data-testid="geological-lineament-panel"
    >
      <div>
        <p className="font-mono text-[10px] uppercase tracking-widest text-leaf">
          Lineament details
        </p>
        {selected ? (
          <>
            <h3 className="mt-1 font-display text-lg text-bark">
              Lineament #{selected.index}
            </h3>
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-stone">Orientation</dt>
                <dd className="font-medium text-bark">
                  {formatAzimuthLabel(selected.azimuthDeg)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-stone">Length</dt>
                <dd className="font-medium text-bark">
                  {formatLengthKm(selected.lengthM)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-stone">Confidence</dt>
                <dd className="font-medium text-bark">Not scored</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-stone">Source layer</dt>
                <dd className="font-medium text-bark">{sourceLayerLabel}</dd>
              </div>
            </dl>
            <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-950">
              {selected.interpretation ||
                "A candidate trend in the magnetic data. It is not a confirmed fault or fracture."}
            </p>
          </>
        ) : (
          <p className="mt-2 text-sm text-stone">
            Select a candidate lineament on the map to inspect length and
            orientation.
          </p>
        )}
      </div>

      <div>
        <h4 className="text-sm font-medium text-bark">
          All {features.length} candidates by direction
        </h4>
        <ul className="mt-3 space-y-1.5">
          {bins.map((bin) => (
            <li key={bin.key} className="flex items-center gap-2 text-xs">
              <span className="w-6 text-stone">{bin.label}</span>
              <span className="h-2 flex-1 overflow-hidden rounded-full bg-meadow/40">
                <span
                  className="block h-full rounded-full bg-leaf/80"
                  style={{ width: `${(bin.count / maxBin) * 100}%` }}
                />
              </span>
              <span className="w-6 text-right text-stone">{bin.count}</span>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onZoomAll}
            className="rounded-lg border border-meadow px-3 py-1.5 text-xs text-bark"
          >
            Zoom to all
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto border-t border-meadow/70 pt-3">
        <p className="text-[11px] font-medium text-stone">Records</p>
        <ul className="mt-2 space-y-1">
          {features.slice(0, 80).map((feature) => (
            <li key={feature.id}>
              <button
                type="button"
                onClick={() => onSelect(feature.id)}
                className={`flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-xs ${
                  selected?.id === feature.id
                    ? "bg-meadow/50 text-bark"
                    : "text-stone hover:bg-mist"
                }`}
              >
                <span>#{feature.index}</span>
                <span>{formatAzimuthLabel(feature.azimuthDeg)}</span>
                <span>{formatLengthKm(feature.lengthM)}</span>
              </button>
            </li>
          ))}
          {features.length > 80 && (
            <li className="px-2 text-[11px] text-stone">
              Showing first 80 of {features.length} candidates.
            </li>
          )}
        </ul>
      </div>
    </aside>
  );
}
