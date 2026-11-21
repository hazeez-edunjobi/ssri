"use client";

import {
  ASSESSMENT_PREVIEW_LABEL,
  groupDemoScenariosByLocation,
  type DemoScenarioSummary,
} from "@/lib/presentationDemo";

type Props = {
  scenarios: DemoScenarioSummary[];
  selectedKey: string | null;
  onSelect: (scenario: DemoScenarioSummary) => void;
};

export function PresentationScenarioPicker({
  scenarios,
  selectedKey,
  onSelect,
}: Props) {
  if (scenarios.length === 0) return null;

  const grouped = groupDemoScenariosByLocation(scenarios);
  const locations = Array.from(grouped.keys());

  return (
    <div
      className="mt-4 rounded-lg border border-meadow bg-mist/70 px-3 py-3"
      data-testid="presentation-scenario-picker"
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] uppercase tracking-widest text-stone">
          Scenario library
        </p>
        <span
          className="font-mono text-[10px] uppercase tracking-widest text-leaf"
          data-testid="presentation-demo-banner"
        >
          {ASSESSMENT_PREVIEW_LABEL}
        </span>
      </div>
      <label className="mt-3 block text-[11px] text-stone">
        Location &amp; profile
        <select
          className="mt-1 w-full rounded border border-meadow bg-chalk px-2 py-1.5 text-xs text-bark"
          value={selectedKey ?? ""}
          data-testid="presentation-scenario-select"
          onChange={(event) => {
            const next = scenarios.find((s) => s.key === event.target.value);
            if (next) onSelect(next);
          }}
        >
          <option value="">Map click / manual coordinates</option>
          {locations.map((location) => (
            <optgroup key={location} label={location}>
              {(grouped.get(location) ?? []).map((scenario) => (
                <option key={scenario.key} value={scenario.key}>
                  {scenario.profile_label} ({scenario.assessment_type})
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>
      {selectedKey && (
        <p
          className="mt-2 text-[10px] text-stone"
          data-testid="presentation-scenario-hint"
        >
          Map centred on the selected catalogue coordinates.
        </p>
      )}
    </div>
  );
}
