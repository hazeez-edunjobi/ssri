import assert from "node:assert/strict";
import { test } from "node:test";

import { clientValidationOutcome, validationOutcomeTone } from "./validationOutcome.ts";

test("maps PASS/WARN/FAIL to client outcomes", () => {
  assert.equal(clientValidationOutcome("PASS"), "Ready");
  assert.equal(clientValidationOutcome("WARN"), "Ready with warnings");
  assert.equal(clientValidationOutcome("FAIL"), "Blocked");
  assert.equal(clientValidationOutcome(""), "Unknown");
});

test("tone follows outcome severity", () => {
  assert.equal(validationOutcomeTone("Ready"), "ok");
  assert.equal(validationOutcomeTone("Ready with warnings"), "warn");
  assert.equal(validationOutcomeTone("Blocked"), "block");
});
