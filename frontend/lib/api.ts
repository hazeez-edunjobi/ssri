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

/* —— Manual training —— */

export type TrainingRequirements = {
  architecture: string;
  hazards: string[];
  channels: number;
  channel_names: string[];
  required_root_files: string[];
  required_sample_files: string[];
  recommended_sample_files: string[];
  layout: Record<string, string>;
  upload_format: string;
  notes: string[];
};

export type TrainingDataset = {
  dataset_id: string;
  name: string;
  description: string;
  hazard_notes: string;
  geographic_area: string;
  data_source: string;
  notes: string;
  created_at: string;
  root_path: string;
  validation_status: string;
  validation_errors: string[];
  preview: Record<string, unknown>;
};

export type DatasetPreview = {
  dataset_name: string | null;
  version: string | null;
  sample_count: number;
  train_count: number;
  validation_count: number;
  test_count: number;
  channel_count: number;
  channels: string[];
  spatial_size: { height: number; width: number } | null;
  crs: string | null;
  label_classes: string[];
  class_distribution: Record<string, number>;
  missing_label_pixels: number;
  non_finite_feature_samples: number;
  resolution_m: number | null;
  validation_status: string;
  errors: string[];
  warnings: string[];
};

export type TrainingJobStatus = {
  job_id: string;
  request_id: string;
  status: string;
  scientific_validation_status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  error_message: string | null;
  result: Record<string, unknown> | null;
  progress: Record<string, unknown> | null;
  payload: Record<string, unknown>;
};

export type TrainedModel = {
  model_id: string;
  name: string;
  created_at: string;
  dataset_id: string;
  dataset_name: string;
  checkpoint_path: string;
  experiment_dir: string;
  job_id: string | null;
  training_metrics: Record<string, unknown>;
  evaluation_status: string;
  scientific_validation_status: string;
  active: boolean;
  notes: string;
};

export async function getTrainingRequirements(
  apiKey?: string,
): Promise<TrainingRequirements> {
  const response = await fetch(`${apiUrl}/api/v1/training/requirements`, {
    headers: authHeaders(apiKey),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function createTrainingDataset(
  body: {
    name: string;
    description?: string;
    hazard_notes?: string;
    geographic_area?: string;
    data_source?: string;
    notes?: string;
  },
  apiKey?: string,
): Promise<{ dataset: TrainingDataset }> {
  const response = await fetch(`${apiUrl}/api/v1/training/datasets`, {
    method: "POST",
    headers: authHeaders(apiKey),
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function listTrainingDatasets(
  apiKey?: string,
): Promise<{ datasets: TrainingDataset[] }> {
  const response = await fetch(`${apiUrl}/api/v1/training/datasets`, {
    headers: authHeaders(apiKey),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function uploadTrainingDatasetZip(
  datasetId: string,
  file: File,
  apiKey?: string,
): Promise<{
  dataset: TrainingDataset;
  preview: DatasetPreview;
  validation_status: string;
}> {
  const form = new FormData();
  form.append("file", file);
  const headers: Record<string, string> = {};
  const key =
    apiKey ||
    (typeof process !== "undefined"
      ? process.env.NEXT_PUBLIC_SSRI_API_KEY
      : undefined);
  if (key) headers.Authorization = `Bearer ${key}`;
  const response = await fetch(
    `${apiUrl}/api/v1/training/datasets/${datasetId}/upload`,
    { method: "POST", headers, body: form },
  );
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function validateTrainingDataset(
  datasetId: string,
  apiKey?: string,
): Promise<{
  dataset: TrainingDataset;
  preview: DatasetPreview;
  validation_status: string;
}> {
  const response = await fetch(
    `${apiUrl}/api/v1/training/datasets/${datasetId}/validate`,
    { method: "POST", headers: authHeaders(apiKey) },
  );
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function startTrainingJob(
  body: {
    dataset_id: string;
    epochs?: number;
    batch_size?: number;
    learning_rate?: number;
    seed?: number;
    early_stopping_patience?: number | null;
    model_name?: string | null;
    device?: string;
  },
  apiKey?: string,
): Promise<{
  job_id: string;
  run_id: string;
  status: string;
  status_url: string;
  message: string;
}> {
  const response = await fetch(`${apiUrl}/api/v1/training/jobs`, {
    method: "POST",
    headers: authHeaders(apiKey),
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function getTrainingJob(
  jobId: string,
  apiKey?: string,
): Promise<TrainingJobStatus> {
  const response = await fetch(`${apiUrl}/api/v1/training/jobs/${jobId}`, {
    headers: authHeaders(apiKey),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function listTrainedModels(
  apiKey?: string,
): Promise<{ models: TrainedModel[] }> {
  const response = await fetch(`${apiUrl}/api/v1/training/models`, {
    headers: authHeaders(apiKey),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function getActiveTrainedModel(
  apiKey?: string,
): Promise<{ active: TrainedModel | null; checkpoint_path: string | null }> {
  const response = await fetch(`${apiUrl}/api/v1/training/models/active`, {
    headers: authHeaders(apiKey),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function activateTrainedModel(
  modelId: string,
  apiKey?: string,
): Promise<{ active: TrainedModel; checkpoint_path: string; message: string }> {
  const response = await fetch(`${apiUrl}/api/v1/training/models/activate`, {
    method: "POST",
    headers: authHeaders(apiKey),
    body: JSON.stringify({ model_id: modelId }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}
