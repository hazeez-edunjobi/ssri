"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { RequireSession } from "@/components/auth/RequireSession";
import { PlatformShell } from "@/components/platform/PlatformShell";
import {
  getAssessmentHistoryDetail,
  type AssessmentHistoryDetailResponse,
} from "@/lib/api";
import {
  dashboardHrefForHistory,
  formatHazardLine,
  formatHistoryCoords,
} from "@/lib/assessmentHistory";

function AssessmentDetailWorkspace() {
  const params = useParams();
  const assessmentId = String(params.id || "");
  const [data, setData] = useState<AssessmentHistoryDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!assessmentId) return;
    setLoading(true);
    setError(null);
    try {
      const body = await getAssessmentHistoryDetail(assessmentId);
      setData(body);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : "Could not load assessment detail");
    } finally {
      setLoading(false);
    }
  }, [assessmentId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const summary = data?.summary;
  const mapHref = summary ? dashboardHrefForHistory(summary) : null;
  const assessment = data?.assessment || {};
  const notes = Array.isArray(assessment.notes)
    ? (assessment.notes as unknown[]).map(String)
    : [];
  const spatialUrl =
    typeof assessment.spatial_output_url === "string"
      ? assessment.spatial_output_url
      : null;

  return (
    <PlatformShell>
      <Link href="/assessments" className="text-sm font-semibold text-moss">
        ← Assessment history
      </Link>
      <h1 className="mt-4 font-display text-2xl" data-testid="assessment-detail-heading">
        {assessmentId || "Assessment"}
      </h1>
      <p className="mt-2 text-sm text-stone">
        Persisted assess response. Relative rankings only; not calibrated probabilities.
      </p>

      {loading && (
        <p className="mt-8 text-sm text-stone" data-testid="assessment-detail-loading">
          Loading assessment…
        </p>
      )}

      {!loading && error && (
        <div
          className="mt-6 rounded-2xl border border-amber-300 bg-amber-50 p-5 text-sm"
          data-testid="assessment-detail-error"
        >
          <p>{error}</p>
          <button
            type="button"
            className="mt-3 font-semibold text-moss underline"
            onClick={() => void load()}
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && summary && (
        <div className="mt-6 space-y-4" data-testid="assessment-detail">
          <section className="rounded-2xl border border-meadow bg-chalk p-5 text-sm">
            <div className="text-xs text-stone">{summary.modified_at || "Date unknown"}</div>
            <div className="mt-2">{formatHistoryCoords(summary)}</div>
            <ul className="mt-3 space-y-1 text-xs">
              {(summary.hazards || []).map((hazard, index) => (
                <li key={`${summary.assessment_id}-${hazard.hazard_type || index}`}>
                  {formatHazardLine(hazard)}
                </li>
              ))}
            </ul>
            <div className="mt-4 flex flex-wrap gap-3 text-xs">
              {mapHref && (
                <Link href={mapHref} className="font-semibold text-moss">
                  Open on assessment map
                </Link>
              )}
              {spatialUrl && (
                <a
                  href={spatialUrl}
                  className="font-semibold text-moss"
                  target="_blank"
                  rel="noreferrer"
                >
                  Spatial output link
                </a>
              )}
            </div>
          </section>

          {data?.note && <p className="text-xs text-stone">{data.note}</p>}

          {notes.length > 0 && (
            <section className="rounded-2xl border border-meadow bg-chalk p-5">
              <h2 className="font-display text-lg">Notes</h2>
              <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-stone">
                {notes.map((note) => (
                  <li key={note.slice(0, 80)}>{note}</li>
                ))}
              </ul>
            </section>
          )}

          <section className="rounded-2xl border border-meadow bg-chalk p-5">
            <h2 className="font-display text-lg">Stored payload (available fields)</h2>
            <pre className="mt-3 max-h-96 overflow-auto rounded-lg bg-mist p-3 text-xs">
              {JSON.stringify(assessment, null, 2)}
            </pre>
          </section>
        </div>
      )}
    </PlatformShell>
  );
}

export default function AssessmentDetailPage() {
  return (
    <RequireSession nextPath="/assessments">
      <AssessmentDetailWorkspace />
    </RequireSession>
  );
}
