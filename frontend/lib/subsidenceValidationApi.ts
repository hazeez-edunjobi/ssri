/**
 * Client for GET/POST /api/v1/subsidence/validation.
 * Never treats inference or HTTP 200 as scientific validation.
 */
import { apiUrl } from "./env";
import {
  outcomeLabel,
  type SubsidenceValidationOutcome,
} from "./subsidenceValidationLabels";

export type { SubsidenceValidationOutcome };
export { outcomeLabel };

export type SubsidenceValidationResponse = {
  outcome: SubsidenceValidationOutcome;
  hazard: string;
  scientific_validation_status: string;
  ground_truth_available: boolean;
  ground_truth_provenance?: Record<string, unknown> | null;
  software?: string;
  software_version?: string;
  report: Record<string, unknown>;
  ui_guidance?: {
    title?: string;
    never_implies?: string[];
    outcome_meanings?: Record<string, string>;
  };
};

async function authHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  const envKey =
    typeof process !== "undefined" ? process.env.NEXT_PUBLIC_SSRI_API_KEY : undefined;
  if (envKey?.trim()) {
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
    // Unauthenticated; development API may still accept requests.
  }
  return headers;
}

export async function fetchSubsidenceValidation(params?: {
  checkpoint_id?: string;
  ground_truth_path?: string;
}): Promise<SubsidenceValidationResponse> {
  const query = new URLSearchParams();
  if (params?.checkpoint_id) query.set("checkpoint_id", params.checkpoint_id);
  if (params?.ground_truth_path) {
    query.set("ground_truth_path", params.ground_truth_path);
  }
  const qs = query.toString();
  const url = `${apiUrl}/api/v1/subsidence/validation${qs ? `?${qs}` : ""}`;
  const response = await fetch(url, {
    headers: await authHeaders(),
    cache: "no-store",
  });
  const body = (await response.json()) as SubsidenceValidationResponse;
  // 400 failed outcomes still carry the envelope for UI rendering.
  if (body?.outcome === "failed") {
    return body;
  }
  if (!response.ok) {
    const reason =
      (body as { report?: { reason?: string } })?.report?.reason ||
      (body as { error?: { message?: string } })?.error?.message ||
      response.statusText;
    throw new Error(String(reason || `HTTP ${response.status}`));
  }
  if (!body?.outcome) {
    throw new Error("Unexpected validation response");
  }
  return body;
}

