"use client";

import type { HistoryEntry } from "@/lib/geologicalPresentation";

export function GeologicalProcessingTimeline({
  entries,
}: {
  entries: HistoryEntry[];
}) {
  if (!entries.length) {
    return (
      <div className="rounded-2xl border border-dashed border-meadow bg-chalk px-4 py-6 text-sm text-stone">
        No processing history recorded yet for this dataset.
      </div>
    );
  }

  return (
    <section data-testid="geological-processing-history">
      <h2 className="font-display text-lg text-bark">Processing history</h2>
      <ol className="relative mt-4 space-y-4 border-l border-meadow pl-4">
        {entries.map((entry) => (
          <li key={entry.id} className="relative">
            <span
              className={`absolute -left-[1.35rem] top-1.5 h-2.5 w-2.5 rounded-full ${
                entry.tone === "warn" ? "bg-amber-500" : "bg-leaf"
              }`}
            />
            <p className="text-sm font-medium text-bark">{entry.title}</p>
            <p className="text-xs text-stone">{entry.detail}</p>
            {entry.at && (
              <p className="mt-0.5 font-mono text-[10px] text-stone/80">
                {new Date(entry.at).toLocaleString()}
              </p>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
