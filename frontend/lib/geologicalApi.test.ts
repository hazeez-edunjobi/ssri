import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { geologicalHttpErrorMessage } from "./geologicalErrors.ts";

describe("geologicalHttpErrorMessage", () => {
  it("explains 401 clearly without claiming upload succeeded", () => {
    const message = geologicalHttpErrorMessage(401, {
      error: { code: "AUTHENTICATION_REQUIRED", message: "Authentication is required." },
    });
    assert.match(message, /Authentication is required|Sign in is required/i);
    assert.doesNotMatch(message, /uploaded successfully/i);
  });

  it("explains 403 manage_geological denial for ordinary users", () => {
    const message = geologicalHttpErrorMessage(403, {
      error: {
        code: "INSUFFICIENT_PERMISSIONS",
        message: "The authenticated principal does not have permission to perform this operation.",
      },
    });
    assert.match(message, /permission/i);
  });

  it("surfaces upload size limit for 413", () => {
    const message = geologicalHttpErrorMessage(413, {
      error: { code: "UPLOAD_TOO_LARGE", message: "That file is too large (12 MB)." },
    });
    assert.match(message, /too large/i);
  });
});
