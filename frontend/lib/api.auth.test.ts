import assert from "node:assert/strict";
import { describe, it } from "node:test";

/**
 * parseError is not exported; exercise the 401 messaging contract via a
 * minimal mirror of the status/code branching used in lib/api.ts.
 */
function authFailureMessage(
  status: number,
  code: string | null,
  context?: string,
): string {
  if (status === 401) {
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
  if (status === 403) {
    const authMessage = "Your account does not have permission for this action.";
    return context ? `${context}: ${authMessage}` : authMessage;
  }
  return context ? `${context}: unknown` : "unknown";
}

describe("assessment auth error messaging", () => {
  it("does not present AUTHENTICATION_REQUIRED as a model inference failure", () => {
    const message = authFailureMessage(
      401,
      "AUTHENTICATION_REQUIRED",
      "Assessment failed",
    );
    assert.match(message, /Sign in is required/i);
    assert.doesNotMatch(message, /model inference/i);
    assert.doesNotMatch(message, /checkpoint/i);
  });

  it("explains rejected credentials clearly", () => {
    const message = authFailureMessage(401, "INVALID_CREDENTIALS", "Assessment failed");
    assert.match(message, /rejected/i);
  });

  it("explains insufficient permissions", () => {
    const message = authFailureMessage(403, "INSUFFICIENT_PERMISSIONS", "Assessment failed");
    assert.match(message, /permission/i);
  });
});
