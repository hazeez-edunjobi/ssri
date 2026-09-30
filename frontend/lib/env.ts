/**
 * Browser API origin. All clients import `apiUrl` from here.
 *
 * `NEXT_PUBLIC_API_URL` wins when it is set. A production build without that
 * variable uses the public Render API. Local `next dev` stays on localhost.
 */
const PRODUCTION_API_URL = "https://ssri-api.onrender.com";
const DEVELOPMENT_API_URL = "http://localhost:8000";

function resolveApiUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (configured) return configured.replace(/\/+$/, "");
  if (process.env.NODE_ENV === "production") return PRODUCTION_API_URL;
  return DEVELOPMENT_API_URL;
}

export const apiUrl = resolveApiUrl();
