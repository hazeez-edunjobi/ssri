import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  canSubmitAssessment,
  presentAssessmentLoading,
} from "./assessmentLoading.ts";

describe("presentAssessmentLoading", () => {
  it("uses indeterminate processing when no backend stage is confirmed", () => {
    const view = presentAssessmentLoading(null);
    assert.equal(view.mode, "indeterminate");
    if (view.mode === "indeterminate") {
      assert.match(view.title, /Acquiring geospatial intelligence/i);
      assert.match(view.statusLabel, /Processing/i);
      assert.match(view.description, /Geospatial acquisition/i);
    }
  });

  it("does not invent percentages for generic running status", () => {
    const view = presentAssessmentLoading({ status: "running" });
    assert.equal(view.mode, "indeterminate");
    const serialized = JSON.stringify(view);
    assert.equal(serialized.includes("percent"), false);
    assert.equal(serialized.includes("%"), false);
  });

  it("shows staged progress only for confirmed backend stages", () => {
    const view = presentAssessmentLoading({
      status: "running",
      stage: "inference",
      completed_stages: ["preparing", "acquiring", "feature_stack"],
      message: "Model forward pass in progress.",
    });
    assert.equal(view.mode, "staged");
    if (view.mode === "staged") {
      assert.equal(view.currentStageId, "inference");
      assert.deepEqual(view.completedStageIds, [
        "preparing",
        "acquiring",
        "feature_stack",
      ]);
      assert.match(view.description, /Model forward pass/);
    }
  });

  it("ignores unknown stage ids instead of inventing completion", () => {
    const view = presentAssessmentLoading({
      stage: "not-a-real-stage",
      completed_stages: ["mystery", "inference"],
    });
    // Unknown current stage → indeterminate; completed still filters unknowns.
    assert.equal(view.mode, "indeterminate");
  });
});

describe("canSubmitAssessment", () => {
  it("blocks duplicate submissions while loading or in flight", () => {
    assert.equal(canSubmitAssessment({ loading: true, inFlight: false }), false);
    assert.equal(canSubmitAssessment({ loading: false, inFlight: true }), false);
    assert.equal(canSubmitAssessment({ loading: false, inFlight: false }), true);
  });
});
