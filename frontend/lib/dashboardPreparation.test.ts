import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { loadingActiveModel } from "./activeModelStatus.ts";
import { presentDashboardPreparation } from "./dashboardPreparation.ts";

describe("presentDashboardPreparation", () => {
  it("stays not ready while API and model checks are in flight", () => {
    const view = presentDashboardPreparation({
      sessionEmail: "ops@ssri.test",
      apiStatus: "checking",
      modelStatus: loadingActiveModel(),
      hazardRegistry: "pending",
      hazards: ["subsidence", "landslide", "sinkhole"],
      mapLoaded: false,
      geophysics: "pending",
      geological: "pending",
      geologicalCount: 0,
    });
    assert.equal(view.ready, false);
    assert.match(view.title, /Preparing assessment workspace/i);
    const api = view.stages.find((s) => s.id === "api_connectivity");
    assert.equal(api?.status, "in_progress");
  });

  it("becomes ready from observed terminal states without inventing percentages", () => {
    const view = presentDashboardPreparation({
      sessionEmail: "ops@ssri.test",
      apiStatus: "ok",
      modelStatus: {
        kind: "available",
        modelId: "ssri-model-1c8de63cd3",
        label: "Stage 2.5 (ssri-model-1c8de63cd3)",
        checkpointAvailable: true,
      },
      hazardRegistry: "loaded",
      hazards: ["subsidence", "landslide", "sinkhole"],
      mapLoaded: true,
      geophysics: "available",
      geological: "available",
      geologicalCount: 3,
      registryReadyDetail: "Registry reachable",
    });
    assert.equal(view.ready, true);
    assert.equal(view.blockingError, null);
    assert.equal(view.connected.model, "ssri-model-1c8de63cd3");
    assert.equal(view.connected.geological, "3 footprints");
    const serialized = JSON.stringify(view);
    assert.equal(serialized.includes("%"), false);
  });

  it("surfaces API down as a blocking error with failed connectivity stage", () => {
    const view = presentDashboardPreparation({
      sessionEmail: "ops@ssri.test",
      apiStatus: "down",
      modelStatus: {
        kind: "error",
        modelId: null,
        label: null,
        checkpointAvailable: false,
      },
      hazardRegistry: "fallback",
      hazards: ["subsidence", "landslide", "sinkhole"],
      mapLoaded: true,
      geophysics: "unavailable",
      geological: "unavailable",
      geologicalCount: 0,
    });
    assert.equal(view.ready, false);
    assert.match(view.blockingError ?? "", /Could not reach the SSRI API/i);
    assert.equal(
      view.stages.find((s) => s.id === "api_connectivity")?.status,
      "failed",
    );
  });

  it("does not invent geophysics connection when the layer is unavailable", () => {
    const view = presentDashboardPreparation({
      sessionEmail: "ops@ssri.test",
      apiStatus: "ok",
      modelStatus: {
        kind: "missing",
        modelId: null,
        label: null,
        checkpointAvailable: false,
      },
      hazardRegistry: "fallback",
      hazards: ["subsidence", "landslide", "sinkhole"],
      mapLoaded: true,
      geophysics: "unavailable",
      geological: "unavailable",
      geologicalCount: 0,
    });
    assert.equal(view.connected.geophysics, "Not connected");
    assert.equal(view.connected.geological, "Not connected");
    assert.equal(
      view.stages.find((s) => s.id === "active_model")?.status,
      "failed",
    );
  });
});
