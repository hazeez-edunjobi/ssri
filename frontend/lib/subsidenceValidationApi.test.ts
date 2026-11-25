import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { outcomeLabel } from "./subsidenceValidationLabels.ts";

describe("subsidenceValidationApi", () => {
  it("labels outcomes without implying scientific validation", () => {
    assert.match(outcomeLabel("success"), /NOT_VALIDATED/i);
    assert.match(outcomeLabel("unavailable"), /unavailable/i);
    assert.match(outcomeLabel("insufficient"), /Insufficient/i);
    assert.match(outcomeLabel("failed"), /failed/i);
  });
});
