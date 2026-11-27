import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { presentAssessmentExecution } from "./assessmentExecution.ts";

describe("presentAssessmentExecution", () => {
  it("marks only earlier client phases complete while awaiting the sync response", () => {
    const view = presentAssessmentExecution({ phase: "awaiting_response" });
    assert.equal(view.live, true);
    assert.match(view.title, /Running ground-risk assessment/i);
    const validating = view.clientPhases.find((p) => p.id === "validating");
    const submitting = view.clientPhases.find((p) => p.id === "submitting");
    const awaiting = view.clientPhases.find((p) => p.id === "awaiting_response");
    assert.equal(validating?.status, "completed");
    assert.equal(submitting?.status, "completed");
    assert.equal(awaiting?.status, "in_progress");
    assert.ok(view.expectedServerWork.length >= 4);
    const serialized = JSON.stringify(view);
    assert.equal(serialized.includes("%"), false);
  });

  it("does not claim server stages are complete without backend confirmation", () => {
    const view = presentAssessmentExecution({
      phase: "awaiting_response",
      backendProgress: { status: "processing" },
    });
    assert.equal(view.backendPresentation.mode, "indeterminate");
    assert.match(
      JSON.stringify(view.expectedServerWork),
      /Acquiring geospatial data|Running model inference/,
    );
  });

  it("uses staged backend presentation only when the API confirms a stage", () => {
    const view = presentAssessmentExecution({
      phase: "awaiting_response",
      backendProgress: {
        status: "running",
        stage: "inference",
        completed_stages: ["preparing", "acquiring", "feature_stack"],
      },
    });
    assert.equal(view.backendPresentation.mode, "staged");
    if (view.backendPresentation.mode === "staged") {
      assert.equal(view.backendPresentation.currentStageId, "inference");
    }
  });
});
