/**
 * Presentation helpers for the geological dataset workspace.
 * Derived only from real dataset / magnetic / validation payloads.
 */

import type {
  GeologicalDataset,
  MagneticProductEntry,
  MagneticProducts,
  ValidationReport,
} from "./geologicalApi";
import { clientValidationOutcome } from "./validationOutcome.ts";

export type PipelineStepStatus = "complete" | "warning" | "pending" | "failed";

export type PipelineStep = {
  id: string;
  label: string;
  detail: string;
  status: PipelineStepStatus;
};

export type HistoryEntry = {
  id: string;
  title: string;
  detail: string;
  at: string | null;
  tone: "ok" | "warn" | "neutral";
};

export type LineamentFeature = {
  id: string;
  index: number;
  lengthM: number | null;
  azimuthDeg: number | null;
  nVertices: number | null;
  componentId: number | null;
  coordinates: [number, number][];
  interpretation: string | null;
};

export type DirectionBin = {
  key: string;
  label: string;
  count: number;
};

const CARD_ORDER = [
  "tmi",
  "gaussian",
  "analytic_signal",
  "first_horizontal_derivative",
] as const;

const FRIENDLY_TITLES: Record<string, string> = {
  tmi: "Magnetic field",
  gaussian: "Smoothed",
  analytic_signal: "Analytic signal",
  first_horizontal_derivative: "Edge strength (THG)",
  first_vertical_derivative: "Vertical derivative",
  rte: "Reduction to equator",
  tilt_derivative: "Tilt derivative",
  radially_averaged_power_spectrum: "Power spectrum",
  candidate_lineament_extraction: "Candidate lineaments",
};

const FRIENDLY_BLURBS: Record<string, string> = {
  tmi: "Original readings gridded for map display.",
  gaussian: "Fine detail removed to show broader magnetic patterns.",
  analytic_signal: "Highlights where magnetic sources sit beneath the survey.",
  first_horizontal_derivative: "Shows sharp changes in the magnetic field.",
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function formatNumber(value: unknown, digits = 0): string | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  });
}

export function previewFilenameForProduct(product: MagneticProductEntry): string | null {
  if (!product.preview_exists) return null;
  if (product.operation === "tmi") return "tmi_preview.png";
  if (product.operation === "radially_averaged_power_spectrum") {
    return "raps_preview.png";
  }
  if (product.operation === "candidate_lineament_extraction") {
    return "candidate_lineaments_preview.png";
  }
  return `${product.operation}_preview.png`;
}

export function geotiffFilenameForProduct(product: MagneticProductEntry): string | null {
  if (!product.geotiff_exists) return null;
  if (product.operation === "tmi") return "tmi_grid.tif";
  if (product.operation === "candidate_lineament_extraction") {
    return "lineament_density.tif";
  }
  if (product.operation === "radially_averaged_power_spectrum") return null;
  return `${product.operation}.tif`;
}

export function productDisplayTitle(product: MagneticProductEntry): string {
  return (
    FRIENDLY_TITLES[product.operation] ||
    product.title ||
    product.operation.split("_").join(" ")
  );
}

export function productDisplayBlurb(product: MagneticProductEntry): string {
  return (
    FRIENDLY_BLURBS[product.operation] ||
    product.summary ||
    "Geological processing product from this survey."
  );
}

/** Prefer the four design-primary cards, then remaining generated products. */
export function presentGeologicalProductCards(
  magnetic: MagneticProducts | null,
): MagneticProductEntry[] {
  const products = magnetic?.products ?? [];
  const byOp = new Map(products.map((p) => [p.operation, p]));
  const primary = CARD_ORDER.map((op) => byOp.get(op)).filter(
    (p): p is MagneticProductEntry => Boolean(p),
  );
  const rest = products.filter(
    (p) =>
      !CARD_ORDER.includes(p.operation as (typeof CARD_ORDER)[number]) &&
      p.operation !== "candidate_lineament_extraction" &&
      (p.preview_exists || p.geotiff_exists || p.raps_exists),
  );
  return [...primary, ...rest];
}

export function presentPipelineSteps(input: {
  dataset: GeologicalDataset | null;
  validation: ValidationReport | null;
  magnetic: MagneticProducts | null;
  compatibility: Record<string, unknown> | null;
}): PipelineStep[] {
  const { dataset, validation, magnetic, compatibility } = input;
  const rows =
    dataset?.feature_count ??
    (typeof validation?.tmi_statistics?.count === "number"
      ? validation.tmi_statistics.count
      : null);
  const outcome = clientValidationOutcome(validation?.overall);
  const checks = validation?.checks ?? [];
  const passCount = checks.filter((c) => c.status === "PASS").length;
  const warnCount = checks.filter((c) => c.status === "WARN").length;
  const failCount = checks.filter((c) => c.status === "FAIL").length;

  const rasterProducts = (magnetic?.products ?? []).filter(
    (p) =>
      p.operation !== "candidate_lineament_extraction" &&
      (p.preview_exists || p.geotiff_exists),
  );
  const lineamentProduct = (magnetic?.products ?? []).find(
    (p) => p.operation === "candidate_lineament_extraction",
  );
  const nLineaments =
    (typeof magnetic?.candidate_lineaments?.n_lineaments === "number"
      ? magnetic.candidate_lineaments.n_lineaments
      : null) ??
    (typeof lineamentProduct?.qc?.n_lineaments === "number"
      ? lineamentProduct.qc.n_lineaments
      : null);

  const gridSpacing =
    dataset?.grid_spacing_x ??
    magnetic?.grid_spacing_x ??
    null;
  const tmiReady = Boolean(
    (magnetic?.products ?? []).find((p) => p.operation === "tmi" && p.preview_exists),
  );
  const compatDecision =
    (compatibility?.decision as string | undefined) ||
    (asRecord(dataset?.feature_compatibility)?.decision as string | undefined);

  const validated =
    dataset?.validation_status === "validated" ||
    outcome === "Ready" ||
    outcome === "Ready with warnings";

  return [
    {
      id: "uploaded",
      label: "Uploaded",
      detail: rows != null ? `${formatNumber(rows)} rows` : "File received",
      status: dataset?.has_original ? "complete" : "pending",
    },
    {
      id: "metadata",
      label: "Metadata",
      detail: dataset?.crs ? dataset.crs : "CRS not declared",
      status: dataset?.crs ? "complete" : "pending",
    },
    {
      id: "validated",
      label: "Validated",
      detail: validation
        ? failCount
          ? `${failCount} blocking`
          : `${passCount} pass${warnCount ? `, ${warnCount} warning` : ""}`
        : "Not run",
      status: !validation
        ? "pending"
        : failCount
          ? "failed"
          : warnCount
            ? "warning"
            : validated
              ? "complete"
              : "pending",
    },
    {
      id: "gridded",
      label: "Gridded",
      detail: tmiReady
        ? gridSpacing != null
          ? `${formatNumber(gridSpacing)} m cells`
          : "Grid available"
        : "Not gridded",
      status: tmiReady ? "complete" : "pending",
    },
    {
      id: "magnetic",
      label: "Magnetic products",
      detail: rasterProducts.length
        ? `${rasterProducts.length} generated`
        : "None yet",
      status: rasterProducts.length ? "complete" : "pending",
    },
    {
      id: "lineaments",
      label: "Lineaments",
      detail:
        nLineaments != null
          ? `${formatNumber(nLineaments)} candidates`
          : lineamentProduct?.geojson_exists
            ? "Candidates available"
            : "None yet",
      status:
        nLineaments != null || lineamentProduct?.geojson_exists
          ? "complete"
          : "pending",
    },
    {
      id: "compatibility",
      label: "Compatibility",
      detail: compatDecision
        ? String(compatDecision).split("_").join(" ")
        : "Not reviewed",
      status: compatDecision ? "complete" : "pending",
    },
    {
      id: "activated",
      label: "Activated",
      detail:
        dataset?.activation_status === "reporting_only"
          ? "Reporting only"
          : dataset?.activation_status === "approved"
            ? "Approved (catalogue)"
            : dataset?.activation_status === "inactive"
              ? "Inactive"
              : "Not activated",
      status:
        dataset?.activation_status === "reporting_only" ||
        dataset?.activation_status === "approved"
          ? "complete"
          : "pending",
    },
  ];
}

export function presentProcessingHistory(
  magnetic: MagneticProducts | null,
  dataset: GeologicalDataset | null,
): HistoryEntry[] {
  const raw = magnetic?.processing_history;
  const entries: HistoryEntry[] = [];

  if (dataset?.uploaded_at) {
    entries.push({
      id: "upload",
      title: "File uploaded",
      detail: dataset.original_filename || "Original survey file stored",
      at: dataset.uploaded_at,
      tone: "ok",
    });
  }

  if (Array.isArray(raw)) {
    raw.forEach((item, index) => {
      const row = asRecord(item);
      if (!row) return;
      const op = String(row.operation || row.event || row.step || "Processing step");
      const status = String(row.status || row.result || "").toLowerCase();
      const at = typeof row.at === "string" ? row.at : typeof row.timestamp === "string" ? row.timestamp : null;
      const detailParts: string[] = [];
      if (row.message) detailParts.push(String(row.message));
      if (row.resolution != null) detailParts.push(`resolution ${String(row.resolution)}`);
      if (row.crs) detailParts.push(String(row.crs));
      if (row.n_lineaments != null) {
        detailParts.push(`${String(row.n_lineaments)} candidate lineaments`);
      }
      entries.push({
        id: `hist-${index}`,
        title: String(op).replaceAll("_", " "),
        detail: detailParts.join(" · ") || "Recorded processing event",
        at,
        tone: status.includes("fail") || status.includes("error") ? "warn" : "ok",
      });
    });
  }

  return entries;
}

export function presentGlanceStats(input: {
  dataset: GeologicalDataset | null;
  validation: ValidationReport | null;
  magnetic: MagneticProducts | null;
}): Array<{ label: string; value: string }> {
  const stats =
    input.magnetic?.tmi_statistics ||
    input.validation?.tmi_statistics ||
    null;
  const count =
    input.dataset?.feature_count ??
    (typeof stats?.count === "number" ? stats.count : null);
  const vmin = typeof stats?.min === "number" ? stats.min : null;
  const vmax = typeof stats?.max === "number" ? stats.max : null;
  const vmean = typeof stats?.mean === "number" ? stats.mean : null;
  const cell =
    input.dataset?.grid_spacing_x ?? input.magnetic?.grid_spacing_x ?? null;
  const units = input.dataset?.units || "nT";

  const rows: Array<{ label: string; value: string }> = [];
  if (count != null) rows.push({ label: "Points", value: formatNumber(count) || String(count) });
  if (vmin != null && vmax != null) {
    rows.push({
      label: "Value range",
      value: `${vmin.toFixed(0)} to ${vmax.toFixed(0)} ${units}`,
    });
  }
  if (vmean != null) {
    rows.push({ label: "Average", value: `${vmean.toFixed(1)} ${units}` });
  }
  if (cell != null) {
    rows.push({ label: "Cell size", value: `${formatNumber(cell)} m` });
  }
  if (input.dataset?.crs) {
    rows.push({ label: "Source CRS", value: input.dataset.crs });
  }
  return rows;
}

export function parseLineamentGeoJson(payload: unknown): {
  crsName: string | null;
  features: LineamentFeature[];
} {
  const root = asRecord(payload);
  if (!root || root.type !== "FeatureCollection") {
    return { crsName: null, features: [] };
  }
  const crs = asRecord(root.crs);
  const crsProps = asRecord(crs?.properties);
  const crsName =
    typeof crsProps?.name === "string"
      ? crsProps.name
      : typeof root.crs === "string"
        ? root.crs
        : null;
  const list = Array.isArray(root.features) ? root.features : [];
  const features: LineamentFeature[] = [];
  list.forEach((item, index) => {
    const feature = asRecord(item);
    if (!feature) return;
    const geometry = asRecord(feature.geometry);
    const props = asRecord(feature.properties) || {};
    if (geometry?.type !== "LineString") return;
    const coordsRaw = Array.isArray(geometry.coordinates)
      ? geometry.coordinates
      : [];
    const coordinates: [number, number][] = [];
    for (const pair of coordsRaw) {
      if (
        Array.isArray(pair) &&
        typeof pair[0] === "number" &&
        typeof pair[1] === "number"
      ) {
        coordinates.push([pair[0], pair[1]]);
      }
    }
    if (coordinates.length < 2) return;
    const componentId =
      typeof props.component_id === "number" ? props.component_id : null;
    features.push({
      id: `lineament-${componentId ?? index}`,
      index: index + 1,
      lengthM: typeof props.length_m === "number" ? props.length_m : null,
      azimuthDeg: typeof props.azimuth_deg === "number" ? props.azimuth_deg : null,
      nVertices: typeof props.n_vertices === "number" ? props.n_vertices : null,
      componentId,
      coordinates,
      interpretation:
        typeof props.interpretation === "string" ? props.interpretation : null,
    });
  });
  return { crsName, features };
}

/** Fold undirected azimuth (0–180) into N / NE / E / SE / S bins for the chart. */
export function directionBins(features: LineamentFeature[]): DirectionBin[] {
  const bins: DirectionBin[] = [
    { key: "N", label: "N", count: 0 },
    { key: "NE", label: "NE", count: 0 },
    { key: "E", label: "E", count: 0 },
    { key: "SE", label: "SE", count: 0 },
    { key: "S", label: "S", count: 0 },
  ];
  for (const feature of features) {
    if (feature.azimuthDeg == null) continue;
    const a = ((feature.azimuthDeg % 180) + 180) % 180;
    if (a < 18 || a >= 162) bins[0].count += 1;
    else if (a < 54) bins[1].count += 1;
    else if (a < 90) bins[2].count += 1;
    else if (a < 126) bins[3].count += 1;
    else bins[4].count += 1;
  }
  return bins;
}

export function formatAzimuthLabel(azimuthDeg: number | null): string {
  if (azimuthDeg == null || !Number.isFinite(azimuthDeg)) return "—";
  const a = ((azimuthDeg % 180) + 180) % 180;
  if (a < 11.25 || a >= 168.75) return `N ${a.toFixed(0)}°`;
  if (a < 33.75) return `NNE ${a.toFixed(0)}°`;
  if (a < 56.25) return `NE ${a.toFixed(0)}°`;
  if (a < 78.75) return `ENE ${a.toFixed(0)}°`;
  if (a < 101.25) return `E ${a.toFixed(0)}°`;
  if (a < 123.75) return `ESE ${a.toFixed(0)}°`;
  if (a < 146.25) return `SE ${a.toFixed(0)}°`;
  return `SSE ${a.toFixed(0)}°`;
}

export function formatLengthKm(lengthM: number | null): string {
  if (lengthM == null || !Number.isFinite(lengthM)) return "—";
  if (lengthM >= 1000) return `${(lengthM / 1000).toFixed(1)} km`;
  return `${lengthM.toFixed(0)} m`;
}

export function statusBadges(input: {
  dataset: GeologicalDataset | null;
  validation: ValidationReport | null;
}): Array<{ label: string; tone: "ok" | "warn" | "neutral" | "danger" }> {
  const outcome = clientValidationOutcome(input.validation?.overall);
  const badges: Array<{ label: string; tone: "ok" | "warn" | "neutral" | "danger" }> =
    [];
  if (outcome === "Ready") badges.push({ label: "Ready", tone: "ok" });
  else if (outcome === "Ready with warnings") {
    badges.push({ label: "Ready with warnings", tone: "warn" });
  } else if (outcome === "Blocked") {
    badges.push({ label: "Blocked", tone: "danger" });
  }
  if (input.dataset?.activation_status === "reporting_only") {
    badges.push({ label: "Reporting-only active", tone: "ok" });
  } else if (input.dataset?.activation_status === "inactive") {
    badges.push({ label: "Inactive", tone: "neutral" });
  }
  badges.push({
    label:
      input.dataset?.scientific_validation_status === "NOT_VALIDATED" ||
      !input.dataset?.scientific_validation_status
        ? "Not scientifically validated"
        : String(input.dataset.scientific_validation_status),
    tone: "neutral",
  });
  return badges;
}
