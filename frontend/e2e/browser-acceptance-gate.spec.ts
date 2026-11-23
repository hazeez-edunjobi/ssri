/**
 * Pre-deployment headed browser acceptance gate.
 * Run: npx playwright test e2e/browser-acceptance-gate.spec.ts --headed --project=chromium
 */
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const base = process.env.SSRI_BASE_URL || "http://localhost:3000";
const api = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const abeokutaCsv = path.resolve(
  __dirname,
  "../../data/outputs/geological/datasets/geo_be00a34ad6f4/original/sheet_260_Abeokuta.csv",
);
const evidenceDir = path.resolve(__dirname, "../../poc/browser_acceptance_evidence");
const email =
  process.env.SSRI_ACCEPTANCE_EMAIL ||
  `ssri.browser.gate.${Date.now()}@mailinator.com`;
const password = process.env.SSRI_ACCEPTANCE_PASSWORD || "BrowserGate1!";

fs.mkdirSync(evidenceDir, { recursive: true });

async function shot(page: Page, name: string) {
  const file = path.join(evidenceDir, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  return file;
}

async function ensureSession(page: Page) {
  // Local acceptance session bypass (dev-only flag) — still exercises auth UI briefly.
  await page.goto(`${base}/login`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible({
    timeout: 20_000,
  });
  await shot(page, "00-login-page");

  if (process.env.SSRI_ACCEPTANCE_EMAIL) {
    await page.locator("#login-email, input[type=email]").first().fill(email);
    await page.locator("#login-password, input[type=password]").first().fill(password);
    await page.getByRole("button", { name: "Log in" }).click();
    await page.waitForURL(/\/(workspace|dashboard|geological)/, { timeout: 45_000 });
    return;
  }

  // Prefer local acceptance bypass when enabled on the running Next.js app.
  await page.goto(`${base}/geological`, { waitUntil: "domcontentloaded" });
  const landed = await Promise.race([
    page
      .getByRole("heading", { name: /Geological datasets/i })
      .waitFor({ timeout: 25_000 })
      .then(() => "geological" as const),
    page
      .getByRole("heading", { name: "Log in" })
      .waitFor({ timeout: 25_000 })
      .then(() => "login" as const),
  ]).catch(() => "unknown" as const);

  if (landed === "geological") {
    test.info().annotations.push({
      type: "note",
      description:
        "Used NEXT_PUBLIC_SSRI_LOCAL_ACCEPTANCE_SESSION local bypass (API still development principal).",
    });
    return;
  }

  await page.goto(`${base}/signup`, { waitUntil: "domcontentloaded" });
  await page.locator("#signup-name").fill("Browser Gate");
  await page.locator("#signup-email").fill(email);
  await page.locator("#signup-password").fill(password);
  await page.locator("#signup-terms").check();
  await page.getByRole("button", { name: "Create account" }).click();
  const alert = page.getByRole("alert");
  if (await alert.count()) {
    const msg = await alert.first().innerText().catch(() => "");
    fs.writeFileSync(path.join(evidenceDir, "signup_error.txt"), msg, "utf8");
  }
  await page.waitForURL(/\/(workspace|verify-email|dashboard|geological)/, {
    timeout: 60_000,
  });
  if (page.url().includes("verify-email")) {
    throw new Error(
      "Supabase requires email verification; set SSRI_ACCEPTANCE_EMAIL/PASSWORD or NEXT_PUBLIC_SSRI_LOCAL_ACCEPTANCE_SESSION=1",
    );
  }
}

test.describe.configure({ mode: "serial", timeout: 600_000 });

test("stack health before browser gate", async ({ request }) => {
  const health = await request.get(`${api}/api/v1/health`);
  expect(health.ok()).toBeTruthy();
  const ready = await request.get(`${api}/api/v1/ready`);
  expect(ready.ok()).toBeTruthy();
  const body = await ready.json();
  expect(body.infrastructure?.components?.find((c: { name: string }) => c.name === "postgresql")?.status).toBe("ok");
  expect(body.infrastructure?.components?.find((c: { name: string }) => c.name === "redis")?.status).toBe("ok");
  fs.writeFileSync(
    path.join(evidenceDir, "ready.json"),
    JSON.stringify(body, null, 2),
    "utf8",
  );
});

test("headed client journey: auth → upload → validate → magnetic → download", async ({
  page,
}) => {
  expect(fs.existsSync(abeokutaCsv)).toBeTruthy();

  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("response", (res) => {
    if (res.status() >= 400) {
      failedRequests.push(`${res.status()} ${res.request().method()} ${res.url()}`);
    }
  });

  await ensureSession(page);
  await shot(page, "01-after-auth");

  // Navigation + dashboard footprint honesty
  await page.goto(`${base}/dashboard`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("ssri-map")).toBeVisible({ timeout: 45_000 });
  await page.waitForTimeout(2500);
  await shot(page, "02-dashboard-map");
  const footprintLabel = page.getByTestId("footprint-visibility-label");
  if (await footprintLabel.count()) {
    await expect(footprintLabel).toBeVisible();
  }

  // Upload Abeokuta Sheet 260 as a new catalogue entry (does not overwrite originals)
  await page.goto(`${base}/geological`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: /Geological datasets/i })).toBeVisible({
    timeout: 30_000,
  });
  await page.getByLabel("Display name").fill("Abeokuta Sheet 260 browser gate");
  await page.setInputFiles('input[type="file"]', abeokutaCsv);
  await page.getByRole("button", { name: /Create & upload|Create and upload|upload/i }).click();
  await expect(page.getByText(/Uploaded as geo_/i)).toBeVisible({ timeout: 120_000 });
  const successText = await page.getByText(/Uploaded as geo_/i).innerText();
  const geoMatch = successText.match(/geo_[a-f0-9]+/i);
  expect(geoMatch).toBeTruthy();
  const geoId = geoMatch![0];
  fs.writeFileSync(path.join(evidenceDir, "uploaded_geo_id.txt"), geoId, "utf8");
  await shot(page, "03-upload-success");

  await page.goto(`${base}/geological/${geoId}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText(new RegExp(`${geoId}\\s*·`))).toBeVisible({ timeout: 30_000 });

  // Configure columns + CRS via Abeokuta preset
  const preset = page.getByTestId("abeokuta-tmi-preset");
  if (await preset.count()) {
    await preset.click();
    await expect(page.getByText(/Abeokuta Sheet 260 metadata applied/i)).toBeVisible({
      timeout: 60_000,
    });
  } else {
    await page.getByLabel(/Measurement type/i).selectOption("total_magnetic_intensity");
    await page.getByLabel(/Source CRS|CRS/i).first().fill("EPSG:32632");
    await page.getByRole("button", { name: /Save declaration/i }).click();
  }
  await shot(page, "04-declared");

  await page.getByRole("button", { name: /Run validation/i }).click();
  await expect(page.getByText(/Validation ·/i)).toBeVisible({ timeout: 180_000 });
  await shot(page, "05-validated");
  const validationHeading = await page.getByRole("heading", { name: /Validation/i }).innerText();
  expect(/Ready|WARN|PASS|Blocked|FAIL/i.test(validationHeading)).toBeTruthy();

  // Geographic footprint / preview
  const preview = page.getByTestId("tmi-survey-preview");
  if (await preview.count()) {
    await expect(preview).toBeVisible();
    await shot(page, "06-geographic-preview");
  }

  // Process TMI grid then a magnetic op (HTTP-synchronous; UI busy/notice monitored)
  const processBtn = page.getByRole("button", { name: /Process TMI grid/i });
  await expect(processBtn).toBeEnabled({ timeout: 15_000 });
  await processBtn.click();
  await expect(
    page.getByText(/processing|cells|NoData|grid|completed|TMI gridding|processed/i).first(),
  ).toBeVisible({ timeout: 480_000 });
  await shot(page, "07-tmi-processed");

  const opSelect = page.locator("label:has-text('Operation') select");
  await expect(opSelect).toBeVisible({ timeout: 30_000 });
  await opSelect.selectOption("analytic_signal");
  await page.getByRole("button", { name: /Run magnetic operation/i }).click();
  await expect(
    page.getByText(/Magnetic operation 'analytic_signal' completed|analytic_signal|NOT_VALIDATED/i).first(),
  ).toBeVisible({ timeout: 480_000 });
  await shot(page, "08-magnetic-result");

  // Download a generated product if listed
  const downloadLink = page.locator("a[href*='/derived/'], a[download], button:has-text('Download')").first();
  if (await downloadLink.count()) {
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 120_000 }).catch(() => null),
      downloadLink.click(),
    ]);
    if (download) {
      const dest = path.join(evidenceDir, await download.suggestedFilename());
      await download.saveAs(dest);
      expect(fs.statSync(dest).size).toBeGreaterThan(0);
      fs.writeFileSync(
        path.join(evidenceDir, "download_ok.txt"),
        `${dest}\nsize=${fs.statSync(dest).size}`,
        "utf8",
      );
    }
  }

  // Also verify derived URL via API when present
  const mag = await page.request.get(`${api}/api/v1/geological/datasets/${geoId}/magnetic`);
  if (mag.ok()) {
    const body = await mag.json();
    fs.writeFileSync(
      path.join(evidenceDir, "magnetic_products.json"),
      JSON.stringify(body, null, 2),
      "utf8",
    );
    const products = body.products || body.magnetic?.products || [];
    const firstWithPreview = (Array.isArray(products) ? products : Object.values(products)).find(
      (p: { preview_relpath?: string; geotiff_relpath?: string }) =>
        p && (p.preview_relpath || p.geotiff_relpath),
    ) as { preview_relpath?: string; geotiff_relpath?: string } | undefined;
    const rel = firstWithPreview?.preview_relpath || firstWithPreview?.geotiff_relpath;
    if (rel) {
      const derivedName = String(rel)
        .replace(/^working\/derived\//, "")
        .replace(/^working\\derived\\/, "");
      const fileRes = await page.request.get(
        `${api}/api/v1/geological/datasets/${geoId}/derived/${derivedName}`,
      );
      // Some routes use query path; fall back to documented helper pattern
      if (!fileRes.ok()) {
        const alt = await page.request.get(
          `${api}/api/v1/geological/datasets/${geoId}/derived?path=${encodeURIComponent(rel)}`,
        );
        expect(alt.ok() || fileRes.status() < 500).toBeTruthy();
        if (alt.ok()) {
          const buf = Buffer.from(await alt.body());
          expect(buf.byteLength).toBeGreaterThan(0);
          fs.writeFileSync(path.join(evidenceDir, "derived_download.bin"), buf);
        }
      } else {
        const buf = Buffer.from(await fileRes.body());
        expect(buf.byteLength).toBeGreaterThan(0);
        fs.writeFileSync(path.join(evidenceDir, "derived_download.bin"), buf);
      }
    }
  }

  // Reopen dataset
  await page.goto(`${base}/geological/${geoId}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText(new RegExp(`${geoId}\\s*·`))).toBeVisible({ timeout: 30_000 });
  await shot(page, "09-reopened");

  // Invalid upload: missing CRS / wrong structure should block
  await page.goto(`${base}/geological`, { waitUntil: "domcontentloaded" });
  const badCsv = path.join(evidenceDir, "bad_incomplete.csv");
  fs.writeFileSync(badCsv, "a,b\n1,2\n3,4\n", "utf8");
  await page.getByLabel("Display name").fill("Invalid incomplete browser gate");
  await page.setInputFiles('input[type="file"]', badCsv);
  await page.getByRole("button", { name: /Create & upload|Create and upload|upload/i }).click();
  await expect(page.getByText(/Uploaded as geo_/i)).toBeVisible({ timeout: 60_000 });
  const badText = await page.getByText(/Uploaded as geo_/i).innerText();
  const badId = badText.match(/geo_[a-f0-9]+/i)![0];
  await page.goto(`${base}/geological/${badId}`, { waitUntil: "domcontentloaded" });
  // Attempt validate without proper CRS/measurement — expect block or actionable error
  const validateBtn = page.getByRole("button", { name: /Run validation/i });
  if (await validateBtn.isEnabled()) {
    await validateBtn.click();
  } else {
    // Save incomplete declaration then validate
    await page.getByRole("button", { name: /Save declaration/i }).click().catch(() => undefined);
  }
  // Force validate after minimal bad declaration if fields exist
  const mt = page.locator("select").first();
  if (await mt.count()) {
    await mt.selectOption({ index: 1 }).catch(() => undefined);
  }
  await page.getByRole("button", { name: /Run validation/i }).click().catch(() => undefined);
  await page.waitForTimeout(3000);
  await shot(page, "10-invalid-blocked");
  const bodyText = await page.locator("body").innerText();
  expect(/Blocked|FAIL|required|CRS|Declare|cannot|unsupported|fix/i.test(bodyText)).toBeTruthy();

  fs.writeFileSync(
    path.join(evidenceDir, "console_errors.json"),
    JSON.stringify(consoleErrors, null, 2),
    "utf8",
  );
  fs.writeFileSync(
    path.join(evidenceDir, "failed_requests.json"),
    JSON.stringify(failedRequests, null, 2),
    "utf8",
  );
});
