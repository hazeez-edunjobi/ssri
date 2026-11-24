import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  dashboardHrefForHistory,
  formatHazardLine,
  formatHistoryCoords,
  formatHistoryScore,
  historyEmptyMessage,
} from "./assessmentHistory.ts";

describe("assessment history presentation", () => {
  it("formats scores without inventing values", () => {
    assert.equal(formatHistoryScore(0.582), "58.2%");
    assert.equal(formatHistoryScore(null), "—");
    assert.equal(formatHistoryScore(undefined), "—");
  });

  it("formats stored coordinates or an honest missing label", () => {
    assert.equal(
      formatHistoryCoords({ assessment_id: "a", latitude: 7.25, longitude: 3.25 }),
      "7.250000, 3.250000",
    );
    assert.equal(
      formatHistoryCoords({ assessment_id: "a" }),
      "Location not stored",
    );
  });

  it("builds a dashboard deep-link only when coordinates exist", () => {
    assert.equal(
      dashboardHrefForHistory({ assessment_id: "a", latitude: 7.25, longitude: 3.25 }),
      "/dashboard?lat=7.25&lon=3.25",
    );
    assert.equal(dashboardHrefForHistory({ assessment_id: "a" }), null);
  });

  it("includes confidence tier only when present", () => {
    assert.equal(
      formatHazardLine({
        hazard_type: "subsidence",
        point_estimate: 0.5,
        confidence_tier: "Low",
      }),
      "subsidence: 50.0% · Low",
    );
    assert.equal(
      formatHazardLine({ hazard_type: "landslide", point_estimate: 0.25 }),
      "landslide: 25.0%",
    );
  });

  it("explains empty history honestly", () => {
    assert.match(historyEmptyMessage(0), /No persisted assessments/);
  });
});
