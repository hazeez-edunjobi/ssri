import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * Frontend alignment rehearsal (Task 5).
 *
 * Runs the REAL owner flow in a browser against a REAL backend:
 *   /shell  upload -> validate -> train (3 seeds) -> evaluate -> select checkpoint
 *   /dashboard  pick point on the map -> assess -> download the HTML report.
 *
 * The backend is a local uvicorn with SSRI_RELEASE_SHELL=true writing only to a
 * git-ignored temp directory (poc/release_shell/outputs/frontend_rehearsal/work),
 * so no trained checkpoint can be committed. Supabase auth is mocked in-page
 * because the dashboard route is session-gated and there are no local creds.
 */
const REPO_ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(
  REPO_ROOT,
  "poc",
  "release_shell",
  "outputs",
  "frontend_rehearsal",
);
const WORK_DIR = path.join(OUT_DIR, "work");
const API_PORT = process.env.SSRI_REHEARSAL_API_PORT || "8000";
const WEB_PORT = process.env.SSRI_REHEARSAL_WEB_PORT || "3000";
const PYTHON =
  process.env.SSRI_REHEARSAL_PYTHON ||
  path.join(REPO_ROOT, "model", ".venv", "Scripts", "python.exe");

export default defineConfig({
  testDir: "./e2e-rehearsal",
  outputDir: path.join(OUT_DIR, "playwright-artifacts"),
  // A cold 3-seed CPU train plus a cold Next dev compile is slow on purpose.
  timeout: 30 * 60_000,
  expect: { timeout: 45_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    ["json", { outputFile: path.join(OUT_DIR, "playwright-report.json") }],
  ],
  use: {
    ...devices["Desktop Chrome"],
    channel: "chrome",
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "on",
    screenshot: "only-on-failure",
    video: "off",
    launchOptions: {
      args: ["--use-gl=angle", "--use-angle=swiftshader"],
    },
  },
  webServer: [
    {
      command: `"${PYTHON}" -m uvicorn ssri_model.api.app:app --host 127.0.0.1 --port ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/api/v1/ready`,
      cwd: path.join(REPO_ROOT, "model"),
      reuseExistingServer: false,
      timeout: 180_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        PYTHONPATH: path.join(REPO_ROOT, "model", "src"),
        SSRI_API_ENVIRONMENT: "development",
        SSRI_API_OUTPUT_ROOT: path.join(WORK_DIR, "service-outputs"),
        SSRI_RELEASE_SHELL: "true",
        SSRI_RELEASE_SHELL_BUFFER_KM: "0",
        SSRI_RELEASE_SHELL_MIN_TILES: "1",
        SSRI_RELEASE_SHELL_MIN_BLOCKS: "4",
        SSRI_RELEASE_SHELL_MIN_HELD_OUT: "1",
        SSRI_ASSESS_SOFTMAX: "true",
      },
    },
    {
      command: `npm run dev -- --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}/`,
      cwd: __dirname,
      reuseExistingServer: false,
      timeout: 300_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        // Matches frontend/.env.local; explicit so the rehearsal never points at
        // a remote API.
        NEXT_PUBLIC_API_URL: `http://localhost:${API_PORT}`,
        PORT: WEB_PORT,
      },
    },
  ],
});
