import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  clientAllowsLocalAcceptanceSession,
  clientAllowsPresentationDemo,
  demoMisconfigurationNotice,
  resolvePresentationDemoActive,
} from "./productionIntegrity.ts";

describe("productionIntegrity", () => {
  it("exports resolve helpers that refuse demo when NODE_ENV is production", () => {
    // Module reads process.env at call time for the allow flag; NODE_ENV is
    // fixed for the running test process. Assert the production branch logic
    // via the documented contract: production builds always deny.
    const previous = process.env.NEXT_PUBLIC_SSRI_ALLOW_PRESENTATION_DEMO;
    const previousNode = process.env.NODE_ENV;
    try {
      process.env.NODE_ENV = "production";
      process.env.NEXT_PUBLIC_SSRI_ALLOW_PRESENTATION_DEMO = "true";
      assert.equal(clientAllowsPresentationDemo(), false);
      assert.equal(resolvePresentationDemoActive(true), false);
      assert.match(demoMisconfigurationNotice(true) ?? "", /will not/i);
    } finally {
      if (previous === undefined) {
        delete process.env.NEXT_PUBLIC_SSRI_ALLOW_PRESENTATION_DEMO;
      } else {
        process.env.NEXT_PUBLIC_SSRI_ALLOW_PRESENTATION_DEMO = previous;
      }
      process.env.NODE_ENV = previousNode;
    }
  });

  it("refuses local acceptance session bypass in production", () => {
    const previousNode = process.env.NODE_ENV;
    const previousFlag = process.env.NEXT_PUBLIC_SSRI_LOCAL_ACCEPTANCE_SESSION;
    try {
      process.env.NODE_ENV = "production";
      process.env.NEXT_PUBLIC_SSRI_LOCAL_ACCEPTANCE_SESSION = "true";
      assert.equal(clientAllowsLocalAcceptanceSession(), false);
    } finally {
      process.env.NODE_ENV = previousNode;
      if (previousFlag === undefined) {
        delete process.env.NEXT_PUBLIC_SSRI_LOCAL_ACCEPTANCE_SESSION;
      } else {
        process.env.NEXT_PUBLIC_SSRI_LOCAL_ACCEPTANCE_SESSION = previousFlag;
      }
    }
  });

  it("requires explicit opt-in outside production", () => {
    const previous = process.env.NEXT_PUBLIC_SSRI_ALLOW_PRESENTATION_DEMO;
    const previousNode = process.env.NODE_ENV;
    try {
      process.env.NODE_ENV = "development";
      delete process.env.NEXT_PUBLIC_SSRI_ALLOW_PRESENTATION_DEMO;
      assert.equal(clientAllowsPresentationDemo(), false);
      assert.equal(resolvePresentationDemoActive(true), false);

      process.env.NEXT_PUBLIC_SSRI_ALLOW_PRESENTATION_DEMO = "true";
      assert.equal(clientAllowsPresentationDemo(), true);
      assert.equal(resolvePresentationDemoActive(true), true);
      assert.equal(resolvePresentationDemoActive(false), false);
      assert.equal(demoMisconfigurationNotice(true), null);
    } finally {
      if (previous === undefined) {
        delete process.env.NEXT_PUBLIC_SSRI_ALLOW_PRESENTATION_DEMO;
      } else {
        process.env.NEXT_PUBLIC_SSRI_ALLOW_PRESENTATION_DEMO = previous;
      }
      process.env.NODE_ENV = previousNode;
    }
  });
});
