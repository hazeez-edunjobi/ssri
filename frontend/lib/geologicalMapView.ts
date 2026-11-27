/**
 * Survey-space map projection helpers for geological exploration.
 * Coordinates are in the dataset processing / GeoJSON CRS (typically projected metres).
 * Aspect ratio is preserved — never stretch X and Y independently to fill the canvas.
 */

export type SurveyExtent = {
  xmin: number;
  xmax: number;
  ymin: number;
  ymax: number;
};

export type ViewTransform = {
  /** Screen rectangle (CSS pixels) covering the full survey extent at current zoom/pan. */
  frame: { x: number; y: number; width: number; height: number };
  extent: SurveyExtent;
  center: { x: number; y: number };
  /** CSS pixels per metre (equal on both axes). */
  scale: number;
  /** Metres per CSS pixel along both axes (equal). */
  metresPerPixel: number;
  viewportWidth: number;
  viewportHeight: number;
};

export type SurveyPoint = { x: number; y: number; z: number };

const PAD_PX = 28;

export function extentFromCoordinates(
  rings: Array<Array<[number, number]>>,
  padRatio = 0.05,
): SurveyExtent | null {
  let xmin = Infinity;
  let xmax = -Infinity;
  let ymin = Infinity;
  let ymax = -Infinity;
  let any = false;
  for (const ring of rings) {
    for (const [x, y] of ring) {
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
      any = true;
      xmin = Math.min(xmin, x);
      xmax = Math.max(xmax, x);
      ymin = Math.min(ymin, y);
      ymax = Math.max(ymax, y);
    }
  }
  if (!any) return null;
  const dx = Math.max(xmax - xmin, 1);
  const dy = Math.max(ymax - ymin, 1);
  const padX = dx * padRatio;
  const padY = dy * padRatio;
  return {
    xmin: xmin - padX,
    xmax: xmax + padX,
    ymin: ymin - padY,
    ymax: ymax + padY,
  };
}

export function extentFromProvenance(
  provenance: Record<string, unknown> | null | undefined,
): SurveyExtent | null {
  if (!provenance) return null;
  const xmin = Number(provenance.xmin);
  const xmax = Number(provenance.xmax);
  const ymin = Number(provenance.ymin);
  const ymax = Number(provenance.ymax);
  if (![xmin, xmax, ymin, ymax].every(Number.isFinite)) return null;
  if (xmax <= xmin || ymax <= ymin) return null;
  return { xmin, xmax, ymin, ymax };
}

export function extentFromSurveyLocal(
  extent:
    | {
        xmin: number;
        xmax: number;
        ymin: number;
        ymax: number;
      }
    | null
    | undefined,
): SurveyExtent | null {
  if (!extent) return null;
  const { xmin, xmax, ymin, ymax } = extent;
  if (![xmin, xmax, ymin, ymax].every(Number.isFinite)) return null;
  if (xmax <= xmin || ymax <= ymin) return null;
  return { xmin, xmax, ymin, ymax };
}

export function unionSurveyExtents(
  extents: Array<SurveyExtent | null | undefined>,
): SurveyExtent | null {
  let xmin = Infinity;
  let xmax = -Infinity;
  let ymin = Infinity;
  let ymax = -Infinity;
  let any = false;
  for (const e of extents) {
    if (!e) continue;
    any = true;
    xmin = Math.min(xmin, e.xmin);
    xmax = Math.max(xmax, e.xmax);
    ymin = Math.min(ymin, e.ymin);
    ymax = Math.max(ymax, e.ymax);
  }
  if (!any) return null;
  return { xmin, xmax, ymin, ymax };
}

/**
 * Fit an extent into a CSS-pixel viewport with equal metres/pixel (letterbox).
 * zoom=1 fits the full extent; higher values zoom toward `center`.
 */
export function computeViewTransform(
  viewportWidth: number,
  viewportHeight: number,
  extent: SurveyExtent,
  zoom = 1,
  center?: { x: number; y: number } | null,
): ViewTransform {
  const w = Math.max(viewportWidth, 1);
  const h = Math.max(viewportHeight, 1);
  const worldW = Math.max(extent.xmax - extent.xmin, 1e-9);
  const worldH = Math.max(extent.ymax - extent.ymin, 1e-9);
  const availW = Math.max(w - PAD_PX * 2, 1);
  const availH = Math.max(h - PAD_PX * 2, 1);
  const fitScale = Math.min(availW / worldW, availH / worldH);
  const scale = fitScale * Math.max(zoom, 0.25);
  const cx = center?.x ?? (extent.xmin + extent.xmax) / 2;
  const cy = center?.y ?? (extent.ymin + extent.ymax) / 2;
  const frame = {
    x: w / 2 + (extent.xmin - cx) * scale,
    y: h / 2 - (extent.ymax - cy) * scale,
    width: worldW * scale,
    height: worldH * scale,
  };
  return {
    frame,
    extent,
    center: { x: cx, y: cy },
    scale,
    metresPerPixel: 1 / scale,
    viewportWidth: w,
    viewportHeight: h,
  };
}

export function worldToScreen(
  x: number,
  y: number,
  transform: ViewTransform,
): [number, number] {
  const px = transform.viewportWidth / 2 + (x - transform.center.x) * transform.scale;
  const py = transform.viewportHeight / 2 - (y - transform.center.y) * transform.scale;
  return [px, py];
}

export function screenToWorld(
  px: number,
  py: number,
  transform: ViewTransform,
): [number, number] {
  const x = transform.center.x + (px - transform.viewportWidth / 2) / transform.scale;
  const y = transform.center.y - (py - transform.viewportHeight / 2) / transform.scale;
  return [x, y];
}

export function niceScaleMetres(
  metresPerPixel: number,
  targetPx = 80,
): {
  metres: number;
  pixels: number;
  label: string;
} {
  const raw = metresPerPixel * targetPx;
  const exp = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1))));
  const candidates = [1, 2, 5, 10].map((n) => n * exp);
  let best = candidates[0];
  for (const c of candidates) {
    if (Math.abs(c - raw) < Math.abs(best - raw)) best = c;
  }
  const pixels = best / metresPerPixel;
  const label =
    best >= 1000
      ? `${(best / 1000).toFixed(best >= 5000 ? 0 : 1)} km`
      : `${Math.round(best)} m`;
  return { metres: best, pixels, label };
}

export function featureCentroid(
  coordinates: Array<[number, number]>,
): { x: number; y: number } | null {
  if (!coordinates.length) return null;
  let sx = 0;
  let sy = 0;
  for (const [x, y] of coordinates) {
    sx += x;
    sy += y;
  }
  return { x: sx / coordinates.length, y: sy / coordinates.length };
}

export function colorForValue(z: number, zmin: number, zmax: number): string {
  const span = Math.max(zmax - zmin, 1e-9);
  const t = Math.max(0, Math.min(1, (z - zmin) / span));
  const r = Math.round(33 + t * (178 - 33));
  const g = Math.round(102 + (1 - Math.abs(t - 0.5) * 2) * 90);
  const b = Math.round(172 + (1 - t) * (33 - 172));
  return `rgb(${r},${g},${b})`;
}
