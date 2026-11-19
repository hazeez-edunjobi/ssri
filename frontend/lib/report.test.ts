/**
 * Report content contract: every value in the HTML report is copied verbatim
 * from the API response. SYNTHETIC data only.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildAssessmentReportHtml,
  findAffirmativeRiskClaims,
} from "./report.ts";
import type { AssessResponse, ShellSettings } from "./api";

const SETTINGS: ShellSettings = {
  block_size_deg: null,
  default_block_size_deg: 5,
  buffer_km: 25,
  minimums: { tiles_per_hazard: 1, blocks: 1, held_out_blocks: 1 },
  preview_unevaluated_scores: false,
  supported_channel_schemas: ["v1", "v2"],
  default_channel_schema: "v2",
  channel_schemas: {},
};

const SYNTHETIC: AssessResponse = {
  assessment_id: "assess-test0001",
  hazard_profiles: [
    {
      hazard_type: "landslide",
      status: "available",
      score: 0.42,
      gate_status: "evaluated",
      score_framing: "relative susceptibility ranking",
    },
    {
      hazard_type: "subsidence",
      status: "not_available",
      score: null,
      gate_status: "trained, no demonstrated skill beyond slope",
      reason: "Hazard gate status is 'trained, no demonstrated skill beyond slope'; score withheld.",
    },
  ],
  explanation: "Relative susceptibility rankings only where gate_status is evaluated.",
  model_version: "ssri-model",
  notes: [
    "data_hash=ABCDEF0123",
    "assess_crs=EPSG:4326",
    "block_size_deg=5.0",
    "channel_schema_version=v1",
    "limitation=trained only on the uploaded data's geography",
  ],
  request_id: "req-1",
  checkpoint_sha256: "A".repeat(64),
  checkpoint_dataset_name: "demo-dataset",
  checkpoint_dataset_version: "2.0.0",
  is_fixture_checkpoint: false,
  domain_similarity_calibrated: true,
  channel_schema_version: "v1",
  channel_names: ["slope", "elevation"],
  checkpoint_id: "shell",
  conditioning_features: {
    layers: {
      overburden_thickness: {
        status: "unavailable",
        value: null,
        unit: "m (thickness; not depth-to-interface)",
        reason: "Channel not present in this assessment feature stack",
      },
      lineament_density: {
        status: "nodata",
        value: null,
        unit: "derived density (training units)",
        reason: "Cell is NoData",
      },
    },
  },
  spatial_output_url: "file:///tmp/example.tif",
  spatial_output_hazard: "landslide",
  spatial_output_crs: "EPSG:32631",
  spatial_output_georef_quality: "acquisition_grid",
  spatial_output_expires_seconds: 3600,
  evaluation_summary: {
    status: "completed",
    split_policy: "whole_5deg_blocks_with_buffer",
    seeds: [42, 43, 44],
    scientific_validation_status: "NOT_VALIDATED",
    score_framing: "relative susceptibility rankings",
    hazards: {
      landslide: {
        gate_status: "evaluated",
        representative_seed: "42",
        roc_auc: 0.71,
        roc_auc_ci95: [0.62, 0.8],
        delta_auc_vs_slope: 0.11,
        delta_auc_ci95: [0.03, 0.19],
        slope_only_auc: 0.6,
        frac_held_out_blocks_auc_gt_0_5: 0.8,
        per_block: { "35_-120": { n: 40, n_pos: 12, roc_auc: 0.74 } },
        seed_aucs: { "42": 0.7, "43": 0.71, "44": 0.72 },
      },
    },
  },
};

function build(): string {
  return buildAssessmentReportHtml({
    result: SYNTHETIC,
    locationLabel: "7.160000, 3.350000",
    point: { latitude: 7.16, longitude: 3.35 },
    projectedPoint: {
      crs: "EPSG:32631",
      x: 500000.123,
      y: 792000.456,
      axis_order: "x=easting, y=northing",
    },
    generatedAt: new Date("2026-01-02T03:04:05Z"),
  });
}

test("report echoes API identity fields exactly", () => {
  const html = build();
  assert.ok(html.includes("assess-test0001"));
  assert.ok(html.includes("shell")); // checkpoint id
  assert.ok(html.includes("A".repeat(64))); // checkpoint sha256
  assert.ok(html.includes("demo-dataset")); // dataset name
  assert.ok(html.includes("2.0.0")); // dataset version
  assert.ok(html.includes("ABCDEF0123")); // dataset hash
});

test("report includes schema, ordered channels, block size and training CRS", () => {
  const html = build();
  assert.ok(html.includes("v1"));
  assert.ok(html.includes("slope, elevation"));
  assert.ok(html.includes("5.0° (checkpoint)"));
  assert.ok(html.includes("EPSG:4326"));
});

test("report includes conditioning layers and GeoTIFF metadata", () => {
  const html = build();
  assert.ok(html.includes("Overburden thickness"));
  assert.ok(html.includes("Lineaments"));
  assert.ok(html.includes("overburden_thickness"));
  assert.ok(html.includes("unavailable"));
  assert.ok(html.includes("NoData (not treated as zero)"));
  assert.ok(html.includes("file:///tmp/example.tif"));
  assert.ok(html.includes("acquisition_grid"));
  assert.ok(html.includes("3600"));
});

test("report includes WGS84 lat/lon at 6 dp and the training-CRS location", () => {
  const html = build();
  assert.ok(html.includes("7.160000"));
  assert.ok(html.includes("3.350000"));
  assert.ok(html.includes("EPSG:32631"));
  assert.ok(html.includes("x=easting, y=northing"));
});

test("report shows the timestamp and NOT_VALIDATED status", () => {
  const html = build();
  assert.ok(html.includes("2026-01-02T03:04:05.000Z"));
  assert.ok(html.includes("NOT_VALIDATED"));
  assert.ok(html.includes("relative susceptibility ranking"));
});

test("score appears only where the gate allows it", () => {
  const html = build();
  // evaluated landslide → ranking shown
  assert.ok(html.includes("42.0% (relative susceptibility ranking)"));
  // not_available subsidence → withheld, score never rendered
  assert.ok(html.includes("withheld"));
  assert.ok(!html.includes("0.000% "));
});

test("evaluation summary numbers match the API exactly", () => {
  const html = build();
  assert.ok(html.includes("42, 43, 44")); // seeds
  assert.ok(html.includes("whole_5deg_blocks_with_buffer")); // split policy
  assert.ok(html.includes("0.710")); // AUC
  assert.ok(html.includes("[0.620, 0.800]")); // AUC 95% CI
  assert.ok(html.includes("+0.110")); // delta vs slope
  assert.ok(html.includes("35_-120")); // per-block table
  assert.ok(html.includes("seed 42: 0.700"));
});

test("report wording never frames results as risk, probability or detection", () => {
  const html = build();
  assert.doesNotMatch(html, /\brisk\b/i);
  assert.doesNotMatch(html, /\bprobability\b/i);
  assert.doesNotMatch(html, /\bprobabilities\b/i);
  assert.doesNotMatch(html, /\bdetection\b/i);
  assert.doesNotMatch(html, /\bvalidation\b/i);
});

test("no evaluation summary degrades to a plain explanation, not a crash", () => {
  const html = buildAssessmentReportHtml({
    result: { ...SYNTHETIC, evaluation_summary: null },
    locationLabel: null,
    point: null,
    generatedAt: new Date("2026-01-02T03:04:05Z"),
  });
  assert.ok(html.includes("Not attached to this point assessment"));
  assert.ok(html.includes("NOT_VALIDATED"));
});

test("report renders the buffer, the limitations array and the local-evidence notice", () => {
  const html = buildAssessmentReportHtml({
    result: {
      ...SYNTHETIC,
      notes: [
        ...SYNTHETIC.notes.filter((n) => !n.startsWith("limitation=")),
        "limitation=local evidence only; trained on the uploaded geography",
      ],
    },
    locationLabel: "7.160000, 3.350000",
    point: { latitude: 7.16, longitude: 3.35 },
    settings: SETTINGS,
    generatedAt: new Date("2026-01-02T03:04:05Z"),
  });
  assert.ok(html.includes("25 km")); // buffer from settings
  assert.ok(html.includes("local evidence only; trained on the uploaded geography")); // limitations array
  assert.ok(html.includes("Local evidence only")); // explicit notice
});

test("wording guard PASSES when only the mandated negation disclaimer is present", () => {
  const disclaimer =
    "NOT_VALIDATED. Scores are relative susceptibility rankings, not probabilities or risk estimates";
  const html = buildAssessmentReportHtml({
    result: { ...SYNTHETIC, explanation: disclaimer },
    locationLabel: null,
    point: null,
    generatedAt: new Date("2026-01-02T03:04:05Z"),
  });
  assert.ok(html.toLowerCase().includes("not probabilities or risk estimates"));
  assert.deepEqual(findAffirmativeRiskClaims(html), []);
});

test("wording guard FAILS on real risk/probability/detection claims", () => {
  assert.ok(findAffirmativeRiskClaims("this is a high risk zone").length > 0);
  assert.ok(findAffirmativeRiskClaims("probability of landslide").length > 0);
  assert.ok(findAffirmativeRiskClaims("landslide detection model").length > 0);
  // The mandated disclaimer alone must never trip the guard.
  assert.deepEqual(
    findAffirmativeRiskClaims(
      "not probabilities or risk estimates",
    ),
    [],
  );
  // And a report that actually claims risk is flagged by the same guard.
  const bad = buildAssessmentReportHtml({
    result: { ...SYNTHETIC, explanation: "This is a high risk area." },
    locationLabel: null,
    point: null,
    generatedAt: new Date("2026-01-02T03:04:05Z"),
  });
  assert.ok(findAffirmativeRiskClaims(bad).length > 0);
});
