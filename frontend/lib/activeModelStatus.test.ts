import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  MISSING_MODEL_ASSESS_HINT,
  activeModelFromHttpStatus,
  activeModelFromNetworkError,
  activeModelFromResponse,
  assessmentButtonDisabled,
  hasAssessmentModelAccess,
  loadingActiveModel,
  modelStatusAssessHint,
  modelStatusPanelMessage,
} from "./activeModelStatus.ts";

describe("activeModelFromResponse", () => {
  it("marks a promoted model available without requiring a filesystem path", () => {
    const status = activeModelFromResponse({
      active: { model_id: "mdl_1", name: "Lagos run" },
      model_id: "mdl_1",
      checkpoint_path: null,
      checkpoint_available: true,
    });
    assert.equal(status.kind, "available");
    assert.equal(status.checkpointAvailable, true);
    assert.equal(status.modelId, "mdl_1");
    assert.match(status.label ?? "", /Lagos run/);
  });

  it("treats an empty active registry as missing, not unauthorized", () => {
    const status = activeModelFromResponse({
      active: null,
      model_id: null,
      checkpoint_path: null,
      checkpoint_available: false,
    });
    assert.equal(status.kind, "missing");
    assert.equal(status.checkpointAvailable, false);
    assert.match(modelStatusPanelMessage(status), /promote/i);
  });
});

describe("activeModelFromHttpStatus", () => {
  it("maps 401 to unauthorized, not missing", () => {
    const status = activeModelFromHttpStatus(401);
    assert.equal(status.kind, "unauthorized");
    assert.doesNotMatch(modelStatusPanelMessage(status), /No promoted Stage 2\.5 checkpoint/i);
    assert.match(modelStatusPanelMessage(status), /Sign in/i);
  });

  it("maps 403 to forbidden, not missing", () => {
    const status = activeModelFromHttpStatus(403);
    assert.equal(status.kind, "forbidden");
    assert.match(modelStatusPanelMessage(status), /permission/i);
  });

  it("maps other HTTP failures to recoverable error", () => {
    const status = activeModelFromHttpStatus(503);
    assert.equal(status.kind, "error");
    assert.match(modelStatusPanelMessage(status), /Retry/i);
  });
});

describe("activeModelFromNetworkError", () => {
  it("does not claim the registry is empty", () => {
    const status = activeModelFromNetworkError();
    assert.equal(status.kind, "error");
    assert.doesNotMatch(modelStatusPanelMessage(status), /No promoted Stage 2\.5 checkpoint/i);
  });
});

describe("assessmentButtonDisabled / hasAssessmentModelAccess", () => {
  const missing = activeModelFromResponse({
    active: null,
    checkpoint_available: false,
  });
  const available = activeModelFromResponse({
    active: { model_id: "m1", name: "A" },
    model_id: "m1",
    checkpoint_available: true,
  });

  it("disables Run assessment when the promoted model is missing", () => {
    assert.equal(hasAssessmentModelAccess(missing, ""), false);
    assert.equal(
      assessmentButtonDisabled({
        loading: false,
        selectedHazardCount: 3,
        status: missing,
        checkpoint: "",
      }),
      true,
    );
    assert.equal(modelStatusAssessHint(missing), MISSING_MODEL_ASSESS_HINT);
  });

  it("enables Run assessment when a promoted model is available", () => {
    assert.equal(hasAssessmentModelAccess(available, ""), true);
    assert.equal(
      assessmentButtonDisabled({
        loading: false,
        selectedHazardCount: 3,
        status: available,
        checkpoint: "",
      }),
      false,
    );
    assert.equal(modelStatusAssessHint(available), null);
  });

  it("allows an explicit operator checkpoint while registry is missing", () => {
    assert.equal(
      hasAssessmentModelAccess(missing, "/data/outputs/training/models/m1/best.pt"),
      true,
    );
    assert.equal(
      assessmentButtonDisabled({
        loading: false,
        selectedHazardCount: 3,
        status: missing,
        checkpoint: " /data/outputs/training/models/m1/best.pt ",
      }),
      false,
    );
  });

  it("keeps the button disabled while status is loading or unauthorized", () => {
    assert.equal(
      assessmentButtonDisabled({
        loading: false,
        selectedHazardCount: 3,
        status: loadingActiveModel(),
        checkpoint: "",
      }),
      true,
    );
    assert.equal(
      assessmentButtonDisabled({
        loading: false,
        selectedHazardCount: 3,
        status: activeModelFromHttpStatus(401),
        checkpoint: "",
      }),
      true,
    );
  });

  it("still disables when no hazards are selected", () => {
    assert.equal(
      assessmentButtonDisabled({
        loading: false,
        selectedHazardCount: 0,
        status: available,
        checkpoint: "",
      }),
      true,
    );
  });
});

describe("scientific contract wording", () => {
  it("keeps Stage 2.5 / promote language without inventing paths", () => {
    assert.match(MISSING_MODEL_ASSESS_HINT, /Stage 2\.5/);
    assert.doesNotMatch(MISSING_MODEL_ASSESS_HINT, /\/data\//);
    assert.doesNotMatch(MISSING_MODEL_ASSESS_HINT, /16-channel|schema-v2/i);
  });
});
