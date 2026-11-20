/**
 * Central client for `/api/v1/geological/*`.
 * UI components must use these helpers — no direct fetch in pages.
 */

import { apiUrl } from "./env";
import { getSupabase } from "./supabase";

export type GeologicalError = { error?: { code?: string; message?: string } };

export type GeologicalDataset = {
  geo_id: string;
  display_name: string;
  asset_kind: "point_grid_csv" | "vector_lineament";
  original_filename: string;
  uploaded_at: string;
  measurement_type: string | null;
  measurement_description?: string;
  description?: string;
  source_client?: string;
  crs: string | null;
  working_crs?: string | null;
  units: string | null;
  coverage_bbox?: number[] | null;
  grid_spacing_x?: number | null;
  grid_spacing_y?: number | null;
  grid_spacing_units?: string | null;
  validation_status: string;
  activation_status: string;
  scientific_validation_status?: string;
  has_original?: boolean;
  has_working?: boolean;
  feature_count?: number | null;
  geometry_type?: string | null;
  x_column?: string | number | null;
  y_column?: string | number | null;
  z_column?: string | number | null;
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
  checks?: Array<{ name: string; status: string; message: string }>;
  messages?: string[];
  measurement_type?: string;
};

async function authHeader(): Promise<Record<string, string>> {
  const supabase = getSupabase();
  const headers: Record<string, string> = {};
  if (!supabase) return headers;
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function connectionError(): Error {
  return new Error(
    `Could not connect to the geological dataset service at ${apiUrl}. Check that the SSRI API is running.`,
  );
}

async function parse(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message =
      (body as GeologicalError).error?.message ||
      (body as { validation?: ValidationReport }).validation?.checks
        ?.filter((c) => c.status === "FAIL")
        .map((c) => c.message)
        .join(" ") ||
      response.statusText ||
      "Request failed";
    throw new Error(message);
  }
  return body;
}

async function geoGet<T>(path: string): Promise<T> {
  const headers = await authHeader();
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
    ...(await authHeader()),
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
  }>(`/datasets/${geoId}`);
}

export function uploadGeologicalFile(
  geoId: string,
  file: File,
  onProgress?: (ratio: number) => void,
): Promise<{ dataset: GeologicalDataset; inspect: InspectReport }> {
  return new Promise((resolve, reject) => {
    authHeader()
      .then((headers) => {
        const form = new FormData();
        form.append("file", file);
        const request = new XMLHttpRequest();
        request.open("POST", `${apiUrl}/api/v1/geological/datasets/${geoId}/upload`);
        Object.entries(headers).forEach(([key, value]) => request.setRequestHeader(key, value));
        request.upload.onprogress = (event) => {
          if (event.lengthComputable && onProgress) onProgress(event.loaded / event.total);
        };
        request.onerror = () => reject(connectionError());
        request.ontimeout = () => reject(connectionError());
        request.onload = () => {
          let body: GeologicalError & {
            dataset?: GeologicalDataset;
            inspect?: InspectReport;
          } = {};
          try {
            body = JSON.parse(request.responseText || "{}");
          } catch {
            body = {};
          }
          if (request.status < 200 || request.status >= 300) {
            reject(new Error(body.error?.message || "Upload failed"));
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

export async function queryGeologicalCoverage(body: {
  aoi_bbox: number[];
  aoi_crs?: string;
  measurement_type?: string;
  require_validated?: boolean;
  require_activated?: boolean;
}) {
  return geoPost<{ coverage: Record<string, unknown> }>("/coverage", body);
}
