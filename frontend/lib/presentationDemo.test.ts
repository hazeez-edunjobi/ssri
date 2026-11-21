import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  DEMO_PROGRESS_STAGES,
  PRESENTATION_DEMO_DURATION_MS,
  demoProgressPercent,
  demoStageAt,
  groupDemoScenariosByLocation,
  type DemoScenarioSummary,
} from "./presentationDemo.ts";

describe("presentation demo progress", () => {
  it("covers a full 15-second stage sequence without gaps", () => {
    assert.equal(DEMO_PROGRESS_STAGES[0].startMs, 0);
    assert.equal(
      DEMO_PROGRESS_STAGES[DEMO_PROGRESS_STAGES.length - 1].endMs,
      PRESENTATION_DEMO_DURATION_MS,
    );
    for (let i = 1; i < DEMO_PROGRESS_STAGES.length; i += 1) {
      assert.equal(
        DEMO_PROGRESS_STAGES[i].startMs,
        DEMO_PROGRESS_STAGES[i - 1].endMs,
      );
    }
  });

  it("maps elapsed time to the expected stage labels", () => {
    assert.match(demoStageAt(0).label, /Validating/i);
    assert.match(demoStageAt(3500).label, /feature layers/i);
    assert.match(demoStageAt(7000).label, /subsidence/i);
    assert.match(demoStageAt(10000).label, /landslide and sinkhole/i);
    assert.match(demoStageAt(13000).label, /uncertainty/i);
    assert.match(demoStageAt(14500).label, /report/i);
  });

  it("clamps progress percent to 0–100", () => {
    assert.equal(demoProgressPercent(-100), 0);
    assert.equal(demoProgressPercent(7500), 50);
    assert.equal(demoProgressPercent(20_000), 100);
  });
});

describe("groupDemoScenariosByLocation", () => {
  it("groups catalogue entries by city name", () => {
    const samples: DemoScenarioSummary[] = [
      {
        key: "a",
        location_name: "Lagos",
        profile_label: "A",
        latitude: 1,
        longitude: 2,
        assessment_type: "point",
        summary: "s",
        landslide: 0.1,
        subsidence: 0.2,
        sinkhole: 0.3,
        confidence_tier: "High",
        timestamp_iso: "2026-11-01T00:00:00Z",
      },
      {
        key: "b",
        location_name: "Lagos",
        profile_label: "B",
        latitude: 1,
        longitude: 2,
        assessment_type: "point",
        summary: "s",
        landslide: 0.4,
        subsidence: 0.5,
        sinkhole: 0.6,
        confidence_tier: "Moderate",
        timestamp_iso: "2026-11-01T00:00:00Z",
      },
      {
        key: "c",
        location_name: "Abuja",
        profile_label: "C",
        latitude: 9,
        longitude: 7,
        assessment_type: "aoi",
        summary: "s",
        landslide: 0.2,
        subsidence: 0.2,
        sinkhole: 0.2,
        confidence_tier: "High",
        timestamp_iso: "2026-11-01T00:00:00Z",
      },
    ];
    const grouped = groupDemoScenariosByLocation(samples);
    assert.equal(grouped.get("Lagos")?.length, 2);
    assert.equal(grouped.get("Abuja")?.length, 1);
  });
});
