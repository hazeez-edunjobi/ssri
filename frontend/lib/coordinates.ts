/**
 * Coordinate entry and formatting for the assessment map.
 *
 * The map is Web Mercator and always deals in WGS84 latitude/longitude
 * (`[longitude, latitude]` in MapLibre). These helpers keep a single, tested
 * source of truth for parsing operator input, validating ranges, formatting the
 * 6-decimal round trip, and the soft coverage hint — so the UI never guesses a
 * projection.
 */

/** Decimal places kept for the enter → plot → read-back round trip. */
export const COORD_DECIMALS = 6;

/** Soft guidance for the Lagos geophysics clip (~2.5–4.5°E, ~5.5–7.5°N). */
export const COVERAGE_HINT = {
  minLon: 2.5,
  maxLon: 4.5,
  minLat: 5.5,
  maxLat: 7.5,
} as const;

export type ParsedCoordinates =
  | { ok: true; latitude: number; longitude: number }
  | { ok: false; error: string };

/**
 * Parse operator-entered latitude/longitude text.
 *
 * Latitude comes first, matching the labelled inputs. Returns a plain-language
 * message for empty, non-numeric, or out-of-range input.
 */
export function parseLatLon(
  latitudeText: string,
  longitudeText: string,
): ParsedCoordinates {
  const latText = latitudeText.trim();
  const lonText = longitudeText.trim();
  if (latText === "" || lonText === "") {
    return { ok: false, error: "Enter numeric latitude and longitude." };
  }
  const latitude = Number(latText);
  const longitude = Number(lonText);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return { ok: false, error: "Enter numeric latitude and longitude." };
  }
  if (latitude < -90 || latitude > 90) {
    return { ok: false, error: "Latitude must be between -90 and 90." };
  }
  if (longitude < -180 || longitude > 180) {
    return { ok: false, error: "Longitude must be between -180 and 180." };
  }
  return { ok: true, latitude, longitude };
}

/** Format a coordinate pair as "lat, lon" with a fixed number of decimals. */
export function formatLatLon(
  latitude: number,
  longitude: number,
  decimals: number = COORD_DECIMALS,
): string {
  return `${latitude.toFixed(decimals)}, ${longitude.toFixed(decimals)}`;
}

export function isWithinCoverage(latitude: number, longitude: number): boolean {
  return (
    longitude >= COVERAGE_HINT.minLon &&
    longitude <= COVERAGE_HINT.maxLon &&
    latitude >= COVERAGE_HINT.minLat &&
    latitude <= COVERAGE_HINT.maxLat
  );
}

/** Soft warning shown when a point falls outside the geophysics clip. */
export function coverageMessage(): string {
  return (
    `Coordinates are outside the Lagos geophysics coverage ` +
    `(~${COVERAGE_HINT.minLon}–${COVERAGE_HINT.maxLon}°E, ` +
    `${COVERAGE_HINT.minLat}–${COVERAGE_HINT.maxLat}°N). Live gravity/magnetics ` +
    `may be empty outside this clip.`
  );
}

export type RegionExtent = {
  lat_min: number;
  lat_max: number;
  lon_min: number;
  lon_max: number;
};

/** Degrees of padding applied around the stored extent. Mirrors the backend. */
export const REGION_PAD_DEG = 0.5;

/**
 * Whether a WGS84 point falls inside a stored training region extent.
 *
 * Uses the same 0.5° pad as the backend ``point_in_training_region`` so the map
 * warning matches the ``outside_training_region`` assess gate exactly.
 */
export function pointInRegion(
  latitude: number,
  longitude: number,
  extent: RegionExtent,
  padDeg: number = REGION_PAD_DEG,
): boolean {
  return (
    latitude >= extent.lat_min - padDeg &&
    latitude <= extent.lat_max + padDeg &&
    longitude >= extent.lon_min - padDeg &&
    longitude <= extent.lon_max + padDeg
  );
}
