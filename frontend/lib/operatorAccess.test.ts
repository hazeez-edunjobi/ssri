import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import {
  canAccessAdminUi,
  canAccessOperatorUi,
  configuredOperatorApiKey,
  operatorAccessDeniedReason,
} from "./operatorAccess.ts";

const here = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(here, "..");

function readApp(rel: string): string {
  return readFileSync(join(frontendRoot, rel), "utf8");
}

describe("operator and admin UI access helpers", () => {
  it("blocks unauthenticated operator access without local acceptance or API key", () => {
    assert.equal(
      canAccessOperatorUi({
        localAcceptance: false,
        hasOperatorApiKey: false,
        hasSession: false,
        platformRole: null,
      }),
      false,
    );
    assert.ok(
      operatorAccessDeniedReason({
        localAcceptance: false,
        hasOperatorApiKey: false,
        hasSession: false,
        platformRole: null,
      }),
    );
  });

  it("blocks authenticated non-admin users from operator UI", () => {
    assert.equal(
      canAccessOperatorUi({
        localAcceptance: false,
        hasOperatorApiKey: false,
        hasSession: true,
        platformRole: "user",
      }),
      false,
    );
  });

  it("allows platform admin, operator API key, and local acceptance for operator UI", () => {
    assert.equal(
      canAccessOperatorUi({
        localAcceptance: false,
        hasOperatorApiKey: false,
        hasSession: true,
        platformRole: "admin",
      }),
      true,
    );
    assert.equal(
      canAccessOperatorUi({
        localAcceptance: false,
        hasOperatorApiKey: true,
        hasSession: false,
        platformRole: null,
      }),
      true,
    );
    assert.equal(
      canAccessOperatorUi({
        localAcceptance: true,
        hasOperatorApiKey: false,
        hasSession: false,
        platformRole: null,
      }),
      true,
    );
  });

  it("rejects non-admin users from admin UI and keeps admin access for role=admin", () => {
    assert.equal(
      canAccessAdminUi({
        localAcceptance: false,
        hasSession: true,
        platformRole: "user",
      }),
      false,
    );
    assert.equal(
      canAccessAdminUi({
        localAcceptance: false,
        hasSession: false,
        platformRole: null,
      }),
      false,
    );
    assert.equal(
      canAccessAdminUi({
        localAcceptance: true,
        hasSession: false,
        platformRole: null,
      }),
      false,
      "local acceptance must not grant admin",
    );
    assert.equal(
      canAccessAdminUi({
        localAcceptance: false,
        hasSession: true,
        platformRole: "admin",
      }),
      true,
    );
  });

  it("reads configured operator API key from env", () => {
    assert.equal(configuredOperatorApiKey({}), null);
    assert.equal(
      configuredOperatorApiKey({ NEXT_PUBLIC_SSRI_API_KEY: "  op-key  " }),
      "op-key",
    );
  });

  it("wires operator, shell, and admin pages to access gates", () => {
    const operator = readApp("app/training/operator/page.tsx");
    const shell = readApp("app/shell/page.tsx");
    const admin = readApp("app/admin/page.tsx");

    assert.ok(operator.includes("RequireOperatorAccess"));
    assert.ok(operator.includes('nextPath="/training/operator"'));
    assert.ok(shell.includes("RequireOperatorAccess"));
    assert.ok(shell.includes('nextPath="/shell"'));
    assert.ok(admin.includes("RequireAdminAccess"));
  });

  it("preserves release-shell feature-flag messaging in /shell", () => {
    const shell = readApp("app/shell/page.tsx");
    assert.ok(shell.includes("release_shell_enabled"));
    assert.ok(shell.includes("SSRI_RELEASE_SHELL"));
  });

  it("keeps dashboard and workspace session patterns intact", () => {
    const dashboard = readApp("app/dashboard/page.tsx");
    const workspace = readApp("app/workspace/page.tsx");
    assert.ok(dashboard.includes("RequireSession"));
    assert.ok(dashboard.includes('nextPath="/dashboard"'));
    assert.ok(workspace.includes("PlatformShell"));
    assert.ok(workspace.includes('role === "admin"'));
  });
});
