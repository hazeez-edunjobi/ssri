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

/**
 * One hazard entry. Under the release shell (flag ON) the backend returns a
 * gate `status` and a `score` that is withheld unless the gate allows it.
 * Classic (flag OFF) responses carry `susceptibility_score` + credible intervals.
 */
export type HazardProfile = {
  hazard_type: string;
  /** Classic (flag OFF) ranking; absent when the shell withholds the score. */
  susceptibility_score?: number;
  /** Shell score; null/absent unless the gate allows a ranking. */
  score?: number | null;
  status?: string;
  reason?: string | null;
  gate_status?: string | null;
  score_framing?: string;
  preview_unevaluated_scores?: boolean;
  scientific_validation_status?: string;
  limitations?: string[] | null;
  credible_interval_80?: [number, number];
  credible_interval_95?: [number, number];
  domain_similarity_score?: number | null;
  confidence_tier?: string;
  primary_drivers?: string[];
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
  /** Ordered channels the checkpoint was trained on (backend echo). */
  channel_schema_version?: string | null;
  channel_names?: string[] | null;
};

export type JobStatusResponse = {
  job_id: string;
  status: string;
  progress?: number | null;
  result?: Record<string, unknown> | null;
  error?: string | null;
};

/**
 * Turn an error response into a plain-language sentence with a next step.
 * Never surfaces a raw stack trace or `[object Object]`.
 */
async function parseError(response: Response, context?: string): Promise<string> {
  const fallback = `${response.status} ${response.statusText}`.trim();
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    return context
      ? `${context}: the server returned an unreadable error (${fallback}). Please retry.`
      : `Request failed (${fallback}). Please retry.`;
  }
  const message = extractErrorMessage(body);
  if (message) {
    return context ? `${context}: ${message}` : message;
  }
  return context
    ? `${context}: unexpected error (${fallback}). Please try again or contact support.`
    : `Unexpected error (${fallback}). Please try again.`;
}

function extractErrorMessage(body: unknown): string | null {
  if (typeof body === "string") return body.trim() || null;
  if (!body || typeof body !== "object") return null;
  const record = body as Record<string, unknown>;
  const detail = record.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc, msg, type}, ...]
    const parts = detail
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        const msg = (item as Record<string, unknown>).msg;
        const loc = (item as Record<string, unknown>).loc;
        if (typeof msg !== "string") return null;
        const where = Array.isArray(loc) ? loc.filter((p) => p !== "body").join(".") : "";
        return where ? `${where}: ${msg}` : msg;
      })
      .filter((p): p is string => Boolean(p));
    if (parts.length) return parts.join("; ");
  }
  const error = record.error;
  if (typeof error === "string" && error.trim()) return error;
  if (error && typeof error === "object") {
    const message = (error as Record<string, unknown>).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  const message = record.message;
  if (typeof message === "string" && message.trim()) return message;
  return null;
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
  if (!response.ok)
    throw new Error(await parseError(response, "Could not reach the service"));
  return response.json();
}

export async function getReady(): Promise<ReadyResponse> {
  const response = await fetch(`${apiUrl}/api/v1/ready`);
  if (!response.ok)
    throw new Error(await parseError(response, "The service is not ready yet"));
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
  if (!response.ok) throw new Error(await parseError(response, "Assessment failed"));
  const body = (await response.json()) as AssessResponse & {
    status?: string;
    message?: string;
  };
  // The shell returns HTTP 200 with a status envelope when no checkpoint exists.
  if (body && body.status === "no_trained_model") {
    throw new Error(
      body.message ||
        "No trained model checkpoint was provided. Upload a labelled dataset, train, then select a checkpoint before running an assessment.",
    );
  }
  return body;
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
  if (!response.ok)
    throw new Error(await parseError(response, "Could not load the gravity layer"));
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
  if (!response.ok) throw new Error(await parseError(response, "Could not load training requirements"));
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
  if (!response.ok) throw new Error(await parseError(response, "Could not create the dataset"));
  return response.json();
}

export async function listTrainingDatasets(
  apiKey?: string,
): Promise<{ datasets: TrainingDataset[] }> {
  const response = await fetch(`${apiUrl}/api/v1/training/datasets`, {
    headers: authHeaders(apiKey),
  });
  if (!response.ok) throw new Error(await parseError(response, "Could not list datasets"));
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
  if (!response.ok) throw new Error(await parseError(response, "Upload failed"));
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
  if (!response.ok) throw new Error(await parseError(response, "Validation failed"));
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
  if (!response.ok) throw new Error(await parseError(response, "Could not start training"));
  return response.json();
}

export async function getTrainingJob(
  jobId: string,
  apiKey?: string,
): Promise<TrainingJobStatus> {
  const response = await fetch(`${apiUrl}/api/v1/training/jobs/${jobId}`, {
    headers: authHeaders(apiKey),
  });
  if (!response.ok) throw new Error(await parseError(response, "Could not read the training job"));
  return response.json();
}

export async function listTrainedModels(
  apiKey?: string,
): Promise<{ models: TrainedModel[] }> {
  const response = await fetch(`${apiUrl}/api/v1/training/models`, {
    headers: authHeaders(apiKey),
  });
  if (!response.ok) throw new Error(await parseError(response, "Could not list trained models"));
  return response.json();
}

export async function getActiveTrainedModel(
  apiKey?: string,
): Promise<{ active: TrainedModel | null; checkpoint_path: string | null }> {
  const response = await fetch(`${apiUrl}/api/v1/training/models/active`, {
    headers: authHeaders(apiKey),
  });
  if (!response.ok) throw new Error(await parseError(response, "Could not read the active model"));
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
  if (!response.ok) throw new Error(await parseError(response, "Could not activate the model"));
  return response.json();
}

/** Release-shell (SSRI_RELEASE_SHELL=true) helpers for the owner upload→train page. */

export type ShellCheck = {
  name: string;
  status: string;
  message: string;
  details?: Record<string, unknown>;
};

export type ShellValidation = {
  overall: string;
  can_train: boolean;
  checks: ShellCheck[];
  hazards?: Record<string, { status?: string; reason?: string }>;
};

export type ShellJobStatus = {
  job_id: string;
  status: string;
  scientific_validation_status?: string;
  result?: Record<string, unknown> | null;
  progress?: Record<string, unknown> | null;
  artifacts?: Record<string, unknown>;
  error_code?: string | null;
  error_message?: string | null;
};

function formAuthHeaders(apiKey?: string): Record<string, string> {
  const headers: Record<string, string> = {};
  const key =
    apiKey ||
    (typeof process !== "undefined"
      ? process.env.NEXT_PUBLIC_SSRI_API_KEY
      : undefined);
  if (key) headers.Authorization = `Bearer ${key}`;
  return headers;
}

export async function getShellStatus(
  apiKey?: string,
): Promise<{
  release_shell_enabled: boolean;
  limitations: string[];
  scientific_validation_status: string;
}> {
  const response = await fetch(`${apiUrl}/api/v1/release-shell/status`, {
    headers: authHeaders(apiKey),
  });
  if (!response.ok)
    throw new Error(await parseError(response, "Could not read the release-shell status"));
  return response.json();
}

export async function uploadShellDatasetZip(
  datasetId: string,
  file: File,
  apiKey?: string,
): Promise<{ dataset_id: string; uploaded: boolean; bytes: number }> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(
    `${apiUrl}/api/v1/release-shell/datasets/${datasetId}/upload`,
    { method: "POST", headers: formAuthHeaders(apiKey), body: form },
  );
  if (!response.ok)
    throw new Error(await parseError(response, "Upload failed"));
  return response.json();
}

export async function validateShellDataset(
  datasetId: string,
  apiKey?: string,
): Promise<{ validation: ShellValidation }> {
  const response = await fetch(
    `${apiUrl}/api/v1/release-shell/datasets/${datasetId}/validate`,
    { method: "POST", headers: authHeaders(apiKey) },
  );
  if (!response.ok)
    throw new Error(await parseError(response, "Validation failed"));
  return response.json();
}

export async function startShellTrainingJob(
  body: {
    dataset_id: string;
    epochs?: number;
    batch_size?: number;
    learning_rate?: number;
    seeds?: number[];
    device?: string;
    model_name?: string | null;
  },
  apiKey?: string,
): Promise<{ job_id: string; run_id: string; message: string; data_hash?: string }> {
  const response = await fetch(`${apiUrl}/api/v1/release-shell/jobs`, {
    method: "POST",
    headers: authHeaders(apiKey),
    body: JSON.stringify(body),
  });
  if (!response.ok)
    throw new Error(await parseError(response, "Could not start training"));
  return response.json();
}

export async function getShellJob(
  jobId: string,
  apiKey?: string,
): Promise<ShellJobStatus> {
  const response = await fetch(`${apiUrl}/api/v1/jobs/${jobId}`, {
    headers: authHeaders(apiKey),
  });
  if (!response.ok)
    throw new Error(await parseError(response, "Could not read the training job"));
  return response.json();
}

export async function getShellEvaluation(
  modelId: string,
  apiKey?: string,
): Promise<Record<string, unknown>> {
  const response = await fetch(
    `${apiUrl}/api/v1/release-shell/models/${modelId}/evaluation`,
    { headers: authHeaders(apiKey) },
  );
  if (!response.ok)
    throw new Error(await parseError(response, "Could not read the evaluation"));
  return response.json();
}

export type ShellChannelSchema = {
  channel_count: number;
  channel_names: string[];
};

/** Hazard registry entry as returned by the backend status endpoint. */
export type ShellHazard = {
  name: string;
  class_id: number;
  enabled_by_default: boolean;
};

export type ShellSettings = {
  block_size_deg: number | null;
  default_block_size_deg: number;
  buffer_km: number;
  minimums: {
    tiles_per_hazard: number;
    blocks: number;
    held_out_blocks: number;
  };
  preview_unevaluated_scores: boolean;
  supported_channel_schemas: string[];
  default_channel_schema: string;
  channel_schemas: Record<string, ShellChannelSchema>;
  /** Backend hazard registry. The UI derives its hazard list from here. */
  hazards?: ShellHazard[];
};

export type ShellStatus = {
  release_shell_enabled: boolean;
  limitations: string[];
  scientific_validation_status: string;
  settings?: ShellSettings;
};

export async function getShellStatusFull(apiKey?: string): Promise<ShellStatus> {
  const response = await fetch(`${apiUrl}/api/v1/release-shell/status`, {
    headers: authHeaders(apiKey),
  });
  if (!response.ok)
    throw new Error(await parseError(response, "Could not read the release-shell status"));
  return response.json();
}

export type TrainingRegionExtent = {
  lat_min: number;
  lat_max: number;
  lon_min: number;
  lon_max: number;
};

export type CheckpointGeography = {
  checkpoint: string;
  has_release_shell_meta: boolean;
  crs: string | null;
  crs_declared: boolean;
  training_region: {
    blocks?: string[];
    extent?: TrainingRegionExtent | null;
    n_tiles?: number;
  } | null;
  region_extent: TrainingRegionExtent | null;
  point_geographic?: { latitude: number; longitude: number };
  point_converted?: {
    x: number;
    y: number;
    crs: string;
    axis_order: string;
  } | null;
  conversion_error?: string;
  inside_training_region?: boolean | null;
  outside_training_region?: boolean;
};

/**
 * Read a checkpoint's declared CRS and training region (release shell only).
 *
 * Map clicks are WGS84 lat/lon; when the checkpoint declares a projected CRS the
 * backend converts the point with pyproj and returns both forms. The UI never
 * guesses a projection in the browser.
 */
export async function fetchCheckpointGeography(
  checkpoint: string,
  point?: { latitude: number; longitude: number },
  apiKey?: string,
): Promise<{ geography: CheckpointGeography }> {
  const response = await fetch(`${apiUrl}/api/v1/release-shell/geography`, {
    method: "POST",
    headers: authHeaders(apiKey),
    body: JSON.stringify(point ? { checkpoint, point } : { checkpoint }),
  });
  if (!response.ok)
    throw new Error(await parseError(response, "Could not read the checkpoint geography"));
  return response.json();
}

export type ShellLayerCheck = { name: string; status: string; message: string };

export type ShellLayerReport = {
  overall: string;
  can_train: boolean;
  layer_name: string;
  status: string;
  trainable: boolean;
  row_count?: number;
  missing_cells?: number;
  value_min?: number | null;
  value_max?: number | null;
  checks: ShellLayerCheck[];
  messages?: string[];
};

export async function validateShellLayer(
  file: File,
  layerName: string,
  crs: string,
  apiKey?: string,
  workingCrs?: string,
): Promise<{ layer: ShellLayerReport }> {
  const form = new FormData();
  form.append("file", file);
  form.append("layer_name", layerName);
  form.append("crs", crs);
  if (workingCrs) form.append("working_crs", workingCrs);
  const response = await fetch(`${apiUrl}/api/v1/release-shell/layers/validate`, {
    method: "POST",
    headers: formAuthHeaders(apiKey),
    body: form,
  });
  if (!response.ok)
    throw new Error(await parseError(response, "Could not check the layer"));
  return response.json();
}

export async function uploadShellLabelInventory(
  file: File,
  crs: string,
  apiKey?: string,
): Promise<{ labels: Record<string, unknown> }> {
  const form = new FormData();
  form.append("file", file);
  form.append("crs", crs);
  const response = await fetch(`${apiUrl}/api/v1/release-shell/labels/inventory`, {
    method: "POST",
    headers: formAuthHeaders(apiKey),
    body: form,
  });
  if (!response.ok)
    throw new Error(await parseError(response, "Could not read the label inventory"));
  return response.json();
}

export async function inspectShellLineaments(
  file: File,
  apiKey?: string,
): Promise<{ lineaments: Record<string, unknown> }> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${apiUrl}/api/v1/release-shell/lineaments/inspect`, {
    method: "POST",
    headers: formAuthHeaders(apiKey),
    body: form,
  });
  if (!response.ok)
    throw new Error(await parseError(response, "Could not inspect the lineaments"));
  return response.json();
}
