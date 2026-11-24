/**
 * Central client for `/api/v1/geological/*`.
 * UI components must use these helpers — no direct fetch in pages.
 *
 * Auth matches Stage 2.5 clients: optional NEXT_PUBLIC_SSRI_API_KEY for
 * operator machine keys, otherwise Supabase session. Backend still enforces
 * MANAGE_GEOLOGICAL for mutations — USER accounts remain read-only.
 */

import { apiUrl } from "./env";
import {
  geologicalHttpErrorMessage,
  type GeologicalErrorBody,
} from "./geologicalErrors";

export type GeologicalError = GeologicalErrorBody;
export { geologicalHttpErrorMessage } from "./geologicalErrors";

export type GeologicalDataset = {
  geo_id: string;
  display_name: string;
  asset_kind: "point_grid_csv" | "vector_lineament";
  original_filename: string;
  uploaded_at: string;
  content_sha256?: string;
  measurement_type: string | null;
  measurement_description?: string;
  description?: string;
  source_client?: string;
  crs: string | null;
  working_crs?: string | null;
  units: string | null;
  coverage_bbox?: number[] | null;
  /** Verified WGS84 [west,south,east,north] for map overlays; null if unknown. */
  display_bbox_wgs84?: number[] | null;
  grid_spacing_x?: number | null;
  grid_spacing_y?: number | null;
  grid_spacing_units?: string | null;
  validation_status: string;
  activation_status: string;
  scientific_validation_status?: string;
  processing_status?: string;
  has_original?: boolean;
  has_working?: boolean;
  has_derived?: boolean;
  feature_count?: number | null;
  geometry_type?: string | null;
  x_column?: string | number | null;
  y_column?: string | number | null;
  z_column?: string | number | null;
  provenance?: Record<string, unknown>;
  feature_compatibility?: Record<string, unknown>;
  processing_report?: Record<string, unknown>;
};

export type InspectReport = Record<string, unknown> & {
  row_count?: number;
  detected_columns?: { x?: number; y?: number; z?: number };
  header_row?: string[] | null;
  negative_z_count?: number;
  missing_lattice_cells?: number | null;
  coverage_bbox?: number[] | null;
  messages?: string[];
};

export type ValidationReport = {
  overall?: string;
  can_activate_reporting?: boolean;
  can_process?: boolean;
  can_train?: boolean;
  checks?: Array<{ name: string; status: string; message: string; detail?: unknown }>;
  messages?: string[];
  measurement_type?: string;
  tmi_statistics?: Record<string, unknown>;
  spatial?: Record<string, unknown>;
  feature_compatibility?: Record<string, unknown>;
  coverage_bbox?: number[] | null;
};

/**
 * Prefer configured operator API key, then Supabase session.
 * Does not invent elevated roles — backend RBAC stays authoritative.
 */
export async function geologicalAuthHeaders(
  apiKey?: string,
): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};
  const envKey =
    apiKey ||
    (typeof process !== "undefined"
      ? process.env.NEXT_PUBLIC_SSRI_API_KEY
      : undefined);
  if (envKey && envKey.trim()) {
    headers.Authorization = `Bearer ${envKey.trim()}`;
    return headers;
  }
  try {
    const { getSupabase } = await import("./supabase");
    const supabase = getSupabase();
    if (supabase) {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (token) headers.Authorization = `Bearer ${token}`;
    }
  } catch {
    // Leave unauthenticated; backend returns AUTHENTICATION_REQUIRED.
  }
  return headers;
}

function connectionError(): Error {
  return new Error(
    `Could not connect to the geological dataset service at ${apiUrl}. Check that the SSRI API is running.`,
  );
}

async function parse(response: Response) {
  const body = (await response.json().catch(() => ({}))) as GeologicalError & {
    validation?: ValidationReport;
  };
  if (!response.ok) {
    throw new Error(
      geologicalHttpErrorMessage(
        response.status,
        body,
        response.statusText || "Request failed",
      ),
    );
  }
  return body;
}

async function geoGet<T>(path: string): Promise<T> {
  const headers = await geologicalAuthHeaders();
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/api/v1/geological${path}`, { headers });
  } catch {
    throw connectionError();
  }
  return parse(response) as Promise<T>;
}

async function geoPost<T>(path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {
    ...(await geologicalAuthHeaders()),
    "Content-Type": "application/json",
  };
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/api/v1/geological${path}`, {
      method: "POST",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw connectionError();
  }
  return parse(response) as Promise<T>;
}

export async function listGeologicalDatasets(params?: {
  measurement_type?: string;
  activation_status?: string;
  asset_kind?: string;
  limit?: number;
  offset?: number;
}) {
  const qs = new URLSearchParams();
  if (params?.measurement_type) qs.set("measurement_type", params.measurement_type);
  if (params?.activation_status) qs.set("activation_status", params.activation_status);
  if (params?.asset_kind) qs.set("asset_kind", params.asset_kind);
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  const suffix = qs.toString() ? `?${qs}` : "";
  return geoGet<{ datasets: GeologicalDataset[]; total: number; limit: number; offset: number }>(
    `/datasets${suffix}`,
  );
}

export async function createGeologicalDataset(body: {
  display_name: string;
  asset_kind?: string;
  description?: string;
  source_client?: string;
  notes?: string;
}) {
  return geoPost<{ dataset: GeologicalDataset }>("/datasets", body);
}

export async function getGeologicalDataset(geoId: string) {
  return geoGet<{
    dataset: GeologicalDataset;
    inspect: InspectReport;
    validation: ValidationReport;
    processing?: Record<string, unknown>;
    feature_compatibility?: Record<string, unknown>;
    storage_backend?: string;
    storage_note?: string;
  }>(`/datasets/${geoId}`);
}

export function uploadGeologicalFile(
  geoId: string,
  file: File,
  onProgress?: (ratio: number) => void,
): Promise<{ dataset: GeologicalDataset; inspect: InspectReport }> {
  return new Promise((resolve, reject) => {
    geologicalAuthHeaders()
      .then((headers) => {
        const form = new FormData();
        // Backend UploadFile field name must remain "file".
        form.append("file", file);
        const request = new XMLHttpRequest();
        request.open("POST", `${apiUrl}/api/v1/geological/datasets/${geoId}/upload`);
        Object.entries(headers).forEach(([key, value]) =>
          request.setRequestHeader(key, value),
        );
        request.upload.onprogress = (event) => {
          if (event.lengthComputable && onProgress) onProgress(event.loaded / event.total);
        };
        request.onerror = () => reject(connectionError());
        request.ontimeout = () => reject(connectionError());
        request.onload = () => {
          let body: GeologicalError & {
            dataset?: GeologicalDataset;
            inspect?: InspectReport;
            validation?: ValidationReport;
          } = {};
          try {
            body = JSON.parse(request.responseText || "{}");
          } catch {
            body = {};
          }
          if (request.status < 200 || request.status >= 300) {
            reject(
              new Error(
                geologicalHttpErrorMessage(
                  request.status,
                  body,
                  "Upload failed",
                ),
              ),
            );
            return;
          }
          resolve(body as { dataset: GeologicalDataset; inspect: InspectReport });
        };
        request.send(form);
      })
      .catch((err: Error) => reject(err));
  });
}

export async function declareGeologicalMetadata(
  geoId: string,
  body: Record<string, unknown>,
) {
  return geoPost<{ dataset: GeologicalDataset }>(`/datasets/${geoId}/declare`, body);
}

export type AbeokutaTmiPreset = {
  preset_id: string;
  display_name: string;
  measurement_type: string;
  measurement_description: string;
  crs: string;
  source_crs?: string;
  processing_crs?: string;
  display_crs?: string;
  working_crs?: string;
  x_column: string;
  y_column: string;
  z_column: string;
  x_meaning: string;
  y_meaning: string;
  z_meaning: string;
  units: string;
  geographic_coverage: string;
  scientific_validation_status: string;
  notes: string;
  publication_magnetic_params?: Record<string, unknown>;
  crs_roles?: Record<string, unknown>;
};

export async function getAbeokutaTmiPreset() {
  return geoGet<{ preset: AbeokutaTmiPreset }>("/presets/abeokuta-tmi");
}

export type TmiPreview = {
  ok: boolean;
  wgs84_map_eligible?: boolean;
  geojson?: {
    type: "FeatureCollection";
    features: Array<{
      type: "Feature";
      geometry: { type: "Point"; coordinates: [number, number] | number[] };
      properties: Record<string, unknown> | null;
    }>;
    properties?: Record<string, unknown> | null;
  } | null;
  survey_local?: {
    points: Array<{ x: number; y: number; z: number }>;
    extent: { xmin: number; xmax: number; ymin: number; ymax: number };
    tmi_statistics?: Record<string, unknown>;
    coordinate_frame?: string;
    note?: string;
  } | null;
  total_points?: number;
  sampled_points?: number;
  tmi_statistics?: Record<string, unknown>;
  error?: string;
};

export async function previewGeologicalTmi(geoId: string, maxPoints = 5000) {
  return geoGet<{ geo_id: string; preview: TmiPreview }>(
    `/datasets/${geoId}/preview?max_points=${maxPoints}`,
  );
}

export async function validateGeologicalDataset(geoId: string) {
  return geoPost<{ dataset: GeologicalDataset; validation: ValidationReport }>(
    `/datasets/${geoId}/validate`,
  );
}

export async function setGeologicalActivation(
  geoId: string,
  body: { activation_status: string; acknowledged_warnings?: string[] },
) {
  return geoPost<{ dataset: GeologicalDataset }>(`/datasets/${geoId}/activation`, body);
}

export async function processGeologicalTmi(
  geoId: string,
  body: { resolution: number; nodata?: number },
) {
  return geoPost<{
    dataset: GeologicalDataset;
    processing: Record<string, unknown>;
    feature_compatibility?: Record<string, unknown>;
  }>(`/datasets/${geoId}/process`, body);
}

export type MagneticProducts = {
  geo_id: string;
  supported_operations: string[];
  operation_catalog?: Array<{
    operation: string;
    title?: string;
    summary?: string;
    units?: string;
  }>;
  products: Array<{
    operation: string;
    title?: string;
    summary?: string;
    units?: string;
    geotiff_exists?: boolean;
    preview_exists?: boolean;
    raps_exists?: boolean;
    geotiff_relpath?: string | null;
    preview_relpath?: string | null;
    raps_relpath?: string | null;
  }>;
  processing_history?: unknown[];
  gridding_reconciliation?: Record<string, unknown>;
  gridding_provenance?: Record<string, unknown>;
  inspect_missing_lattice_cells?: number | null;
  inspect_expected_full_grid_cells?: number | null;
  crs_roles?: {
    source_crs?: string | null;
    processing_crs?: string | null;
    display_crs?: string | null;
    crs_declaration_history?: unknown;
  };
  publication_magnetic_params?: Record<string, unknown>;
  publication_comparison?: Record<string, unknown>;
  raps?: {
    wavelength_m?: Array<number | null>;
    log10_power?: Array<number | null>;
    wavenumber_rad_per_m?: number[];
    wavenumber_cycles_per_m?: number[];
    depth_interpretation?: Record<string, unknown>;
  } | null;
  scientific_validation_status?: string;
  tmi_statistics?: Record<string, unknown>;
  spatial?: Record<string, unknown>;
  grid_spacing_x?: number | null;
  grid_spacing_y?: number | null;
  not_hazard_labels?: boolean;
};

export async function listGeologicalMagnetic(geoId: string) {
  return geoGet<MagneticProducts>(`/datasets/${geoId}/magnetic`);
}

export async function runGeologicalMagnetic(
  geoId: string,
  body: {
    operation: string;
    resolution?: number;
    nodata?: number;
    inclination_deg?: number;
    declination_deg?: number;
    average_igrf_nT?: number;
    gaussian_central_wavelength_m?: number;
    gaussian_std?: number;
    gaussian_mode?: string;
    rte_amplitude_clip?: number;
  },
) {
  return geoPost<{
    dataset: GeologicalDataset;
    magnetic: Record<string, unknown>;
  }>(`/datasets/${geoId}/magnetic`, body);
}

/** Candidate magnetic lineaments — NOT confirmed faults; used_in_inference=false. */
export async function extractGeologicalLineaments(
  geoId: string,
  body: {
    percentile?: number;
    min_length_cells?: number;
    min_component_cells?: number;
    density_window_m?: number;
    use_residual_blend?: boolean;
    ensure_derivatives?: boolean;
  } = {},
) {
  return geoPost<{
    dataset: GeologicalDataset;
    lineaments: Record<string, unknown>;
    scientific_validation_status: string;
    not_confirmed_faults_or_fractures: boolean;
    used_in_inference: boolean;
  }>(`/datasets/${geoId}/magnetic/lineaments`, body);
}

/** Absolute URL for a derived preview/product under /geological/datasets/{id}/derived/. */
export function geologicalDerivedUrl(geoId: string, filename: string): string {
  return `${apiUrl}/api/v1/geological/datasets/${geoId}/derived/${encodeURIComponent(filename)}`;
}

export async function setGeologicalCompatibility(
  geoId: string,
  body: { decision: string; notes?: string },
) {
  return geoPost<{
    dataset: GeologicalDataset;
    feature_compatibility?: Record<string, unknown>;
  }>(`/datasets/${geoId}/compatibility`, body);
}

export async function queryGeologicalCoverage(body: {
  aoi_bbox: number[];
  aoi_crs?: string;
  measurement_type?: string;
  require_validated?: boolean;
  require_activated?: boolean;
}) {
  return geoPost<{ coverage: Record<string, unknown> }>("/coverage", body);
}

/** Authenticated original-bytes download (requires manage_geological). */
export async function downloadGeologicalOriginal(
  geoId: string,
  filenameHint?: string,
): Promise<void> {
  const headers = await geologicalAuthHeaders();
  let response: Response;
  try {
    response = await fetch(
      `${apiUrl}/api/v1/geological/datasets/${geoId}/original`,
      { headers },
    );
  } catch {
    throw connectionError();
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as GeologicalError;
    throw new Error(
      geologicalHttpErrorMessage(response.status, body, "Could not download original file"),
    );
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = /filename\*?=(?:UTF-8''|")?([^\";]+)/i.exec(disposition);
  const filename =
    (match ? decodeURIComponent(match[1].replace(/"/g, "")) : null) ||
    filenameHint ||
    `${geoId}-original.bin`;
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
