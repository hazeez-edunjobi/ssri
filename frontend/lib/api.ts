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

export type PerBlockEval = {
  n: number | null;
  n_pos: number | null;
  roc_auc: number | null;
};

export type EvaluationHazardSummary = {
  gate_status: string | null;
  representative_seed: string | null;
  roc_auc: number | null;
  roc_auc_ci95: [number, number] | null;
  delta_auc_vs_slope: number | null;
  delta_auc_ci95: [number, number] | null;
  slope_only_auc: number | null;
  frac_held_out_blocks_auc_gt_0_5: number | null;
  per_block: Record<string, PerBlockEval> | null;
  seed_aucs: Record<string, number>;
};

/**
 * Trimmed held-out evaluation attached to a release-shell assessment. Copied
 * verbatim from the stored evaluation: relative susceptibility rankings only,
 * status stays NOT_VALIDATED.
 */
export type AssessmentEvaluationSummary = {
  status: string | null;
  split_policy: string | null;
  seeds: number[];
  scientific_validation_status: string;
  score_framing: string;
  hazards: Record<string, EvaluationHazardSummary>;
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
  /** Checkpoint file id (stem) when the release shell is enabled. */
  checkpoint_id?: string | null;
  /** Held-out evaluation trimmed for the report; null when not available. */
  evaluation_summary?: AssessmentEvaluationSummary | null;
  /** Traceable map→grid location record from the assessment API. */
  location_provenance?: {
    submitted_crs?: string;
    submitted?: { latitude: number; longitude: number; crs?: string } | null;
    acquisition_bbox_wgs84?: number[] | null;
    model_grid?: {
      crs?: string | null;
      pixel_row?: number;
      pixel_col?: number;
      outside_grid?: boolean;
      transformed?: { x: number; y: number; crs?: string | null; axis_order?: string };
    } | null;
    outside_acquisition_grid?: boolean | null;
    notes?: string[];
  } | null;
  /** Point-sampled overburden / lineament channels when present in the feature stack. */
  conditioning_features?: {
    schema_channel_count?: number | null;
    sample_policy?: string;
    sample_row?: number;
    sample_col?: number;
    notes?: string[];
    layers?: Record<
      string,
      {
        status: "available" | "nodata" | "unavailable" | string;
        value: number | null;
        unit?: string;
        reason?: string | null;
      }
    >;
  } | null;
  spatial_output_expires_seconds?: number | null;
  spatial_output_hazard?: string | null;
  spatial_output_crs?: string | null;
  spatial_output_georef_quality?: string | null;
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
  if (response.status === 401) {
    const code =
      body && typeof body === "object"
        ? ((body as { error?: { code?: string } }).error?.code ?? null)
        : null;
    if (code === "AUTHENTICATION_REQUIRED") {
      const authMessage =
        "Sign in is required. Refresh after signing in, then try again. " +
        "Assessment uses your signed-in session (or an operator API key), not a public endpoint.";
      return context ? `${context}: ${authMessage}` : authMessage;
    }
    if (code === "INVALID_CREDENTIALS") {
      const authMessage =
        "Your credentials were rejected. Sign in again, or use a valid operator API key.";
      return context ? `${context}: ${authMessage}` : authMessage;
    }
  }
  if (response.status === 403) {
    const authMessage =
      "Your account does not have permission for this action.";
    return context ? `${context}: ${authMessage}` : authMessage;
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

/**
 * Attach credentials for Stage 2.5 / assess / training API routes.
 * Prefer an explicit API key, then NEXT_PUBLIC_SSRI_API_KEY, then the
 * signed-in Supabase session (same contract as platform/geological clients).
 * Never embeds admin/service-role secrets.
 */
async function authHeaders(apiKey?: string): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
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
    headers: await authHeaders(apiKey),
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
    { headers: await authHeaders(apiKey) },
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
    headers: await authHeaders(apiKey),
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
    headers: await authHeaders(apiKey),
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await parseError(response, "Could not create the dataset"));
  return response.json();
}

export async function listTrainingDatasets(
  apiKey?: string,
): Promise<{ datasets: TrainingDataset[] }> {
  const response = await fetch(`${apiUrl}/api/v1/training/datasets`, {
    headers: await authHeaders(apiKey),
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
  const headers = await formAuthHeaders(apiKey);
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
    { method: "POST", headers: await authHeaders(apiKey) },
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
    headers: await authHeaders(apiKey),
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
    headers: await authHeaders(apiKey),
  });
  if (!response.ok) throw new Error(await parseError(response, "Could not read the training job"));
  return response.json();
}

export async function listTrainedModels(
  apiKey?: string,
): Promise<{ models: TrainedModel[] }> {
  const response = await fetch(`${apiUrl}/api/v1/training/models`, {
    headers: await authHeaders(apiKey),
  });
  if (!response.ok) throw new Error(await parseError(response, "Could not list trained models"));
  return response.json();
}

export async function getActiveTrainedModel(
  apiKey?: string,
): Promise<{ active: TrainedModel | null; checkpoint_path: string | null }> {
  const response = await fetch(`${apiUrl}/api/v1/training/models/active`, {
    headers: await authHeaders(apiKey),
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
    headers: await authHeaders(apiKey),
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

async function formAuthHeaders(apiKey?: string): Promise<Record<string, string>> {
  const headers = await authHeaders(apiKey);
  delete headers["Content-Type"];
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
    headers: await authHeaders(apiKey),
  });
  if (!response.ok)
    throw new Error(await parseError(response, "Could not read the release-shell status"));
  return response.json();
}

export async function uploadShellDatasetZip(
  datasetId: string,
  file: File,
  apiKey?: string,
  onProgress?: (ratio: number) => void,
): Promise<{ dataset_id: string; uploaded: boolean; bytes: number }> {
  const form = new FormData();
  form.append("file", file);
  const headers = await formAuthHeaders(apiKey);
  // XHR so large uploads can report progress (fetch has no upload progress).
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${apiUrl}/api/v1/release-shell/datasets/${datasetId}/upload`);
    Object.entries(headers).forEach(([key, value]) => {
      if (value) xhr.setRequestHeader(key, value);
    });
    xhr.upload.onprogress = (event) => {
      if (!onProgress || !event.lengthComputable || event.total <= 0) return;
      onProgress(Math.min(1, event.loaded / event.total));
    };
    xhr.onload = async () => {
      const raw = xhr.responseText || "";
      let body: unknown = {};
      try {
        body = raw ? JSON.parse(raw) : {};
      } catch {
        body = { error: { message: raw || "Upload failed" } };
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as { dataset_id: string; uploaded: boolean; bytes: number });
        return;
      }
      const message =
        typeof body === "object" &&
        body &&
        "error" in body &&
        typeof (body as { error?: { message?: string } }).error?.message === "string"
          ? (body as { error: { message: string } }).error.message
          : `Upload failed (${xhr.status})`;
      reject(new Error(message));
    };
    xhr.onerror = () => reject(new Error("Upload failed (network error)"));
    xhr.send(form);
  });
}

export async function validateShellDataset(
  datasetId: string,
  apiKey?: string,
): Promise<{ validation: ShellValidation }> {
  const response = await fetch(
    `${apiUrl}/api/v1/release-shell/datasets/${datasetId}/validate`,
    { method: "POST", headers: await authHeaders(apiKey) },
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
    headers: await authHeaders(apiKey),
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
    headers: await authHeaders(apiKey),
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
    { headers: await authHeaders(apiKey) },
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
    headers: await authHeaders(apiKey),
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
    headers: await authHeaders(apiKey),
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
  measurementType?: string,
  units?: string,
): Promise<{ layer: ShellLayerReport }> {
  const form = new FormData();
  form.append("file", file);
  form.append("layer_name", layerName);
  form.append("crs", crs);
  if (workingCrs) form.append("working_crs", workingCrs);
  if (measurementType) form.append("measurement_type", measurementType);
  if (units) form.append("units", units);
  const response = await fetch(`${apiUrl}/api/v1/release-shell/layers/validate`, {
    method: "POST",
    headers: await formAuthHeaders(apiKey),
    body: form,
  });
  if (!response.ok)
    throw new Error(await parseError(response, "Could not check the layer"));
  return response.json();
}

export async function applyShellLineaments(
  datasetId: string,
  file: File,
  crs: string,
  windowM = 500,
  apiKey?: string,
): Promise<{ lineaments_applied: Record<string, unknown> }> {
  const form = new FormData();
  form.append("file", file);
  form.append("crs", crs);
  form.append("window_m", String(windowM));
  const response = await fetch(
    `${apiUrl}/api/v1/release-shell/datasets/${datasetId}/lineaments/apply`,
    { method: "POST", headers: await formAuthHeaders(apiKey), body: form },
  );
  if (!response.ok)
    throw new Error(await parseError(response, "Could not apply lineaments to the dataset"));
  return response.json();
}

export async function applyShellOverburden(
  datasetId: string,
  file: File,
  options: {
    layerName?: string;
    crs: string;
    workingCrs?: string;
    measurementType?: string;
    units?: string;
  },
  apiKey?: string,
): Promise<{ overburden_applied: Record<string, unknown> }> {
  const form = new FormData();
  form.append("file", file);
  form.append("layer_name", options.layerName || "overburden_thickness");
  form.append("crs", options.crs);
  if (options.workingCrs) form.append("working_crs", options.workingCrs);
  form.append("measurement_type", options.measurementType || "thickness");
  form.append("units", options.units || "m");
  const response = await fetch(
    `${apiUrl}/api/v1/release-shell/datasets/${datasetId}/overburden/apply`,
    { method: "POST", headers: await formAuthHeaders(apiKey), body: form },
  );
  if (!response.ok)
    throw new Error(await parseError(response, "Could not apply overburden to the dataset"));
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
    headers: await formAuthHeaders(apiKey),
    body: form,
  });
  if (!response.ok)
    throw new Error(await parseError(response, "Could not read the label inventory"));
  return response.json();
}

export async function applyShellLabels(
  datasetId: string,
  file: File,
  crs: string,
  apiKey?: string,
): Promise<{ labels_applied: Record<string, unknown> }> {
  const form = new FormData();
  form.append("file", file);
  form.append("crs", crs);
  const response = await fetch(
    `${apiUrl}/api/v1/release-shell/datasets/${datasetId}/labels/apply`,
    { method: "POST", headers: await formAuthHeaders(apiKey), body: form },
  );
  if (!response.ok)
    throw new Error(await parseError(response, "Could not apply labels to the dataset"));
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
    headers: await formAuthHeaders(apiKey),
    body: form,
  });
  if (!response.ok)
    throw new Error(await parseError(response, "Could not inspect the lineaments"));
  return response.json();
}
