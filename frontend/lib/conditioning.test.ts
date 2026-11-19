import assert from "node:assert/strict";
import { test } from "node:test";
import {
  buildConditioningGroups,
  conditioningSampleCaption,
} from "./conditioning.ts";

test("buildConditioningGroups always exposes overburden and lineaments", () => {
  const groups = buildConditioningGroups({
    schema_channel_count: 13,
    sample_policy: "query_grid_cell",
    sample_row: 4,
    sample_col: 5,
    layers: {
      overburden_thickness: {
        status: "unavailable",
        value: null,
        unit: "m (thickness; not depth-to-interface)",
        reason: "Channel not present",
      },
      lineament_density: {
        status: "nodata",
        value: null,
        unit: "derived density (training units)",
        reason: "Cell is NoData",
      },
      lineament_distance: {
        status: "available",
        value: 42.5,
        unit: "m (distance to nearest lineament segment)",
        reason: null,
      },
    },
  });

  assert.equal(groups.length, 2);
  assert.equal(groups[0].id, "overburden");
  assert.equal(groups[0].title, "Overburden thickness");
  assert.equal(groups[1].id, "lineaments");
  assert.equal(groups[1].title, "Lineaments");

  const overburden = groups[0].metrics[0];
  assert.equal(overburden.status, "unavailable");
  assert.match(overburden.valueText, /Unavailable/i);
  assert.ok(!overburden.valueText.includes("0"));
  assert.equal(overburden.supportedInProduct, true);
  assert.equal(overburden.availableAtLocation, false);
  assert.equal(overburden.usedInThisAssessment, false);
  assert.match(overburden.usageNote, /Not included in this assessment/i);

  const density = groups[1].metrics.find((m) => m.key === "lineament_density");
  assert.ok(density);
  assert.equal(density.status, "nodata");
  assert.match(density.valueText, /NoData/);
  assert.equal(density.usedInThisAssessment, false);
  assert.match(density.usageNote, /NoData/i);

  const distance = groups[1].metrics.find((m) => m.key === "lineament_distance");
  assert.ok(distance);
  assert.equal(distance.status, "available");
  assert.equal(distance.valueText, "42.500");
  assert.match(distance.unit || "", /m/);
  assert.equal(distance.usedInThisAssessment, true);
  assert.match(distance.usageNote, /Present in this assessment/i);
});

test("missing conditioning_features still yields visible unavailable groups", () => {
  const groups = buildConditioningGroups(null);
  assert.equal(groups.length, 2);
  for (const group of groups) {
    assert.ok(group.metrics.length >= 1);
    for (const metric of group.metrics) {
      assert.equal(metric.status, "unavailable");
      assert.match(metric.reason || "", /did not return conditioning_features/);
    }
  }
});

test("available values never coerce null to zero", () => {
  const groups = buildConditioningGroups({
    layers: {
      overburden_thickness: {
        status: "available",
        value: 12,
        unit: "m (thickness; not depth-to-interface)",
      },
      lineament_density: { status: "unavailable", value: null },
      lineament_distance: { status: "nodata", value: null },
    },
  });
  const thickness = groups[0].metrics[0];
  assert.equal(thickness.valueText, "12");
  assert.ok(!groups.flatMap((g) => g.metrics).some((m) => m.valueText === "0"));
});

test("conditioningSampleCaption reports policy and cell", () => {
  const caption = conditioningSampleCaption({
    sample_policy: "tensor_centre",
    sample_row: 1,
    sample_col: 2,
    schema_channel_count: 16,
  });
  assert.ok(caption);
  assert.match(caption!, /tensor_centre/);
  assert.match(caption!, /r1 c2/);
  assert.match(caption!, /16 channels/);
});
