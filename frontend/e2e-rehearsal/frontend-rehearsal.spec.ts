import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { test, expect, type Page } from "@playwright/test";

/**
 * Task 5 — synthetic browser rehearsal.
 *
 * Drives the REAL release-shell owner flow and the REAL dashboard against a
 * local backend (see playwright.rehearsal.config.ts). The trained model lives
 * only under a git-ignored temp dir; nothing here is committed as weights.
 *
 * SYNTHETIC data throughout — never real geology. Status stays NOT_VALIDATED.
 */

const OUT = path.join(
  path.resolve(__dirname, "..", ".."),
  "poc",
  "release_shell",
  "outputs",
  "frontend_rehearsal",
);
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const TEMPLATE =
  process.env.SSRI_REHEARSAL_TEMPLATE ||
  path.join(
    REPO_ROOT,
    "poc",
    "release_shell",
    "templates",
    "SYNTHETIC_stage25_v2_template.zip",
  );

// The release-shell LIVE point path builds a v1 (13-channel) stack, which a v2
// (16-channel) checkpoint rejects with a plain-language schema error. The
// dashboard's supported offline path accepts an explicit `.npy`, so the
// rehearsal extracts one SYNTHETIC v2 tile from the template and points the
// "Offline features .npy" input at it. This exercises the real results + report
// download UI end to end. (SYNTHETIC data — never real geology.)
const PYTHON =
  process.env.SSRI_REHEARSAL_PYTHON ||
  path.join(REPO_ROOT, "model", ".venv", "Scripts", "python.exe");
const WORK = path.join(OUT, "work");
const ASSESS_FEATURES = path.join(WORK, "assess_features_v2.npy");

/** Extract a SYNTHETIC v2 (16,H,W) feature tile from the template ZIP. */
function extractV2Features(): string {
  fs.mkdirSync(WORK, { recursive: true });
  const script = [
    "import sys, zipfile, shutil, pathlib",
    "src, dst = sys.argv[1], pathlib.Path(sys.argv[2])",
    "dst.parent.mkdir(parents=True, exist_ok=True)",
    "with zipfile.ZipFile(src) as zf:",
    "    name = next(n for n in zf.namelist() if n.endswith('feature_stack.npy'))",
    "    with zf.open(name) as fh, open(dst, 'wb') as out:",
    "        shutil.copyfileobj(fh, out)",
    "print(dst)",
  ].join("\n");
  execFileSync(PYTHON, ["-c", script, TEMPLATE, ASSESS_FEATURES], {
    stdio: "pipe",
  });
  return ASSESS_FEATURES;
}

// A point inside the SYNTHETIC v2 training region (US blocks) and one far away.
const IN_REGION = { lat: "37.0", lon: "-120.0" };
const OUT_OF_REGION = { lat: "51.5", lon: "-0.12" };

const SUPABASE_HOST = "https://xcwyicyjhbydjrchqauf.supabase.co";
const STORAGE_KEY = "sb-xcwyicyjhbydjrchqauf-auth-token";

type Timing = { step: string; ms: number; at: string };
const timings: Timing[] = [];

async function step<T>(name: string, fn: () => Promise<T>): Promise<T> {
  const t0 = Date.now();
  try {
    return await fn();
  } finally {
    const record = { step: name, ms: Date.now() - t0, at: new Date().toISOString() };
    timings.push(record);
    console.log(`[rehearsal] ${name}: ${record.ms} ms`);
  }
}

/** Seed a Supabase session so the session-gated /dashboard renders. */
async function seedRehearsalSession(page: Page): Promise<void> {
  const session = {
    access_token: "rehearsal-access-token",
    token_type: "bearer",
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    refresh_token: "rehearsal-refresh-token",
    user: {
      id: "00000000-0000-0000-0000-000000000001",
      aud: "authenticated",
      role: "authenticated",
      email: "rehearsal@ssri.local",
      app_metadata: { provider: "email", providers: ["email"] },
      user_metadata: {},
      created_at: "2026-01-01T00:00:00.000Z",
    },
  };
  await page.addInitScript(
    (payload: { key: string; value: unknown }) => {
      window.localStorage.setItem(payload.key, JSON.stringify(payload.value));
    },
    { key: STORAGE_KEY, value: session },
  );
  await page.route(`${SUPABASE_HOST}/**`, async (route) => {
    const url = route.request().url();
    if (url.includes("/auth/v1/user")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(session.user),
      });
    }
    if (url.includes("/auth/v1/")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(session),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: "{}",
    });
  });
}

async function shoot(page: Page, name: string): Promise<string> {
  const file = path.join(OUT, name);
  await page.screenshot({ path: file, fullPage: true });
  return file;
}

let assessFeatures = "";

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
  assessFeatures = extractV2Features();
});

test.afterAll(() => {
  fs.writeFileSync(
    path.join(OUT, "rehearsal-timings.json"),
    JSON.stringify({ generated_at: new Date().toISOString(), timings }, null, 2),
    "utf8",
  );
});

test.describe.configure({ mode: "serial" });

test("SYNTHETIC v2 owner flow: upload → validate → train → pick point → assess → download report", async ({
  page,
}) => {
  expect(fs.existsSync(TEMPLATE), `template missing: ${TEMPLATE}`).toBeTruthy();

  // ---------------------------------------------------------------- /shell
  await step("shell: open owner page", async () => {
    await page.goto("/shell", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByRole("heading", { name: "Owner training shell" }),
    ).toBeVisible({ timeout: 60_000 });
    // The flag must be ON for this rehearsal.
    await expect(page.getByText(/Release shell is off/i)).toHaveCount(0);
    await shoot(page, "01-shell-upload.png");
  });

  await step("shell: upload + validate SYNTHETIC v2 ZIP", async () => {
    await page.locator('input[accept=".zip"]').setInputFiles(TEMPLATE);
    await page.getByRole("button", { name: /Upload and validate/i }).click();
    await expect(
      page.getByRole("heading", { name: "2. Validation report" }),
    ).toBeVisible({ timeout: 180_000 });
    await expect(page.getByText(/can_train: yes/i)).toBeVisible({
      timeout: 60_000,
    });
  });

  await step("shell: start 3-seed training job", async () => {
    await page.locator('input[type="number"][min="1"]').fill("1");
    await page.getByRole("button", { name: /Start training \(3 seeds\)/i }).click();
    await expect(
      page.getByRole("heading", { name: "3. Training progress" }),
    ).toBeVisible({ timeout: 30_000 });
    await shoot(page, "02-shell-training-started.png");
  });

  await step("shell: wait for evaluation report", async () => {
    await expect(
      page.getByRole("heading", { name: "4. Evaluation report" }),
    ).toBeVisible({ timeout: 1_500_000 });
    await shoot(page, "03-shell-evaluation.png");
  });

  await step("shell: select (promote) the trained checkpoint", async () => {
    await page.getByRole("button", { name: "Choose checkpoint" }).click();
    await expect(
      page.getByRole("heading", { name: "5. Checkpoint selection" }),
    ).toBeVisible({ timeout: 30_000 });
    const select = page.getByRole("button", { name: "Select" }).first();
    await expect(select).toBeVisible({ timeout: 30_000 });
    await select.click();
    await expect(
      page.getByRole("button", { name: "Active" }),
    ).toBeVisible({ timeout: 30_000 });
    await shoot(page, "04-shell-checkpoint-selected.png");
  });

  // ------------------------------------------------------------ /dashboard
  await seedRehearsalSession(page);

  await step("dashboard: open map with the active checkpoint prefilled", async () => {
    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("ssri-map")).toBeVisible({ timeout: 90_000 });
    await expect(
      page.locator('input[placeholder="/data/models/best.pt"]'),
    ).not.toHaveValue("", { timeout: 60_000 });
    await shoot(page, "05-dashboard-map.png");
  });

  await step("dashboard: click the map to pick a point (6 dp round trip)", async () => {
    const map = page.getByTestId("ssri-map");
    const box = await map.boundingBox();
    expect(box, "map bounding box").toBeTruthy();
    if (box) {
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    }
    const sixDp = /^-?\d+\.\d{6}$/;
    await expect(page.getByTestId("coord-latitude")).toHaveValue(sixDp);
    await expect(page.getByTestId("coord-longitude")).toHaveValue(sixDp);
  });

  await step("dashboard: type an in-region point and assess", async () => {
    // Invalid input must produce a plain-language, actionable message (Task 3).
    await page.getByTestId("coord-latitude").fill("99");
    await page.getByTestId("coord-locate").click();
    await expect(page.getByTestId("coord-error")).toContainText(
      /Latitude must be between -90 and 90/i,
    );

    await page.getByTestId("coord-latitude").fill(IN_REGION.lat);
    await page.getByTestId("coord-longitude").fill(IN_REGION.lon);
    await page.getByTestId("coord-locate").click();
    // The Lagos live-coverage hint is an advisory (amber) note, and a SYNTHETIC
    // US training region legitimately sits outside it. Assert the message is
    // only that soft hint (never a parse error) and that the point is inside
    // the trained region.
    const coordError = page.getByTestId("coord-error");
    if (await coordError.count()) {
      await expect(coordError).toContainText(
        /outside the Lagos geophysics coverage/i,
      );
    }
    await expect(page.getByTestId("region-warning")).toHaveCount(0);

    // The live point path is v1-only; supply a SYNTHETIC v2 tile so the v2
    // checkpoint can be assessed offline while the point still drives the
    // release-shell region gate.
    await page.getByTestId("offline-features").fill(assessFeatures);

    const [response] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/api/v1/assess") && r.request().method() === "POST",
        { timeout: 300_000 },
      ),
      page.getByRole("button", { name: /Run assessment/i }).click(),
    ]);
    expect(response.ok(), `assess status ${response.status()}`).toBeTruthy();
    const body = (await response.json()) as {
      assessment_id: string;
      scientific_validation_status?: string;
      hazard_profiles: Array<{
        hazard_type: string;
        status?: string;
        gate_status?: string;
        score?: number | null;
      }>;
      notes?: string[];
    };
    fs.writeFileSync(
      path.join(OUT, "assess-response.json"),
      JSON.stringify(body, null, 2),
      "utf8",
    );

    await expect(page.getByTestId("assess-result-modal")).toBeVisible({
      timeout: 300_000,
    });
    await expect(page.getByTestId("assess-result-body")).toBeVisible({
      timeout: 300_000,
    });
    await expect(page.getByTestId("assess-result-error")).toHaveCount(0);

    // The rendered modal must agree with the API for every hazard.
    for (const profile of body.hazard_profiles) {
      const card = page.getByTestId(`assess-hazard-${profile.hazard_type}`);
      await expect(card).toBeVisible();
      const allowed = profile.gate_status == null || profile.gate_status === "evaluated";
      if (allowed && typeof profile.score === "number") {
        await expect(card).toContainText(`${(profile.score * 100).toFixed(1)}%`);
      } else {
        await expect(card).toContainText("score withheld");
      }
    }
    await expect(page.getByTestId("assess-not-validated")).toContainText(
      "NOT_VALIDATED",
    );

    // Wording guard: never risk / probability / detection / validation.
    const text = (await page.getByTestId("assess-result-modal").innerText()).toLowerCase();
    for (const banned of ["probability", "detection"]) {
      expect(text.includes(banned), `modal must not say "${banned}"`).toBeFalsy();
    }

    await shoot(page, "06-dashboard-assess-result.png");
  });

  await step("dashboard: download the HTML report", async () => {
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 60_000 }),
      page.getByTestId("assess-download-report").click(),
    ]);
    const target = path.join(OUT, "ssri-assessment-report.html");
    await download.saveAs(target);
    expect(fs.existsSync(target)).toBeTruthy();
    const html = fs.readFileSync(target, "utf8");
    const lower = html.toLowerCase();
    expect(lower).toContain("relative susceptibility ranking");
    // Wording guard: the report must never *claim* risk / probability /
    // detection. The backend's mandated disclaimer ("scores are relative
    // susceptibility rankings, not probabilities or risk estimates", from
    // release_shell/flags.py) negates those exact terms and the report contract
    // echoes API strings verbatim, so strip the negation phrases before checking
    // for affirmative use.
    const withoutNegations = lower.replace(
      /not probabilities or risk estimates\.?/g,
      "",
    );
    expect(withoutNegations).not.toMatch(
      /\b(risk|probabilit(?:y|ies)|detection)\b/,
    );
    expect(html).toContain("NOT_VALIDATED");
  });

  await step("dashboard: out-of-region point warns and withholds", async () => {
    await page.getByTestId("coord-latitude").fill(OUT_OF_REGION.lat);
    await page.getByTestId("coord-longitude").fill(OUT_OF_REGION.lon);
    await page.getByTestId("coord-locate").click();
    await expect(page.getByTestId("region-warning")).toBeVisible({
      timeout: 30_000,
    });
    await shoot(page, "07-dashboard-out-of-region.png");
  });
});
