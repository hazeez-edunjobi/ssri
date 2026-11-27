import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  directionBins,
  parseLineamentGeoJson,
  presentPipelineSteps,
  productDisplayTitle,
} from "./geologicalPresentation.ts";

describe("geologicalPresentation", () => {
  it("builds pipeline steps from observed dataset state without inventing counts", () => {
    const steps = presentPipelineSteps({
      dataset: {
        geo_id: "geo_test",
        display_name: "Example",
        asset_kind: "point_grid_csv",
        original_filename: "sheet.csv",
        uploaded_at: "2026-11-27T00:00:00Z",
        measurement_type: "total_magnetic_intensity",
        crs: "EPSG:32632",
        units: "nT",
        validation_status: "validated",
        activation_status: "reporting_only",
        has_original: true,
        feature_count: 100,
        scientific_validation_status: "NOT_VALIDATED",
      },
      validation: {
        overall: "WARN",
        checks: [
          { name: "a", status: "PASS", message: "ok" },
          { name: "b", status: "WARN", message: "warn" },
        ],
      },
      magnetic: {
        geo_id: "geo_test",
        supported_operations: ["tmi"],
        products: [
          {
            operation: "tmi",
            preview_exists: true,
          },
          {
            operation: "candidate_lineament_extraction",
            geojson_exists: true,
            qc: { n_lineaments: 72 },
          },
        ],
        candidate_lineaments: { n_lineaments: 72 },
        grid_spacing_x: 100,
      },
      compatibility: { decision: "accepted_with_limitations" },
    });
    assert.equal(steps.find((s) => s.id === "lineaments")?.detail, "72 candidates");
    assert.equal(steps.find((s) => s.id === "validated")?.status, "warning");
    assert.equal(steps.find((s) => s.id === "activated")?.detail, "Reporting only");
  });

  it("parses lineament geojson attributes used by the details panel", () => {
    const parsed = parseLineamentGeoJson({
      type: "FeatureCollection",
      crs: { type: "name", properties: { name: "EPSG:32631" } },
      features: [
        {
          type: "Feature",
          geometry: {
            type: "LineString",
            coordinates: [
              [1, 2],
              [3, 4],
            ],
          },
          properties: {
            length_m: 4200,
            azimuth_deg: 45,
            component_id: 31,
            interpretation: "Candidate magnetic lineament",
          },
        },
      ],
    });
    assert.equal(parsed.crsName, "EPSG:32631");
    assert.equal(parsed.features.length, 1);
    assert.equal(parsed.features[0].lengthM, 4200);
    assert.equal(parsed.features[0].azimuthDeg, 45);
    assert.equal(productDisplayTitle({ operation: "first_horizontal_derivative" }), "Edge strength (THG)");
    const bins = directionBins(parsed.features);
    assert.ok(bins.some((b) => b.key === "NE" && b.count === 1));
  });
});
