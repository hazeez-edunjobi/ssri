/**
 * Canonical client-facing capability catalogue for SSRI Stage 2.5.
 * Keep hazards and geological conditioning separate.
 */

/** Stage 2.5 ground-risk hazard identifiers (live assess classes). */
export type HazardId = "subsidence" | "landslide" | "sinkhole";

/** Geological conditioning / catalogue identifiers — never hazards. */
export type GeologicalCapabilityId =
  | "overburden_thickness"
  | "lineament_density"
  | "lineament_distance"
  | "geological_ingestion";

export type HazardCatalogueEntry = {
  id: HazardId;
  name: string;
  detail: string;
};

export type GeologicalCatalogueEntry = {
  id: GeologicalCapabilityId;
  name: string;
  status: string;
};

export const PRODUCT_HAZARDS: readonly HazardCatalogueEntry[] = [
  {
    id: "subsidence",
    name: "Subsidence",
    detail: "Ground-settling susceptibility ranking",
  },
  {
    id: "landslide",
    name: "Landslide",
    detail: "Slope-movement susceptibility ranking",
  },
  {
    id: "sinkhole",
    name: "Sinkhole",
    detail: "Collapse / sinking-ground susceptibility ranking",
  },
];

export const PRODUCT_GEOLOGICAL: readonly GeologicalCatalogueEntry[] = [
  {
    id: "overburden_thickness",
    name: "Overburden thickness",
    status: "Offline conditioning supported · Live inference integration pending",
  },
  {
    id: "lineament_density",
    name: "Lineament density",
    status: "Available for geological data management · Live inference integration pending",
  },
  {
    id: "lineament_distance",
    name: "Distance to lineaments",
    status: "Available for geological data management · Live inference integration pending",
  },
  {
    id: "geological_ingestion",
    name: "Geological dataset ingestion and validation",
    status: "Catalogue, upload, validate, and activate datasets",
  },
];

export const PRODUCT_SAFEGUARDS = [
  "Model compatibility checks (13-channel Stage 2.5 live contract)",
  "Assessment confidence and uncertainty where implemented",
  "Geological data validation in the catalogue and release shell",
  "Clear distinction between offline conditioning and live inference",
] as const;

export const PRODUCT_HAZARD_IDS: readonly HazardId[] = PRODUCT_HAZARDS.map(
  (entry) => entry.id,
);

export const PRODUCT_GEOLOGICAL_IDS: readonly GeologicalCapabilityId[] =
  PRODUCT_GEOLOGICAL.map((entry) => entry.id);

export function isHazardId(value: string): value is HazardId {
  for (const id of PRODUCT_HAZARD_IDS) {
    if (id === value) return true;
  }
  return false;
}

export function isGeologicalCapabilityId(
  value: string,
): value is GeologicalCapabilityId {
  for (const id of PRODUCT_GEOLOGICAL_IDS) {
    if (id === value) return true;
  }
  return false;
}

/**
 * Merge a backend/registry hazard name list with the canonical Stage 2.5 set.
 *
 * - Always keeps subsidence, landslide, and sinkhole.
 * - Deduplicates while preserving first-seen order after the canonical prefix.
 * - Ignores geological conditioning identifiers (they are not hazards).
 * - Appends unknown non-geological names (backend may extend the registry).
 * - Does not mutate the input array.
 */
export function mergeHazardNames(names: readonly string[]): string[] {
  const ordered: string[] = [...PRODUCT_HAZARD_IDS];
  for (const name of names) {
    if (isGeologicalCapabilityId(name)) continue;
    if (ordered.includes(name)) continue;
    ordered.push(name);
  }
  for (const required of PRODUCT_HAZARD_IDS) {
    if (!ordered.includes(required)) {
      ordered.push(required);
    }
  }
  return ordered;
}
