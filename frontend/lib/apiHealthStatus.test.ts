import assert from "node:assert/strict";
import { test } from "node:test";
import { apiHealthLabel, resolveApiHealthStatus } from "./apiHealthStatus.ts";

test("resolveApiHealthStatus distinguishes unreachable from not ready", () => {
  assert.equal(resolveApiHealthStatus({ healthOk: false, readyOk: false }), "down");
  assert.equal(resolveApiHealthStatus({ healthOk: true, readyOk: false }), "degraded");
  assert.equal(resolveApiHealthStatus({ healthOk: true, readyOk: true }), "ok");
});

test("apiHealthLabel never calls readiness failure unreachable", () => {
  assert.equal(apiHealthLabel("degraded"), "reachable · infrastructure not ready");
  assert.ok(!apiHealthLabel("degraded").includes("unreachable"));
  assert.equal(apiHealthLabel("down"), "unreachable");
});
