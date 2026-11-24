"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { RequireSession } from "@/components/auth/RequireSession";
import { PlatformShell } from "@/components/platform/PlatformShell";
import {
  listAssessmentHistory,
  type AssessmentHistoryItem,
  type AssessmentHistoryResponse,
} from "@/lib/api";
import {
  dashboardHrefForHistory,
  formatHazardLine,
  formatHistoryCoords,
  historyEmptyMessage,
} from "@/lib/assessmentHistory";

const PAGE_SIZE = 25;

function AssessmentHistoryWorkspace() {
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<AssessmentHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (nextOffset: number) => {
    setLoading(true);
    setError(null);
    try {
      const body = await listAssessmentHistory({
        limit: PAGE_SIZE,
        offset: nextOffset,
      });
      setData(body);
      setOffset(nextOffset);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : "Could not load assessment history");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load(0);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const items: AssessmentHistoryItem[] = data?.assessments ?? [];
  const total = data?.total ?? items.length;
  const hasMore = Boolean(data?.has_more);

  return (
    <PlatformShell>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl" data-testid="assessments-heading">
            Assessment history
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-stone">
            Operational archive of persisted map assessments. Scores are relative
            susceptibility rankings and remain NOT_VALIDATED unless independently
            validated.
          </p>
        </div>
        <Link
          href="/dashboard"
          className="rounded-xl bg-leaf px-4 py-2 text-sm text-chalk"
        >
          New assessment
        </Link>
      </div>

      {data?.note && (
        <p className="mt-4 text-xs text-stone" data-testid="assessments-api-note">
          {data.note}
        </p>
      )}

      {loading && (
        <p className="mt-8 text-sm text-stone" data-testid="assessments-loading">
          Loading assessment history…
        </p>
      )}

      {!loading && error && (
        <div
          className="mt-6 rounded-2xl border border-amber-300 bg-amber-50 p-5 text-sm text-amber-950"
          data-testid="assessments-error"
        >
          <p>{error}</p>
          <button
            type="button"
            className="mt-3 font-semibold text-moss underline"
            onClick={() => void load(offset)}
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <p className="mt-8 text-sm text-stone" data-testid="assessments-empty">
          {historyEmptyMessage(total)}
        </p>
      )}

      {!loading && !error && items.length > 0 && (
        <ul className="mt-6 space-y-3" data-testid="assessments-list">
          {items.map((item) => {
            const mapHref = dashboardHrefForHistory(item);
            return (
              <li
                key={item.assessment_id}
                className="rounded-2xl border border-meadow bg-chalk p-5 text-sm"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <Link
                      href={`/assessments/${encodeURIComponent(item.assessment_id)}`}
                      className="font-mono text-sm font-semibold text-moss"
                    >
                      {item.assessment_id}
                    </Link>
                    <div className="mt-1 text-xs text-stone">
                      {item.modified_at || "Date unknown"}
                      {item.model_version ? ` · ${item.model_version}` : ""}
                      {item.scientific_notes_present ? " · NOT_VALIDATED note present" : ""}
                    </div>
                    <div className="mt-2 text-stone">
                      {formatHistoryCoords(item)}
                      {item.aoi_source ? ` · ${item.aoi_source}` : ""}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-3 text-xs">
                    <Link
                      href={`/assessments/${encodeURIComponent(item.assessment_id)}`}
                      className="font-semibold text-moss"
                    >
                      Details
                    </Link>
                    {mapHref && (
                      <Link href={mapHref} className="font-semibold text-moss">
                        Open map
                      </Link>
                    )}
                  </div>
                </div>
                <ul className="mt-3 space-y-1 text-xs text-bark">
                  {(item.hazards || []).map((hazard, index) => (
                    <li key={`${item.assessment_id}-${hazard.hazard_type || index}`}>
                      {formatHazardLine(hazard)}
                    </li>
                  ))}
                  {(!item.hazards || item.hazards.length === 0) && (
                    <li className="text-stone">No hazard scores stored on this record.</li>
                  )}
                </ul>
                {item.parse_error && (
                  <p className="mt-2 text-xs text-amber-900">Parse issue: {item.parse_error}</p>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {!loading && !error && (offset > 0 || hasMore) && (
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            disabled={offset <= 0}
            className="rounded-xl border border-meadow bg-chalk px-4 py-2 text-sm disabled:opacity-40"
            onClick={() => void load(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </button>
          <button
            type="button"
            disabled={!hasMore}
            className="rounded-xl border border-meadow bg-chalk px-4 py-2 text-sm disabled:opacity-40"
            onClick={() => void load(offset + PAGE_SIZE)}
          >
            Next
          </button>
          <span className="self-center text-xs text-stone">
            Showing {offset + 1}–{offset + items.length} of {total}
          </span>
        </div>
      )}
    </PlatformShell>
  );
}

export default function AssessmentsPage() {
  return (
    <RequireSession nextPath="/assessments">
      <AssessmentHistoryWorkspace />
    </RequireSession>
  );
}
