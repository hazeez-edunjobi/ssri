import assert from "node:assert/strict";
import { test } from "node:test";
import {
  formatGravityUnavailableMessage,
  gravityLoadState,
  gravityVisibilityLabel,
} from "./gravityLayer.ts";

test("gravityLoadState distinguishes loading, ready, unavailable", () => {
  assert.equal(gravityLoadState({ loaded: false, error: null }), "loading");
  assert.equal(gravityLoadState({ loaded: true, error: null }), "ready");
  assert.equal(
    gravityLoadState({ loaded: false, error: "missing file" }),
    "unavailable",
  );
});

test("missing GeoTIFF message stays optional and does not claim visibility", () => {
  const msg = formatGravityUnavailableMessage(
    "Could not load the gravity layer: GRAVITY_DATA_PATH GeoTIFF not found for visualization",
  );
  assert.match(msg, /Optional gravity map overlay is unavailable/i);
  assert.match(msg, /Assessment can still run/i);
  assert.ok(!msg.toLowerCase().includes("visible"));
});

test("improved API detail is preserved as optional overlay copy", () => {
  const msg = formatGravityUnavailableMessage(
    "Optional gravity map overlay GeoTIFF not found. Set GRAVITY_DATA_PATH",
  );
  assert.match(msg, /Optional gravity map overlay is unavailable/i);
});

test("visibility label never says shown when overlay is not ready", () => {
  assert.equal(gravityVisibilityLabel("loading", true), "Not on map");
  assert.equal(gravityVisibilityLabel("unavailable", true), "Not on map");
  assert.equal(gravityVisibilityLabel("ready", true), "Shown on map");
  assert.equal(gravityVisibilityLabel("ready", false), "Hidden on map");
});
