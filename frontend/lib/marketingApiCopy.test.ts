import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import {
  AVAILABLE_API_CAPABILITIES,
  FORBIDDEN_LIVE_MARKETING_CLAIMS,
  LIVE_ASSESS_ROUTE,
  ROADMAP_API_ITEMS,
} from "./marketingApiCopy.ts";

const here = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(here, "..");

function readApp(rel: string): string {
  return readFileSync(join(frontendRoot, rel), "utf8");
}

describe("marketing API copy accuracy", () => {
  it("advertises the live assess route as POST /api/v1/assess", () => {
    assert.equal(LIVE_ASSESS_ROUTE, "POST /api/v1/assess");
    assert.ok(
      AVAILABLE_API_CAPABILITIES.some((item) => item.route === "POST /api/v1/assess"),
    );
  });

  it("does not list unimplemented endpoints as available", () => {
    const availableBlob = AVAILABLE_API_CAPABILITIES.map(
      (item) => `${item.route} ${item.summary}`,
    ).join("\n");
    for (const claim of FORBIDDEN_LIVE_MARKETING_CLAIMS) {
      assert.equal(
        availableBlob.includes(claim),
        false,
        `available capabilities must not include live claim: ${claim}`,
      );
    }
  });

  it("marks /v1/hazard and SDKs as roadmap / not shipped", () => {
    const roadmapBlob = ROADMAP_API_ITEMS.map(
      (item) => `${item.label} ${item.note}`,
    ).join("\n");
    assert.ok(roadmapBlob.includes("/v1/hazard"));
    assert.ok(roadmapBlob.includes("ssri-python") || roadmapBlob.includes("@ssri/sdk"));
    assert.ok(/not (implemented|published|shipped)/i.test(roadmapBlob));
  });

  it("developers and platform pages use shared copy and do not hardcode live /v1/hazard", () => {
    const developers = readApp("app/developers/page.tsx");
    const platform = readApp("app/platform/page.tsx");

    for (const source of [developers, platform]) {
      assert.ok(source.includes("marketingApiCopy"));
      assert.ok(source.includes("AVAILABLE_API_CAPABILITIES"));
      assert.ok(source.includes("ROADMAP_API_ITEMS"));
      // Must not present /v1/hazard outside the shared roadmap module.
      assert.equal(source.includes("/v1/hazard"), false);
      assert.equal(source.includes("pip install ssri-python"), false);
      assert.equal(source.includes("POST /v1/assessments"), false);
    }

    assert.ok(developers.includes("LIVE_ASSESS_ROUTE") || developers.includes("ASSESS_CURL_EXAMPLE"));
    assert.ok(developers.includes("developers-available-api"));
    assert.ok(developers.includes("developers-roadmap-api"));
    assert.ok(platform.includes("platform-available-api"));
    assert.ok(platform.includes("platform-roadmap-api"));
  });
});
