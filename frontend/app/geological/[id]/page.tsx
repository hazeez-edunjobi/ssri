"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { PlatformShell } from "@/components/platform/PlatformShell";
import {
  declareGeologicalMetadata,
  getGeologicalDataset,
  setGeologicalActivation,
  validateGeologicalDataset,
  type GeologicalDataset,
  type InspectReport,
  type ValidationReport,
} from "@/lib/geologicalApi";

export default function GeologicalDetailPage() {
  const params = useParams();
  const geoId = String(params.id || "");
  const [dataset, setDataset] = useState<GeologicalDataset | null>(null);
  const [inspect, setInspect] = useState<InspectReport | null>(null);
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [measurementType, setMeasurementType] = useState("");
  const [crs, setCrs] = useState("");
  const [units, setUnits] = useState("");
  const [description, setDescription] = useState("");
  const [sourceClient, setSourceClient] = useState("");
  const [xCol, setXCol] = useState("X");
  const [yCol, setYCol] = useState("Y");
  const [zCol, setZCol] = useState("Z");
  const [ack, setAck] = useState<string[]>([]);

  const applyDetail = useCallback(
    (body: Awaited<ReturnType<typeof getGeologicalDataset>>) => {
      setDataset(body.dataset);
      setInspect(body.inspect || null);
      setValidation(body.validation || null);
      setMeasurementType(body.dataset.measurement_type || "");
      setCrs(body.dataset.crs || "");
      setUnits(body.dataset.units || "");
      setDescription(body.dataset.description || "");
      setSourceClient(body.dataset.source_client || "");
      const cols = body.inspect?.detected_columns;
      const headers = body.inspect?.header_row;
      if (headers && cols) {
        setXCol(headers[cols.x ?? 0] || "X");
        setYCol(headers[cols.y ?? 1] || "Y");
        setZCol(headers[cols.z ?? 2] || "Z");
      }
    },
    [],
  );

  const reload = useCallback(() => {
    if (!geoId) return;
    getGeologicalDataset(geoId)
      .then(applyDetail)
      .catch((err: Error) => setError(err.message));
  }, [geoId, applyDetail]);

  useEffect(() => {
    if (!geoId) return;
    let cancelled = false;
    getGeologicalDataset(geoId)
      .then((body) => {
        if (!cancelled) applyDetail(body);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [geoId, applyDetail]);

  const warnNames = useMemo(
    () =>
      (validation?.checks || [])
        .filter((c) => c.status === "WARN")
        .map((c) => c.name),
    [validation],
  );

  async function onDeclare(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body: Record<string, unknown> = {
        measurement_type: measurementType || null,
        crs: crs || null,
        units: units || null,
        description,
        source_client: sourceClient,
      };
      if (dataset?.asset_kind === "point_grid_csv") {
        body.x_column = xCol;
        body.y_column = yCol;
        body.z_column = zCol;
      }
      await declareGeologicalMetadata(geoId, body);
      setNotice("Metadata saved. Run validation next.");
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Declare failed");
    } finally {
      setBusy(false);
    }
  }

  async function onValidate() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body = await validateGeologicalDataset(geoId);
      setDataset(body.dataset);
      setValidation(body.validation);
      setNotice(`Validation ${body.validation.overall}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
      reload();
    } finally {
      setBusy(false);
    }
  }

  async function onActivate(status: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body = await setGeologicalActivation(geoId, {
        activation_status: status,
        acknowledged_warnings: status === "inactive" ? [] : ack,
      });
      setDataset(body.dataset);
      setNotice(`Activation set to ${body.dataset.activation_status}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Activation failed");
    } finally {
      setBusy(false);
    }
  }

  if (!dataset && !error) {
    return (
      <PlatformShell>
        <p className="text-sm text-stone">Loading dataset…</p>
      </PlatformShell>
    );
  }

  return (
    <PlatformShell>
      <Link href="/geological" className="text-xs text-stone underline">
        ← Geological catalogue
      </Link>
      <h1 className="mt-3 font-display text-2xl">{dataset?.display_name || geoId}</h1>
      <p className="mt-1 text-sm text-stone">
        {dataset?.geo_id} · {dataset?.asset_kind} · validation{" "}
        {dataset?.validation_status} · activation {dataset?.activation_status}
      </p>
      <p className="mt-2 text-xs text-stone">
        Scientific status: {dataset?.scientific_validation_status || "NOT_VALIDATED"}.
        Catalogue activation does not feed live 13-channel inference.
      </p>

      {error && <p className="mt-4 text-sm text-amber-900">{error}</p>}
      {notice && <p className="mt-4 text-sm text-leaf">{notice}</p>}

      <section className="mt-8 rounded-2xl border border-meadow bg-chalk p-5">
        <h2 className="font-display text-lg">Inspect</h2>
        {!inspect || Object.keys(inspect).length === 0 ? (
          <p className="mt-2 text-sm text-stone">No inspect report yet.</p>
        ) : (
          <dl className="mt-3 grid gap-2 text-sm md:grid-cols-2">
            <div>
              <dt className="text-xs text-stone">Rows</dt>
              <dd>{String(inspect.row_count ?? "—")}</dd>
            </div>
            <div>
              <dt className="text-xs text-stone">Suggested columns</dt>
              <dd>{JSON.stringify(inspect.detected_columns || {})}</dd>
            </div>
            <div>
              <dt className="text-xs text-stone">Negative Z count</dt>
              <dd>{String(inspect.negative_z_count ?? "—")}</dd>
            </div>
            <div>
              <dt className="text-xs text-stone">Missing lattice cells</dt>
              <dd>{String(inspect.missing_lattice_cells ?? "—")}</dd>
            </div>
            <div className="md:col-span-2">
              <dt className="text-xs text-stone">Coverage bbox</dt>
              <dd>{JSON.stringify(inspect.coverage_bbox || dataset?.coverage_bbox || null)}</dd>
            </div>
          </dl>
        )}
      </section>

      <form
        onSubmit={onDeclare}
        className="mt-6 grid gap-3 rounded-2xl border border-meadow bg-chalk p-5 md:grid-cols-2"
      >
        <h2 className="font-display text-lg md:col-span-2">Declare metadata</h2>
        {dataset?.asset_kind === "point_grid_csv" ? (
          <label className="text-xs md:col-span-2">
            Measurement type
            <select
              className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
              value={measurementType}
              onChange={(e) => setMeasurementType(e.target.value)}
              required
            >
              <option value="">Select…</option>
              <option value="overburden_thickness">overburden_thickness</option>
              <option value="depth_to_bedrock">depth_to_bedrock</option>
            </select>
          </label>
        ) : (
          <p className="text-xs text-stone md:col-span-2">
            Measurement type is fixed as lineament_vectors for this asset.
          </p>
        )}
        <label className="text-xs">
          CRS (EPSG or WKT)
          <input
            className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
            value={crs}
            onChange={(e) => setCrs(e.target.value)}
            placeholder="EPSG:32631"
            required
          />
        </label>
        {dataset?.asset_kind === "point_grid_csv" && (
          <label className="text-xs">
            Units
            <input
              className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
              value={units}
              onChange={(e) => setUnits(e.target.value)}
              placeholder="m"
              required
            />
          </label>
        )}
        {dataset?.asset_kind === "point_grid_csv" && (
          <>
            <label className="text-xs">
              X column
              <input
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={xCol}
                onChange={(e) => setXCol(e.target.value)}
              />
            </label>
            <label className="text-xs">
              Y column
              <input
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={yCol}
                onChange={(e) => setYCol(e.target.value)}
              />
            </label>
            <label className="text-xs">
              Z / value column
              <input
                className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
                value={zCol}
                onChange={(e) => setZCol(e.target.value)}
              />
            </label>
          </>
        )}
        <label className="text-xs md:col-span-2">
          Description
          <input
            className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <label className="text-xs md:col-span-2">
          Source / provenance
          <input
            className="mt-1 w-full rounded-lg border border-meadow bg-mist px-3 py-2"
            value={sourceClient}
            onChange={(e) => setSourceClient(e.target.value)}
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="rounded-xl bg-leaf px-4 py-2 text-sm text-chalk disabled:opacity-50 md:w-fit"
        >
          Save declaration
        </button>
      </form>

      <div className="mt-6 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={onValidate}
          className="rounded-xl border border-meadow px-4 py-2 text-sm disabled:opacity-50"
        >
          Run validation
        </button>
      </div>

      {validation && Object.keys(validation).length > 0 && (
        <section className="mt-6 rounded-2xl border border-meadow bg-chalk p-5">
          <h2 className="font-display text-lg">
            Validation · {validation.overall || "—"}
          </h2>
          <ul className="mt-3 space-y-2 text-sm">
            {(validation.checks || []).map((check) => (
              <li key={check.name} className="rounded-lg border border-meadow/60 px-3 py-2">
                <span className="font-medium">
                  {check.name}: {check.status}
                </span>
                <p className="text-stone">{check.message}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mt-6 rounded-2xl border border-meadow bg-chalk p-5">
        <h2 className="font-display text-lg">Activation</h2>
        <p className="mt-1 text-xs text-stone">
          reporting_only / approved enable offline coverage and feature apply — not live
          inference.
        </p>
        {warnNames.length > 0 && (
          <fieldset className="mt-3 space-y-1 text-xs">
            <legend>Acknowledge warnings</legend>
            {warnNames.map((name) => (
              <label key={name} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={ack.includes(name)}
                  onChange={(e) => {
                    setAck((prev) =>
                      e.target.checked
                        ? [...prev, name]
                        : prev.filter((n) => n !== name),
                    );
                  }}
                />
                {name}
              </label>
            ))}
          </fieldset>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            className="rounded-xl border border-meadow px-3 py-2 text-sm"
            onClick={() => onActivate("inactive")}
          >
            Deactivate
          </button>
          <button
            type="button"
            disabled={busy || dataset?.validation_status !== "validated"}
            className="rounded-xl bg-leaf px-3 py-2 text-sm text-chalk disabled:opacity-50"
            onClick={() => onActivate("reporting_only")}
          >
            Activate reporting_only
          </button>
        </div>
      </section>
    </PlatformShell>
  );
}
