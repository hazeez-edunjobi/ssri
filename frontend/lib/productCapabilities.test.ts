import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  PRODUCT_GEOLOGICAL_IDS,
  PRODUCT_HAZARD_IDS,
  isGeologicalCapabilityId,
  isHazardId,
  mergeHazardNames,
} from "./productCapabilities.ts";

describe("product capability visibility", () => {
  it("exposes all three Stage 2.5 hazards including sinkhole", () => {
    assert.deepEqual([...PRODUCT_HAZARD_IDS], [
      "subsidence",
      "landslide",
      "sinkhole",
    ]);
    assert.equal(PRODUCT_HAZARD_IDS.length, 3);
    assert.ok(isHazardId("sinkhole"));
  });

  it("lists geological conditioning separately from hazards", () => {
    assert.deepEqual([...PRODUCT_GEOLOGICAL_IDS], [
      "overburden_thickness",
      "lineament_density",
      "lineament_distance",
      "geological_ingestion",
    ]);
    for (const hazard of PRODUCT_HAZARD_IDS) {
      assert.equal(isGeologicalCapabilityId(hazard), false);
    }
    for (const geo of PRODUCT_GEOLOGICAL_IDS) {
      assert.equal(isHazardId(geo), false);
    }
  });

  it("does not treat lineaments as a fourth hazard", () => {
    assert.equal(PRODUCT_HAZARD_IDS.length, 3);
    assert.ok(
      PRODUCT_GEOLOGICAL_IDS.some((id) => id.includes("lineament")),
    );
    assert.equal(isHazardId("lineament_density"), false);
    assert.equal(isHazardId("lineament_distance"), false);
  });

  it("restores sinkhole when a truncated registry omits it", () => {
    assert.deepEqual(mergeHazardNames(["subsidence", "landslide"]), [
      "subsidence",
      "landslide",
      "sinkhole",
    ]);
  });

  it("deduplicates repeated hazard names", () => {
    assert.deepEqual(
      mergeHazardNames([
        "subsidence",
        "landslide",
        "sinkhole",
        "landslide",
        "subsidence",
      ]),
      ["subsidence", "landslide", "sinkhole"],
    );
  });

  it("appends unknown non-geological registry names after the canonical set", () => {
    assert.deepEqual(mergeHazardNames(["custom_block_hazard", "landslide"]), [
      "subsidence",
      "landslide",
      "sinkhole",
      "custom_block_hazard",
    ]);
  });

  it("rejects geological identifiers from the hazard list", () => {
    assert.deepEqual(
      mergeHazardNames([
        "lineament_density",
        "overburden_thickness",
        "subsidence",
      ]),
      ["subsidence", "landslide", "sinkhole"],
    );
  });

  it("does not mutate the input catalogue array", () => {
    const input = ["landslide", "lineament_density"];
    const before = [...input];
    const merged = mergeHazardNames(input);
    assert.deepEqual(input, before);
    assert.notEqual(merged, input);
    assert.ok(merged.includes("sinkhole"));
    assert.equal(merged.includes("lineament_density"), false);
  });
});
