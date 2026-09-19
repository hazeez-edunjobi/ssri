/**
 * SSRI API client — targets the authoritative model FastAPI service.
 */
import { apiUrl } from "./env";

export type HealthResponse = { status: string; service?: string };
export type ReadyResponse = {
  status: string;
  service?: string;
  infrastructure?: Record<string, unknown>;
};

export type AssessRequest = {
  request_id?: string;
  checkpoint?: string;
  features?: string;
  point?: { latitude: number; longitude: number };
  polygon_geojson?: GeoJsonPolygon;
  hazards?: string[];
  mc_samples?: number;
  model_version?: string;
  produce_geotiff?: boolean;
  resolution_m?: number;
};

export type GeoJsonPolygon = {
  type: "Polygon";
  coordinates: number[][][];
};

export type HazardProfile = {
  hazard_type: string;
  susceptibility_score: number;
  credible_interval_80: [number, number];
  credible_interval_95: [number, number];
  domain_similarity_score: number | null;
  confidence_tier: string;
  primary_drivers: string[];
};

export type AssessResponse = {
  assessment_id: string;
  hazard_profiles: HazardProfile[];
  explanation: string;
  model_version: string;
  spatial_output_url: string | null;
  notes: string[];
  request_id: string;
  checkpoint_sha256: string;
  checkpoint_dataset_name: string | null;
  checkpoint_dataset_version: string | null;
  is_fixture_checkpoint: boolean;
  domain_similarity_calibrated: boolean;
};

export type JobStatusResponse = {
  job_id: string;
  status: string;
  progress?: number | null;
  result?: Record<string, unknown> | null;
  error?: string | null;
};

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return JSON.stringify(body);
  } catch {
    return response.statusText;
  }
}

function authHeaders(apiKey?: string): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const key =
    apiKey ||
    (typeof process !== "undefined"
      ? process.env.NEXT_PUBLIC_SSRI_API_KEY
      : undefined);
  if (key) headers.Authorization = `Bearer ${key}`;
  return headers;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${apiUrl}/api/v1/health`);
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function getReady(): Promise<ReadyResponse> {
  const response = await fetch(`${apiUrl}/api/v1/ready`);
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function submitAssess(
  payload: AssessRequest,
  apiKey?: string,
): Promise<AssessResponse> {
  const response = await fetch(`${apiUrl}/api/v1/assess`, {
    method: "POST",
    headers: authHeaders(apiKey),
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export type GeophysicsLayerMetadata = {
  layer_id: string;
  title: string;
  dataset: string;
  provider: string;
  units: string;
  native_resolution: string;
  crs: string;
  nodata: number | null;
  value_min: number | null;
  value_max: number | null;
  feature_count: number;
  scientific_limitation: string;
  source_path_basename: string;
};

export type GravityLayerResponse = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    properties: { value: number };
    geometry: {
      type: "Polygon";
      coordinates: number[][][];
    };
  }>;
  metadata: GeophysicsLayerMetadata;
};

export async function getGravityLayer(
  maxCells = 2500,
  apiKey?: string,
): Promise<GravityLayerResponse> {
  const response = await fetch(
    `${apiUrl}/api/v1/layers/gravity?max_cells=${maxCells}`,
    { headers: authHeaders(apiKey) },
  );
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}
