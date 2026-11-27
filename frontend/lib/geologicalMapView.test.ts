import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  computeViewTransform,
  extentFromCoordinates,
  niceScaleMetres,
  screenToWorld,
  worldToScreen,
} from "./geologicalMapView.ts";

describe("geologicalMapView", () => {
  it("preserves equal metres-per-pixel when fitting a non-square extent", () => {
    const extent = { xmin: 0, xmax: 2000, ymin: 0, ymax: 1000 };
    const view = computeViewTransform(800, 600, extent, 1);
    const worldAspect = 2000 / 1000;
    const frameAspect = view.frame.width / view.frame.height;
    assert.ok(Math.abs(worldAspect - frameAspect) < 1e-9);
    const [px0, py0] = worldToScreen(0, 0, view);
    const [px1] = worldToScreen(1000, 0, view);
    const [, py1] = worldToScreen(0, 1000, view);
    const dx = Math.abs(px1 - px0);
    const dy = Math.abs(py1 - py0);
    assert.ok(Math.abs(dx - dy) < 1e-6);
  });

  it("round-trips world ↔ screen at the frame centre", () => {
    const extent = extentFromCoordinates([
      [
        [500000, 800000],
        [501000, 801000],
      ],
    ]);
    assert.ok(extent);
    const view = computeViewTransform(640, 480, extent, 1);
    const midX = (extent.xmin + extent.xmax) / 2;
    const midY = (extent.ymin + extent.ymax) / 2;
    const screen = worldToScreen(midX, midY, view);
    const back = screenToWorld(screen[0], screen[1], view);
    assert.ok(Math.abs(back[0] - midX) < 1e-6);
    assert.ok(Math.abs(back[1] - midY) < 1e-6);
  });

  it("formats a readable scale bar length", () => {
    const scale = niceScaleMetres(10, 80);
    assert.equal(scale.metres, 1000);
    assert.equal(scale.label, "1.0 km");
  });
});
