/**
 * Shared geological HTTP error messaging (keeps NODE tests free of Next env imports).
 */

export type GeologicalErrorBody = {
  error?: { code?: string; message?: string };
  validation?: {
    checks?: Array<{ name: string; status: string; message: string }>;
  };
};

export function geologicalHttpErrorMessage(
  status: number,
  body: GeologicalErrorBody,
  fallback = "Request failed",
): string {
  const code = body.error?.code;
  const serverMessage = body.error?.message;
  if (status === 401) {
    return (
      serverMessage ||
      "Sign in is required for the geological catalogue. Use an operator or admin session, or configure NEXT_PUBLIC_SSRI_API_KEY with a key that has manage_geological permission."
    );
  }
  if (status === 403 || code === "INSUFFICIENT_PERMISSIONS") {
    return (
      serverMessage ||
      "Your account cannot change geological datasets. Operator or admin permission (manage_geological) is required. Ordinary user accounts may list metadata when signed in but cannot upload, declare, validate, or download originals."
    );
  }
  if (status === 413 || code === "UPLOAD_TOO_LARGE") {
    return (
      serverMessage ||
      "That file exceeds the configured upload size limit (SSRI_UPLOAD_MAX_BYTES)."
    );
  }
  const validationFails = body.validation?.checks
    ?.filter((c) => c.status === "FAIL")
    .map((c) => c.message)
    .join(" ");
  return serverMessage || validationFails || fallback;
}
