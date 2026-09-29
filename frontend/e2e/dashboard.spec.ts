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
      page.getByText("Click the map to select a point, or provide offline features path."),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("polygon mode validation failure without geometry", async ({ page }) => {
    await openAssessmentOrSkip(page);
    await page.goto(dashboard, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: /Polygon/i }).click();
    await expect(page.getByTestId("ssri-map")).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: /Run assessment/i }).click();
    await expect(
      page.getByText("Draw a polygon (3+ clicks) or provide offline features path."),
    ).toBeVisible({ timeout: 15_000 });
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
      page.getByText(/Provide a checkpoint path|Click the map to select a point/i),
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
    await expect(page.getByText("6.52440, 3.37920")).toBeVisible({
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
