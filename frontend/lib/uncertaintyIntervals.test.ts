import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { presentHazardIntervals } from "./uncertaintyIntervals.ts";

describe("presentHazardIntervals", () => {
  it("marks explicitly unavailable intervals", () => {
    const view = presentHazardIntervals({
      hazard_type: "subsidence",
      uncertainty_intervals_available: false,
      uncertainty_unavailable_reason: "no dropout",
      credible_interval_80: [0.5, 0.5],
      credible_interval_95: [0.5, 0.5],
    });
    assert.equal(view.kind, "unavailable");
    if (view.kind === "unavailable") {
      assert.match(view.reason, /no dropout/);
    }
  });

  it("rejects zero-width legacy bands", () => {
    const view = presentHazardIntervals({
      hazard_type: "landslide",
      credible_interval_80: [0.4, 0.4],
      credible_interval_95: [0.4, 0.4],
    });
    assert.equal(view.kind, "unavailable");
  });

  it("keeps stochastic intervals", () => {
    const view = presentHazardIntervals({
      hazard_type: "sinkhole",
      uncertainty_intervals_available: true,
      credible_interval_80: [0.2, 0.4],
      credible_interval_95: [0.1, 0.5],
    });
    assert.equal(view.kind, "available");
    if (view.kind === "available") {
      assert.deepEqual(view.ci80, [0.2, 0.4]);
      assert.deepEqual(view.ci95, [0.1, 0.5]);
    }
  });
});
