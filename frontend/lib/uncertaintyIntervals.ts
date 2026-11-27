export type IntervalPresentation =
  | { kind: "available"; ci80: [number, number]; ci95: [number, number] }
  | { kind: "unavailable"; reason: string };

type IntervalProfile = {
  credible_interval_80?: [number, number] | null;
  credible_interval_95?: [number, number] | null;
  uncertainty_intervals_available?: boolean;
  uncertainty_unavailable_reason?: string | null;
};

/**
 * Decide how hazard confidence intervals should be shown.
 * Zero-width bands must never be rendered as real uncertainty.
 */
export function presentHazardIntervals(profile: IntervalProfile): IntervalPresentation {
  if (profile.uncertainty_intervals_available === false) {
    return {
      kind: "unavailable",
      reason:
        profile.uncertainty_unavailable_reason?.trim() ||
        "Credible intervals are unavailable for this checkpoint.",
    };
  }
  const ci80 = profile.credible_interval_80;
  const ci95 = profile.credible_interval_95;
  if (
    !ci80 ||
    !ci95 ||
    ci80.length !== 2 ||
    ci95.length !== 2 ||
    !Number.isFinite(ci80[0]) ||
    !Number.isFinite(ci80[1]) ||
    !Number.isFinite(ci95[0]) ||
    !Number.isFinite(ci95[1])
  ) {
    return {
      kind: "unavailable",
      reason: "Credible intervals were not provided.",
    };
  }
  if (ci80[0] === ci80[1] && ci95[0] === ci95[1]) {
    return {
      kind: "unavailable",
      reason: "Zero-width MC bands are not shown as confidence intervals.",
    };
  }
  return { kind: "available", ci80: [ci80[0], ci80[1]], ci95: [ci95[0], ci95[1]] };
}
