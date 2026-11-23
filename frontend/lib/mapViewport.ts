/**
 * Shared map viewport helpers for SSRI assessment and catalogue maps.
 *
 * Bounds are always WGS84 [west, south, east, north] = [minLon, minLat, maxLon, maxLat].
 * Never invent a location for projected CRS data without a verified transform.
 */

/** Neutral product starting view: SW Nigeria covering Lagos + Abeokuta survey area. */
export const DEFAULT_PRODUCT_BOUNDS: [number, number, number, number] = [
  2.7, 6.2, 4.0, 7.7,
];

export const DEFAULT_PRODUCT_CENTER: [number, number] = [3.35, 6.95];
export const DEFAULT_PRODUCT_ZOOM = 8.5;

export const MAP_MIN_ZOOM = 5;
export const MAP_MAX_ZOOM = 16;

export type LngLatBoundsTuple = [[number, number], [number, number]];

export function isValidWgs84Bounds(
  bounds: [number, number, number, number] | null | undefined,
): bounds is [number, number, number, number] {
  if (!bounds || bounds.length !== 4) return false;
  const [w, s, e, n] = bounds;
  if (![w, s, e, n].every((v) => Number.isFinite(v))) return false;
  if (w < -180 || e > 180 || s < -90 || n > 90) return false;
  if (e <= w || n <= s) return false;
  // Reject near-global extents that imply failed CRS / empty world fit.
  if (e - w > 40 || n - s > 40) return false;
  return true;
}

/** Merge one or more WGS84 boxes; returns null if none valid. */
export function unionBounds(
  boxes: Array<[number, number, number, number] | null | undefined>,
): [number, number, number, number] | null {
  let w = Infinity;
  let s = Infinity;
  let e = -Infinity;
  let n = -Infinity;
  let any = false;
  for (const b of boxes) {
    if (!isValidWgs84Bounds(b)) continue;
    any = true;
    w = Math.min(w, b[0]);
    s = Math.min(s, b[1]);
    e = Math.max(e, b[2]);
    n = Math.max(n, b[3]);
  }
  if (!any) return null;
  const out: [number, number, number, number] = [w, s, e, n];
  return isValidWgs84Bounds(out) ? out : null;
}

export function boundsFromRing(
  ring: Array<[number, number]>,
): [number, number, number, number] | null {
  if (!ring.length) return null;
  let w = ring[0][0];
  let s = ring[0][1];
  let e = ring[0][0];
  let n = ring[0][1];
  for (const [lng, lat] of ring) {
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) continue;
    w = Math.min(w, lng);
    s = Math.min(s, lat);
    e = Math.max(e, lng);
    n = Math.max(n, lat);
  }
  const out: [number, number, number, number] = [w, s, e, n];
  return isValidWgs84Bounds(out) ? out : null;
}

export function toFitBounds(
  bounds: [number, number, number, number],
): LngLatBoundsTuple {
  return [
    [bounds[0], bounds[1]],
    [bounds[2], bounds[3]],
  ];
}

export type FitOptions = {
  padding?: number;
  maxZoom?: number;
  duration?: number;
};

/** Fit a MapLibre map to WGS84 bounds; no-op if bounds invalid. */
export function fitMapToWgs84Bounds(
  map: { fitBounds: (b: LngLatBoundsTuple, o?: object) => void },
  bounds: [number, number, number, number] | null | undefined,
  options: FitOptions = {},
): boolean {
  if (!isValidWgs84Bounds(bounds)) return false;
  map.fitBounds(toFitBounds(bounds), {
    padding: options.padding ?? 48,
    maxZoom: options.maxZoom ?? 12,
    duration: options.duration ?? 600,
  });
  return true;
}

/**
 * Geographic CRS family only — projected coverage_bbox must not be plotted as lon/lat.
 */
export function displayBboxFromDataset(dataset: {
  crs?: string | null;
  coverage_bbox?: number[] | null;
  display_bbox_wgs84?: number[] | null;
  provenance?: Record<string, unknown> | null;
}): [number, number, number, number] | null {
  const explicit = dataset.display_bbox_wgs84;
  if (
    Array.isArray(explicit) &&
    explicit.length === 4 &&
    isValidWgs84Bounds(explicit as [number, number, number, number])
  ) {
    return explicit as [number, number, number, number];
  }
  const fromProv = dataset.provenance?.display_bbox_wgs84;
  if (
    Array.isArray(fromProv) &&
    fromProv.length === 4 &&
    isValidWgs84Bounds(fromProv as [number, number, number, number])
  ) {
    return fromProv as [number, number, number, number];
  }
  const crs = (dataset.crs || "").toUpperCase();
  const geographic =
    crs.includes("4326") || crs === "WGS84" || crs.includes("CRS84");
  const box = dataset.coverage_bbox;
  if (
    geographic &&
    Array.isArray(box) &&
    box.length === 4 &&
    isValidWgs84Bounds(box as [number, number, number, number])
  ) {
    return box as [number, number, number, number];
  }
  return null;
}
