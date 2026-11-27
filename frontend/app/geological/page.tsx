"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { PlatformShell } from "@/components/platform/PlatformShell";
import {
  createGeologicalDataset,
  listGeologicalDatasets,
  queryGeologicalCoverage,
  uploadGeologicalFile,
  type GeologicalDataset,
} from "@/lib/geologicalApi";

const PAGE_SIZE = 20;

export default function GeologicalListPage() {
  const [datasets, setDatasets] = useState<GeologicalDataset[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [lastUploadedId, setLastUploadedId] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [assetKind, setAssetKind] = useState<"point_grid_csv" | "vector_lineament">(
    "point_grid_csv",
  );
  const [sourceClient, setSourceClient] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [filterKind, setFilterKind] = useState<string>("");
  // Coverage probe
  const [bboxText, setBboxText] = useState("2.9,6.9,3.6,7.6");
  const [aoiCrs, setAoiCrs] = useState("EPSG:4326");
  const [coverage, setCoverage] = useState<Record<string, unknown> | null>(null);

  const reload = useCallback((nextOffset = 0, kind = filterKind) => {
    setError(null);
    listGeologicalDatasets({
      limit: PAGE_SIZE,
      offset: nextOffset,
      asset_kind: kind || undefined,
    })
      .then((body) => {
        setDatasets(body.datasets);
        setTotal(body.total);
        setOffset(body.offset);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message);
        setLoading(false);
      });
  }, [filterKind]);

  useEffect(() => {
    let cancelled = false;
    listGeologicalDatasets({
      limit: PAGE_SIZE,
      offset: 0,
      asset_kind: filterKind || undefined,
    })
      .then((body) => {
        if (cancelled) return;
        setDatasets(body.datasets);
        setTotal(body.total);
        setOffset(body.offset);
        setLoading(false);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filterKind]);

  async function onCreateAndUpload(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    if (!displayName.trim()) {
      setError("Give the dataset a display name.");
      return;
    }
    if (!file) {
      setError("Choose a file to upload.");
      return;
    }
    setUploading(true);
    setProgress(0);
    try {
      const created = await createGeologicalDataset({
        display_name: displayName.trim(),
        asset_kind: assetKind,
        source_client: sourceClient.trim(),
      });
      const geoId = created.dataset.geo_id;
      await uploadGeologicalFile(geoId, file, setProgress);
      setLastUploadedId(geoId);
      setSuccess(
        file.name.toLowerCase().includes("abeokuta") ||
          file.name.toLowerCase().includes("260")
          ? `Uploaded as ${geoId}. Open the dataset and click “Apply Abeokuta TMI metadata” (X=easting, Y=northing, Z=TMI; source EPSG:32632 → processing EPSG:32631 → display EPSG:4326). Stay in Geological — do not create a Stage 2.5 entry under Datasets.`
          : `Uploaded as ${geoId}. Open the dataset to declare columns, source CRS, and measurement type before validation. Stay in Geological — Datasets is only for Stage 2.5 training packages.`,
      );
      setDisplayName("");
      setFile(null);
      setProgress(0);
      reload(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function onCoverage(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setCoverage(null);
    const parts = bboxText.split(",").map((p) => Number(p.trim()));
    if (parts.length !== 4 || parts.some((n) => Number.isNaN(n))) {
      setError("AOI bbox must be four numbers: xmin,ymin,xmax,ymax");
      return;
    }
    try {
      const body = await queryGeologicalCoverage({
        aoi_bbox: parts,
        aoi_crs: aoiCrs || undefined,
      });
      setCoverage(body.coverage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Coverage query failed");
    }
  }

  return (
    <PlatformShell>
      <h1 className="font-display text-2xl">Geological datasets</h1>
      <p className="mt-2 max-w-2xl text-sm text-stone">
        Catalogue client point-grid CSVs (including TMI magnetic surveys), ZIPCSV, and
        lineament vectors separately from Stage 2.5 training. TMI is a conditioning
        measurement — not a hazard label and not the live EMAG2 magnetics channel.
        Availability here does not mean the layer was used in live assessment inference.
        Upload, declare, validate, and original download require an{" "}
        <strong className="font-medium text-ink">operator or admin</strong> session (or
        an API key with <code className="text-xs">manage_geological</code>). Ordinary
        signed-in users cannot mutate the catalogue. Scientific status remains
        NOT_VALIDATED.
      </p>

      <div className="mt-4 rounded-2xl border border-leaf/30 bg-mist/40 p-4 text-sm text-bark">
        <p className="font-medium">Before you upload</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-stone">
          <li>
            Point-grid CSV needs X, Y and a measurement column (Z). Column meanings are
            declared on the dataset detail page — they are not guessed.
          </li>
          <li>
            You must set the <strong>source CRS</strong> (EPSG). SSRI never assumes
            EPSG:4326. For Abeokuta Sheet 260 use the publication preset (source
            EPSG:32632 → processing EPSG:32631 → display EPSG:4326).
          </li>
          <li>
            Projected easting/northing values are not plotted on the world map until a
            verified transform to WGS84 exists.
          </li>
          <li>
            Validation outcomes: Ready / Ready with warnings / Blocked. Unsupported
            analyses stay disabled.
          </li>
        </ul>
      </div>

      <form
        onSubmit={onCreateAndUpload}
        className="mt-6 grid gap-3 rounded-2xl border border-meadow bg-chalk p-5 md:grid-cols-2"
      >
        <label className="text-xs">
          Display name
          <input
            className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
          />
        </label>
        <label className="text-xs">
          Asset kind
          <select
            className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
            value={assetKind}
            onChange={(e) =>
              setAssetKind(e.target.value as "point_grid_csv" | "vector_lineament")
            }
          >
            <option value="point_grid_csv">Point-grid CSV (X,Y,Z)</option>
            <option value="vector_lineament">Lineament vectors</option>
          </select>
        </label>
        <label className="text-xs">
          Source / client
          <input
            className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
            value={sourceClient}
            onChange={(e) => setSourceClient(e.target.value)}
          />
        </label>
        <label className="text-xs">
          File
          <input
            className="mt-1 w-full text-sm"
            type="file"
            accept={
              assetKind === "vector_lineament"
                ? ".geojson,.json,.zip,.gpkg"
                : ".csv,text/csv"
            }
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <button
          className="rounded-xl bg-leaf px-4 py-2 text-sm text-chalk disabled:opacity-50 md:col-span-2 md:w-fit"
          type="submit"
          disabled={uploading}
        >
          {uploading ? `Uploading… ${Math.round(progress * 100)}%` : "Create & upload"}
        </button>
      </form>

      {error && <p className="mt-4 text-sm text-amber-900">{error}</p>}
      {success && (
        <div className="mt-4 space-y-2 rounded-xl border border-leaf/30 bg-leaf/10 px-3 py-3 text-sm text-moss">
          <p>{success}</p>
          {lastUploadedId && (
            <Link
              href={`/geological/${lastUploadedId}`}
              className="inline-flex rounded-lg bg-moss px-3 py-1.5 text-xs text-chalk"
              data-testid="open-uploaded-geological-dataset"
            >
              Open dataset workspace
            </Link>
          )}
        </div>
      )}

      <div className="mt-8 flex flex-wrap items-center gap-3">
        <label className="text-xs">
          Filter kind
          <select
            className="ml-2 rounded-lg border border-meadow bg-mist px-2 py-1"
            value={filterKind}
            onChange={(e) => setFilterKind(e.target.value)}
          >
            <option value="">All</option>
            <option value="point_grid_csv">Point-grid CSV</option>
            <option value="vector_lineament">Lineaments</option>
          </select>
        </label>
        <span className="text-xs text-stone">
          {total} dataset{total === 1 ? "" : "s"}
        </span>
      </div>

      {loading ? (
        <p className="mt-6 text-sm text-stone">Loading catalogue…</p>
      ) : datasets.length === 0 ? (
        <p className="mt-6 text-sm text-stone">
          No geological datasets yet. Upload a CSV or lineament file above.
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-meadow rounded-2xl border border-meadow bg-chalk">
          {datasets.map((ds) => (
            <li key={ds.geo_id}>
              <Link
                href={`/geological/${ds.geo_id}`}
                className="flex flex-col gap-1 px-4 py-3 text-sm hover:bg-meadow/70 md:flex-row md:items-center md:justify-between"
              >
                <span>
                  <span className="font-medium">{ds.display_name}</span>
                  <span className="ml-2 text-xs text-stone">{ds.geo_id}</span>
                </span>
                <span className="text-xs text-stone">
                  {ds.asset_kind} · {ds.measurement_type || "undeclared"} · CRS{" "}
                  {ds.crs || "undeclared"}
                  {ds.working_crs ? ` → ${ds.working_crs}` : ""} ·{" "}
                  {ds.validation_status} · map{" "}
                  {ds.display_bbox_wgs84 ? "WGS84 footprint ready" : "no display footprint"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {total > PAGE_SIZE && (
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            className="rounded-lg border border-meadow px-3 py-1 text-xs disabled:opacity-40"
            disabled={offset <= 0}
            onClick={() => reload(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </button>
          <button
            type="button"
            className="rounded-lg border border-meadow px-3 py-1 text-xs disabled:opacity-40"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => reload(offset + PAGE_SIZE)}
          >
            Next
          </button>
        </div>
      )}

      <section className="mt-12">
        <h2 className="font-display text-xl">AOI bounding-box intersection</h2>
        <p className="mt-1 text-sm text-stone">
          Reports axis-aligned bounding-box overlap between the AOI and each
          activated, validated dataset footprint. This is not valid-cell or
          non-NoData coverage of the AOI. Does not change live risk scores.
        </p>
        <form onSubmit={onCoverage} className="mt-4 grid gap-3 md:grid-cols-3">
          <label className="text-xs md:col-span-2">
            AOI bbox (xmin,ymin,xmax,ymax)
            <input
              className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
              value={bboxText}
              onChange={(e) => setBboxText(e.target.value)}
            />
          </label>
          <label className="text-xs">
            AOI CRS (must be comparable to dataset CRS)
            <input
              className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
              value={aoiCrs}
              onChange={(e) => setAoiCrs(e.target.value)}
              placeholder="e.g. EPSG:32631"
            />
          </label>
          <button
            type="submit"
            className="rounded-xl border border-meadow px-4 py-2 text-sm md:w-fit"
          >
            Query bbox intersection
          </button>
        </form>
        {coverage && (
          <div className="mt-4 space-y-2">
            <p className="text-xs text-stone">
              Metric:{" "}
              {String(
                (coverage as { coverage_metric?: string }).coverage_metric ||
                  "aoi_bbox_intersection",
              )}
              . Fractions are bbox overlap ratios, not valid-data percentages.
            </p>
            <pre className="max-h-80 overflow-auto rounded-xl border border-meadow bg-mist p-3 text-xs">
              {JSON.stringify(coverage, null, 2)}
            </pre>
          </div>
        )}
      </section>
    </PlatformShell>
  );
}
