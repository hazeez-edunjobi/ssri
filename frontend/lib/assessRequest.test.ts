import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { buildAssessRequestBody } from "./assessRequest.ts";

describe("buildAssessRequestBody", () => {
  it("omits empty checkpoint so the API can resolve the promoted model", () => {
    const body = buildAssessRequestBody({
      point: { latitude: 6.52, longitude: 3.38 },
      hazards: ["subsidence", "landslide", "sinkhole"],
      checkpoint: "",
      model_id: "model-a",
    });
    assert.equal(body.checkpoint, undefined);
    assert.equal(body.model_id, "model-a");
    assert.deepEqual(body.hazards, ["subsidence", "landslide", "sinkhole"]);
  });

  it("preserves an explicit operator checkpoint override", () => {
    const body = buildAssessRequestBody({
      checkpoint: "  /data/models/best.pt  ",
      point: { latitude: 1, longitude: 2 },
    });
    assert.equal(body.checkpoint, "/data/models/best.pt");
  });

  it("does not invent a checkpoint when none is provided", () => {
    const body = buildAssessRequestBody({
      point: { latitude: 6.52, longitude: 3.38 },
    });
    assert.equal(Object.prototype.hasOwnProperty.call(body, "checkpoint"), false);
    assert.equal(Object.prototype.hasOwnProperty.call(body, "model_id"), false);
  });
});

describe("missing checkpoint messaging", () => {
  it("keeps production-checkpoint errors actionable", () => {
    const message =
      "No valid production checkpoint is configured. Promote a trained Stage 2.5 (13-channel) model in the training registry, then retry the assessment.";
    assert.match(message, /No valid production checkpoint/i);
    assert.match(message, /Promote/i);
    assert.doesNotMatch(message, /\/data\//);
  });
});
