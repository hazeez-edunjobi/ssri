import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DEFAULT_PRODUCT_BOUNDS,
  displayBboxFromDataset,
  isValidWgs84Bounds,
  unionBounds,
} from "./mapViewport.ts";

test("DEFAULT_PRODUCT_BOUNDS covers Lagos and Abeokuta corridor", () => {
  assert.equal(isValidWgs84Bounds(DEFAULT_PRODUCT_BOUNDS), true);
  const [w, s, e, n] = DEFAULT_PRODUCT_BOUNDS;
  assert.ok(w < 3.38 && e > 3.38); // Lagos lon
  assert.ok(s < 6.52 && n > 6.52);
  assert.ok(w < 3.25 && e > 3.25); // Abeokuta lon
  assert.ok(s < 7.15 && n > 7.15);
});

test("rejects global and inverted bounds", () => {
  assert.equal(isValidWgs84Bounds([-180, -90, 180, 90]), false);
  assert.equal(isValidWgs84Bounds([10, 10, 5, 20]), false);
});

test("unionBounds merges footprints", () => {
  const u = unionBounds([
    [3.0, 7.0, 3.5, 7.5],
    [2.8, 6.3, 3.6, 6.8],
  ]);
  assert.deepEqual(u, [2.8, 6.3, 3.6, 7.5]);
});

test("displayBboxFromDataset ignores projected coverage_bbox", () => {
  assert.equal(
    displayBboxFromDataset({
      crs: "EPSG:32632",
      coverage_bbox: [-163800, 777400, -107800, 833500],
    }),
    null,
  );
  assert.deepEqual(
    displayBboxFromDataset({
      crs: "EPSG:32632",
      display_bbox_wgs84: [3.0, 7.0, 3.5, 7.5],
    }),
    [3.0, 7.0, 3.5, 7.5],
  );
  assert.deepEqual(
    displayBboxFromDataset({
      crs: "EPSG:4326",
      coverage_bbox: [3.1, 6.4, 3.5, 6.7],
    }),
    [3.1, 6.4, 3.5, 6.7],
  );
});
