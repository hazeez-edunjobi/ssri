/**
 * Build the JSON body for POST /api/v1/assess.
 * Omits empty checkpoint/model_id so the API can resolve the promoted registry
 * model server-side. Never invents a checkpoint path.
 */

export type AssessRequestPayload = {
  request_id?: string;
  checkpoint?: string;
  model_id?: string;
  features?: string;
  point?: { latitude: number; longitude: number };
  polygon_geojson?: {
    type: "Polygon";
    coordinates: number[][][];
  };
  hazards?: string[];
  mc_samples?: number;
  model_version?: string;
  produce_geotiff?: boolean;
  resolution_m?: number;
};

export function buildAssessRequestBody(
  payload: AssessRequestPayload,
): AssessRequestPayload {
  const body: AssessRequestPayload = { ...payload };
  if (!body.checkpoint?.trim()) {
    delete body.checkpoint;
  } else {
    body.checkpoint = body.checkpoint.trim();
  }
  if (!body.model_id?.trim()) {
    delete body.model_id;
  } else {
    body.model_id = body.model_id.trim();
  }
  if (!body.features?.trim()) {
    delete body.features;
  }
  return body;
}
