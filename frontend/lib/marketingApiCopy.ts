/**
 * Marketing-page API copy. Keep in sync with implemented routes only.
 * Live assessment: POST /api/v1/assess (not /v1/hazard).
 */

export const LIVE_ASSESS_ROUTE = "POST /api/v1/assess";

/** Capabilities that exist in the shipped API today. */
export const AVAILABLE_API_CAPABILITIES = [
  {
    route: "POST /api/v1/assess",
    summary: "Run a ground-risk assessment for a point or polygon (Stage 2.5, 13 channels).",
  },
  {
    route: "GET /api/v1/health",
    summary: "Liveness check for the inference API.",
  },
  {
    route: "GET /api/v1/ready",
    summary: "Readiness: Postgres, Redis/queue, and promoted checkpoint status.",
  },
  {
    route: "GET /api/v1/training/models/active",
    summary: "Inspect the promoted Stage 2.5 checkpoint used for assessments.",
  },
  {
    route: "GET /api/v1/assess/history",
    summary: "List persisted filesystem assessments (operational archive index).",
  },
] as const;

/** Explicitly not shipped — do not present as live. */
export const ROADMAP_API_ITEMS = [
  {
    label: "Public GET /v1/hazard point query",
    note: "Not implemented. Use POST /api/v1/assess with a WGS84 point instead.",
  },
  {
    label: "pip install ssri-python / npm install @ssri/sdk",
    note: "Official SDKs are not published. Call the REST API directly.",
  },
  {
    label: "POST/GET /v1/assessments job API",
    note: "Not the live contract. Live assess is synchronous POST /api/v1/assess.",
  },
] as const;

export const ASSESS_CURL_EXAMPLE = `curl -X POST "$SSRI_API_URL/api/v1/assess" \\
  -H "Authorization: Bearer $SSRI_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"point":{"latitude":6.52,"longitude":3.38},"hazards":["subsidence","landslide","sinkhole"]}'`;

/** Strings that must never appear as live claims on marketing pages. */
export const FORBIDDEN_LIVE_MARKETING_CLAIMS = [
  "/v1/hazard",
  "pip install ssri-python",
  "npm install @ssri/sdk",
  "GET /v1/assessments",
  "POST /v1/assessments",
] as const;
