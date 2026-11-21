import { test, expect, type Page } from "@playwright/test";

const dashboard = process.env.SSRI_DASHBOARD_URL || "http://localhost:3000/dashboard";
const api = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

async function openAssessmentOrSkip(page: Page) {
  await page.goto(dashboard, { waitUntil: "domcontentloaded" });
  const login = page.getByRole("heading", { name: "Log in" });
  const workspace = page.getByText("Risk Assessment Workspace");
  await expect(login.or(workspace)).toBeVisible({ timeout: 20_000 });
  if (await login.isVisible()) {
    test.skip(true, "Assessment requires a signed-in session");
  }
}

test.describe("SSRI dashboard smoke", () => {
  test("API readiness is reachable", async ({ request }) => {
    const response = await request.get(`${api}/api/v1/ready`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.status).toBe("ready");
  });

  test("anonymous visitors must log in before assessment", async ({ page }) => {
    await page.goto(dashboard, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByRole("link", { name: "Create account" })).toBeVisible();
  });

  test("point mode validation failure without selection", async ({ page }) => {
    await openAssessmentOrSkip(page);
    await page.goto(dashboard, { waitUntil: "networkidle" });
    await expect(page.getByTestId("ssri-map")).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: /Run assessment/i }).click();
    await expect(
      page.getByText("Click the map or enter coordinates to select a point."),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("polygon mode validation failure without geometry", async ({ page }) => {
    await openAssessmentOrSkip(page);
    await page.goto(dashboard, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: /Polygon/i }).click();
    await expect(page.getByTestId("ssri-map")).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: /Run assessment/i }).click();
    await expect(
      page.getByText("Draw a polygon on the map (3+ clicks)."),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("developer path controls stay collapsed for ordinary clients", async ({
    page,
  }) => {
    await openAssessmentOrSkip(page);
    await page.goto(dashboard, { waitUntil: "networkidle" });
    const advanced = page.getByTestId("advanced-operator-options");
    await expect(advanced).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("offline-features")).toBeHidden();
    await advanced.locator("summary").click();
    await expect(page.getByTestId("offline-features")).toBeVisible();
    await expect(page.getByTestId("checkpoint-path")).toBeVisible();
  });

  test("point selection + missing checkpoint validates", async ({ page }) => {
    await openAssessmentOrSkip(page);
    await page.goto(dashboard, { waitUntil: "networkidle" });
    const map = page.getByTestId("ssri-map");
    await expect(map).toBeVisible({ timeout: 30_000 });
    const box = await map.boundingBox();
    expect(box).toBeTruthy();
    if (box) {
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    }
    await page.getByRole("button", { name: /Run assessment/i }).click();
    await expect(
      page.getByText(
        /No valid production checkpoint is configured|Click the map to select a point|Assessment failed|Sign in is required/i,
      ),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("manual coordinate entry locates and validates", async ({ page }) => {
    await openAssessmentOrSkip(page);
    await page.goto(dashboard, { waitUntil: "networkidle" });
    await expect(page.getByTestId("coordinate-entry")).toBeVisible({
      timeout: 30_000,
    });
    await page.getByTestId("coord-latitude").fill("99");
    await page.getByTestId("coord-longitude").fill("3.3792");
    await page.getByTestId("coord-locate").click();
    await expect(page.getByTestId("coord-error")).toContainText(
      "Latitude must be between -90 and 90.",
    );

    await page.getByTestId("coord-latitude").fill("6.5244");
    await page.getByTestId("coord-longitude").fill("200");
    await page.getByTestId("coord-locate").click();
    await expect(page.getByTestId("coord-error")).toContainText(
      "Longitude must be between -180 and 180.",
    );

    await page.getByTestId("coord-latitude").fill("abc");
    await page.getByTestId("coord-longitude").fill("3.3792");
    await page.getByTestId("coord-locate").click();
    await expect(page.getByTestId("coord-error")).toContainText("numeric");

    await page.getByTestId("coord-latitude").fill("6.5244");
    await page.getByTestId("coord-longitude").fill("3.3792");
    await page.getByTestId("coord-locate").click();
    await expect(page.getByText("6.524400, 3.379200")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("coordinate round trip matches to 6 decimals (all quadrants)", async ({
    page,
  }) => {
    await openAssessmentOrSkip(page);
    await page.goto(dashboard, { waitUntil: "networkidle" });
    await expect(page.getByTestId("coordinate-entry")).toBeVisible({
      timeout: 30_000,
    });

    // Abeokuta (~7.16N, 3.35E) plus points in other quadrants.
    const points: Array<[string, string, string]> = [
      ["7.16", "3.35", "7.160000, 3.350000"],
      ["-33.92", "18.42", "-33.920000, 18.420000"],
      ["40.71", "-74.01", "40.710000, -74.010000"],
      ["-23.7", "133.88", "-23.700000, 133.880000"],
    ];
    for (const [lat, lon, expected] of points) {
      await page.getByTestId("coord-latitude").fill(lat);
      await page.getByTestId("coord-longitude").fill(lon);
      await page.getByTestId("coord-locate").click();
      await expect(page.getByText(expected)).toBeVisible({ timeout: 10_000 });
    }
  });

  test("clicking the map fills both coordinates to 6 decimals", async ({
    page,
  }) => {
    await openAssessmentOrSkip(page);
    await page.goto(dashboard, { waitUntil: "networkidle" });
    const map = page.getByTestId("ssri-map");
    await expect(map).toBeVisible({ timeout: 30_000 });
    const box = await map.boundingBox();
    expect(box).toBeTruthy();
    if (box) {
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    }
    const sixDp = /^-?\d+\.\d{6}$/;
    await expect(page.getByTestId("coord-latitude")).toHaveValue(sixDp);
    await expect(page.getByTestId("coord-longitude")).toHaveValue(sixDp);
  });

  test("release-shell geography panel shows CRS and warns outside region", async ({
    page,
  }) => {
    await openAssessmentOrSkip(page);
    await page.route("**/api/v1/release-shell/status", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          release_shell_enabled: true,
          limitations: [],
          scientific_validation_status: "NOT_VALIDATED",
          settings: {
            block_size_deg: 5,
            default_block_size_deg: 5,
            buffer_km: 50,
            minimums: { tiles_per_hazard: 12, blocks: 3, held_out_blocks: 1 },
            preview_unevaluated_scores: false,
            supported_channel_schemas: ["v1", "v2"],
            default_channel_schema: "v1",
            channel_schemas: {
              v1: { channel_count: 13, channel_names: ["a"] },
              v2: { channel_count: 16, channel_names: ["a"] },
            },
            hazards: [
              { name: "subsidence", class_id: 0, enabled_by_default: true },
              { name: "landslide", class_id: 1, enabled_by_default: true },
              { name: "sinkhole", class_id: 2, enabled_by_default: true },
            ],
          },
        }),
      });
    });
    await page.route("**/api/v1/release-shell/geography", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          geography: {
            checkpoint: "/data/models/best.pt",
            has_release_shell_meta: true,
            crs: "EPSG:32631",
            crs_declared: true,
            training_region: {
              blocks: ["7.0,3.0"],
              extent: { lat_min: 7.0, lat_max: 7.3, lon_min: 3.2, lon_max: 3.5 },
              n_tiles: 3,
            },
            region_extent: {
              lat_min: 7.0,
              lat_max: 7.3,
              lon_min: 3.2,
              lon_max: 3.5,
            },
            point_geographic: { latitude: 51.5, longitude: -0.12 },
            point_converted: {
              x: 525000.0,
              y: 5710000.0,
              crs: "EPSG:32631",
              axis_order: "x=easting, y=northing",
            },
            inside_training_region: false,
            outside_training_region: true,
          },
        }),
      });
    });

    await page.goto(dashboard, { waitUntil: "networkidle" });
    await page
      .locator('input[placeholder="/data/models/best.pt"]')
      .fill("/data/models/best.pt");
    await expect(page.getByTestId("checkpoint-crs")).toContainText(
      "EPSG:32631",
      { timeout: 15_000 },
    );
    await expect(page.getByTestId("training-region")).toContainText("7.000");

    // A point far outside the region triggers the matching warning.
    await page.getByTestId("coord-latitude").fill("51.5");
    await page.getByTestId("coord-longitude").fill("-0.12");
    await page.getByTestId("coord-locate").click();
    await expect(page.getByTestId("region-warning")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("assessment opens result modal on API success and failure", async ({
    page,
  }) => {
    await openAssessmentOrSkip(page);
    await page.goto(dashboard, { waitUntil: "networkidle" });
    await page.getByTestId("coord-latitude").fill("6.5244");
    await page.getByTestId("coord-longitude").fill("3.3792");
    await page.getByTestId("coord-locate").click();
    await page.locator('input[placeholder="/data/models/best.pt"]').fill(
      "/data/outputs/e2e-job/checkpoint.pt",
    );

    await page.route("**/api/v1/assess", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          assessment_id: "assess-test-modal",
          request_id: "req-test",
          model_version: "ssri-test",
          checkpoint_sha256: "abc1234567890def",
          checkpoint_dataset_name: "e2e",
          checkpoint_dataset_version: "1",
          is_fixture_checkpoint: true,
          domain_similarity_calibrated: false,
          explanation: "Mocked assessment for UI test.",
          notes: ["fixture note"],
          spatial_output_url: null,
          hazard_profiles: [
            {
              hazard_type: "subsidence",
              susceptibility_score: 0.42,
              confidence_tier: "Moderate",
              domain_similarity_score: null,
              credible_interval_80: [0.3, 0.5],
              credible_interval_95: [0.2, 0.6],
              primary_drivers: ["slope"],
            },
            {
              hazard_type: "landslide",
              susceptibility_score: 0.11,
              confidence_tier: "Low",
              domain_similarity_score: null,
              credible_interval_80: [0.05, 0.2],
              credible_interval_95: [0.01, 0.3],
              primary_drivers: [],
            },
            {
              hazard_type: "sinkhole",
              susceptibility_score: 0.07,
              confidence_tier: "Low",
              domain_similarity_score: null,
              credible_interval_80: [0.02, 0.1],
              credible_interval_95: [0.01, 0.15],
              primary_drivers: [],
            },
          ],
        }),
      });
    });

    await page.getByRole("button", { name: /Run assessment/i }).click();
    await expect(page.getByTestId("assess-result-modal")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("assess-result-body")).toBeVisible();
    await expect(page.getByText("assess-test-modal")).toBeVisible();
    await expect(page.getByTestId("assess-fixture-banner")).toContainText(
      "Research / fixture model",
    );
    await expect(page.getByTestId("assess-hazard-subsidence")).toContainText(
      "42.0%",
    );
    await page.getByTestId("assess-result-close").click();
    await expect(page.getByTestId("assess-result-modal")).toHaveCount(0);
    await expect(page.getByTestId("reopen-assess-result")).toBeVisible();

    await page.unroute("**/api/v1/assess");
    await page.route("**/api/v1/assess", async (route) => {
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Mocked assess failure" }),
      });
    });
    await page.getByRole("button", { name: /Run assessment/i }).click();
    await expect(page.getByTestId("assess-result-modal")).toBeVisible();
    await expect(page.getByTestId("assess-result-error")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("Gravity WGM2012 layer loads and visibility toggle works", async ({
    page,
    request,
  }) => {
    const layer = await request.get(`${api}/api/v1/layers/gravity`);
    expect(layer.ok()).toBeTruthy();
    const body = await layer.json();
    expect(body.metadata.dataset).toContain("WGM2012");
    expect(body.metadata.dataset.toLowerCase()).not.toContain("eigen6c4");
    expect(body.features.length).toBeGreaterThan(0);

    await openAssessmentOrSkip(page);
    await page.goto(dashboard, { waitUntil: "networkidle" });
    await expect(page.getByTestId("gravity-layer-panel")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("gravity-layer-title")).toContainText(
      "WGM2012 Complete Spherical Bouguer",
      { timeout: 45_000 },
    );
    await expect(page.getByTestId("ssri-map-status")).toHaveAttribute(
      "data-gravity-loaded",
      "true",
      { timeout: 45_000 },
    );
    const toggle = page.getByTestId("gravity-visibility-toggle");
    await expect(toggle).toBeChecked();
    await toggle.click();
    await expect(page.getByTestId("ssri-map-status")).toHaveAttribute(
      "data-gravity-visible",
      "false",
    );
    await toggle.click();
    await expect(page.getByTestId("ssri-map-status")).toHaveAttribute(
      "data-gravity-visible",
      "true",
    );
  });
});
