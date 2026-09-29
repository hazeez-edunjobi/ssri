import { apiUrl } from "./env";
import { getSupabase } from "./supabase";

export type PlatformError = { error?: { code?: string; message?: string } };

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
    `Could not connect to the dataset upload service at ${apiUrl}. Check that the SSRI API is running and that this site is allowed to call it.`,
  );
}

async function parse(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message =
      (body as PlatformError).error?.message || response.statusText || "Request failed";
    throw new Error(message);
  }
  return body;
}

export async function platformGet<T>(path: string): Promise<T> {
  const headers = await authHeader();
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/api/v1/platform${path}`, { headers });
  } catch {
    throw connectionError();
  }
  return parse(response) as Promise<T>;
}

export async function platformPost<T>(path: string, body?: unknown, idempotencyKey?: string): Promise<T> {
  const headers: Record<string, string> = {
    ...(await authHeader()),
    "Content-Type": "application/json",
  };
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/api/v1/platform${path}`, {
      method: "POST",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw connectionError();
  }
  return parse(response) as Promise<T>;
}

export async function uploadDatasetVersion(datasetId: string, file: File, fields?: Record<string, string>) {
  return uploadDatasetVersionWithProgress(datasetId, file, undefined, fields);
}

export function uploadDatasetVersionWithProgress(
  datasetId: string,
  file: File,
  onProgress?: (ratio: number) => void,
  fields?: Record<string, string>,
): Promise<{ version: Record<string, unknown> }> {
  return new Promise((resolve, reject) => {
    authHeader()
      .then((headers) => {
        const form = new FormData();
        form.append("file", file);
        Object.entries(fields || {}).forEach(([key, value]) => {
          if (value) form.append(key, value);
        });
        const request = new XMLHttpRequest();
        request.open("POST", `${apiUrl}/api/v1/platform/datasets/${datasetId}/versions`);
        Object.entries(headers).forEach(([key, value]) => request.setRequestHeader(key, value));
        request.upload.onprogress = (event) => {
          if (event.lengthComputable && onProgress) {
            onProgress(event.loaded / event.total);
          }
        };
        request.onerror = () => reject(connectionError());
        request.ontimeout = () => reject(connectionError());
        request.onload = () => {
          let body: PlatformError & { version?: Record<string, unknown> } = {};
          try {
            body = JSON.parse(request.responseText || "{}");
          } catch {
            body = {};
          }
          if (request.status < 200 || request.status >= 300) {
            reject(new Error(body.error?.message || "Upload failed"));
            return;
          }
          resolve(body as { version: Record<string, unknown> });
        };
        request.send(form);
      })
      .catch((err: Error) => reject(err));
  });
}
