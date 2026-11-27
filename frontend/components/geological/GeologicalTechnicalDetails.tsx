"use client";

import { useState } from "react";

type Props = {
  payload: Record<string, unknown>;
};

export function GeologicalTechnicalDetails({ payload }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <section
      className="rounded-2xl border border-meadow bg-chalk"
      data-testid="geological-technical-details"
    >
      <button
        type="button"
        className="flex w-full items-center justify-between px-4 py-3 text-left"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span>
          <span className="block font-display text-lg text-bark">
            Technical details
          </span>
          <span className="text-xs text-stone">
            Validation report, statistics, provenance, compatibility record and
            raw data.
          </span>
        </span>
        <span className="rounded-lg border border-meadow px-3 py-1 text-xs text-moss">
          {open ? "Hide" : "Show"}
        </span>
      </button>
      {open && (
        <pre className="max-h-[28rem] overflow-auto border-t border-meadow/70 bg-mist/40 p-4 text-[11px] text-bark">
          {JSON.stringify(payload, null, 2)}
        </pre>
      )}
    </section>
  );
}
