import assert from "node:assert/strict";
import { test } from "node:test";

import {
  COORD_DECIMALS,
  REGION_PAD_DEG,
  coverageMessage,
  formatLatLon,
  isWithinCoverage,
  parseLatLon,
  pointInRegion,
} from "./coordinates.ts";

// Known points in four quadrants: [lat, lon, label].
const QUADRANTS: Array<[number, number, string]> = [
  [7.16, 3.35, "Abeokuta (NE)"],
  [-33.92, 18.42, "Cape Town (SW)"],
  [40.71, -74.01, "New York (NW)"],
  [-23.7, 133.88, "Alice Springs (SE)"],
];

test("COORD_DECIMALS is 6", () => {
  assert.equal(COORD_DECIMALS, 6);
});

test("parseLatLon accepts valid latitude-first input", () => {
  const parsed = parseLatLon("7.16", "3.35");
  assert.equal(parsed.ok, true);
  if (parsed.ok) {
    assert.equal(parsed.latitude, 7.16);
    assert.equal(parsed.longitude, 3.35);
  }
});

test("parseLatLon rejects empty input with a plain-language message", () => {
  assert.deepEqual(parseLatLon("", "3.35"), {
    ok: false,
    error: "Enter numeric latitude and longitude.",
  });
});

test("parseLatLon rejects non-numeric input", () => {
  const parsed = parseLatLon("abc", "3.35");
  assert.equal(parsed.ok, false);
  if (!parsed.ok) assert.match(parsed.error, /numeric/);
});

test("parseLatLon enforces latitude then longitude ranges", () => {
  const badLat = parseLatLon("99", "3.35");
  assert.equal(badLat.ok, false);
  if (!badLat.ok) assert.equal(badLat.error, "Latitude must be between -90 and 90.");

  const badLon = parseLatLon("7.16", "200");
  assert.equal(badLon.ok, false);
  if (!badLon.ok)
    assert.equal(badLon.error, "Longitude must be between -180 and 180.");
});

test("formatLatLon round-trips every quadrant to 6 decimals", () => {
  for (const [lat, lon, label] of QUADRANTS) {
    const text = formatLatLon(lat, lon);
    const [latText, lonText] = text.split(", ");
    assert.equal(Number(latText), Number(lat.toFixed(6)), label);
    assert.equal(Number(lonText), Number(lon.toFixed(6)), label);
    assert.equal(latText.split(".")[1].length, 6, label);
    assert.equal(lonText.split(".")[1].length, 6, label);
  }
});

test("enter → format → parse round trip is stable", () => {
  for (const [lat, lon, label] of QUADRANTS) {
    const text = formatLatLon(lat, lon);
    const [latText, lonText] = text.split(", ");
    const parsed = parseLatLon(latText, lonText);
    assert.equal(parsed.ok, true, label);
    if (parsed.ok) {
      assert.equal(parsed.latitude, Number(lat.toFixed(6)), label);
      assert.equal(parsed.longitude, Number(lon.toFixed(6)), label);
    }
  }
});

test("isWithinCoverage matches the Lagos clip with a clear message", () => {
  assert.equal(isWithinCoverage(6.52, 3.38), true);
  assert.equal(isWithinCoverage(51.5, -0.12), false);
  assert.match(coverageMessage(), /outside the Lagos geophysics coverage/);
});

test("pointInRegion mirrors the backend 0.5° pad", () => {
  const extent = { lat_min: 7.0, lat_max: 7.3, lon_min: 3.2, lon_max: 3.5 };
  assert.equal(REGION_PAD_DEG, 0.5);
  assert.equal(pointInRegion(7.15, 3.35, extent), true);
  // Within the pad still counts as inside…
  assert.equal(pointInRegion(7.7, 3.35, extent), true);
  // …clearly outside does not.
  assert.equal(pointInRegion(51.5, -0.12, extent), false);
});
