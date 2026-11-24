/**
 * Presentation helpers for assess conditioning_features (overburden / lineaments).
 * Never invents measurements or treats missing/NoData as zero.
 */

export type ConditioningLayer = {
  status: "available" | "nodata" | "unavailable" | string;
  value: number | null;
  unit?: string;
  reason?: string | null;
  /** Explicit: catalogue overlays must not claim Stage 2.5 v1 inference use. */
  used_in_inference?: boolean | null;
  source?: string | null;
};

export type GeologicalContextItem = {
  geo_id?: string;
  display_name?: string;
  kind?: string;
  structural_orientation_theme?: string | null;
  published_interpretation_themes?: string[];
  scientific_validation_status?: string;
  not_overburden_thickness?: boolean;
  not_confirmed_faults_or_fractures?: boolean;
  not_hazard_labels?: boolean;
  source?: string;
};

export type ConditioningFeatures = {
  schema_channel_count?: number | null;
  sample_policy?: string;
  sample_row?: number;
  sample_col?: number;
  notes?: string[];
  layers?: Record<string, ConditioningLayer>;
  geological_context?: GeologicalContextItem[];
  catalogue_overlay?: {
    queried?: boolean;
    used_in_inference?: boolean;
    notes?: string[];
    geological_context?: GeologicalContextItem[];
  } | null;
} | null | undefined;

export type ConditioningMetricView = {
  key: string;
  label: string;
  status: string;
  valueText: string;
  unit: string | null;
  reason: string | null;
  /** Whether SSRI can carry this channel in schema v2 stacks. */
  supportedInProduct: boolean;
  /** Whether this sample cell has a finite measurement. */
  availableAtLocation: boolean;
  /** Whether this channel was present and usable in the assessed stack (inference input). */
  usedInThisAssessment: boolean;
  usageNote: string;
};

export type ConditioningGroupView = {
  id: "overburden" | "lineaments";
  title: string;
  subtitle: string;
  metrics: ConditioningMetricView[];
};

const LAYER_META: Record<
  string,
  { group: "overburden" | "lineaments"; label: string; defaultUnit: string }
> = {
  overburden_thickness: {
    group: "overburden",
    label: "Thickness",
    defaultUnit: "m (thickness; not depth-to-interface)",
  },
  lineament_density: {
    group: "lineaments",
    label: "Density",
    defaultUnit: "derived density (training units)",
  },
  lineament_distance: {
    group: "lineaments",
    label: "Distance to nearest lineament",
    defaultUnit: "m (distance to nearest lineament segment)",
  },
};

const EXPECTED_KEYS = [
  "overburden_thickness",
  "lineament_density",
  "lineament_distance",
] as const;

function formatValue(layer: ConditioningLayer): string {
  if (layer.status === "available" && layer.value != null && Number.isFinite(layer.value)) {
    return Number.isInteger(layer.value)
      ? String(layer.value)
      : layer.value.toFixed(3);
  }
  if (layer.status === "nodata") {
    return "NoData (not treated as zero)";
  }
  if (layer.status === "unavailable") {
    return "Unavailable";
  }
  return layer.status || "Unknown";
}

function absentLayer(key: (typeof EXPECTED_KEYS)[number], reason: string): ConditioningLayer {
  return {
    status: "unavailable",
    value: null,
    unit: LAYER_META[key].defaultUnit,
    reason,
  };
}

/**
 * Build always-visible Overburden + Lineaments groups for the assess UI.
 * When the API omits conditioning_features, surfaces honest "not reported" states.
 */
export function buildConditioningGroups(
  conditioning: ConditioningFeatures,
): ConditioningGroupView[] {
  const layers = conditioning?.layers ?? {};
  const apiReported = Boolean(conditioning?.layers);

  const resolved: Record<string, ConditioningLayer> = {};
  for (const key of EXPECTED_KEYS) {
    const fromApi = layers[key];
    if (fromApi) {
      resolved[key] = fromApi;
    } else if (apiReported) {
      resolved[key] = absentLayer(
        key,
        "This layer was not included in the assessment conditioning payload.",
      );
    } else {
      resolved[key] = absentLayer(
        key,
        "The assessment API did not return conditioning_features. Re-run against an API that includes this field, or inspect the raw response.",
      );
    }
  }

  // Include any unexpected conditioning keys under the closest group.
  for (const [key, layer] of Object.entries(layers)) {
    if (key in resolved) continue;
    resolved[key] = layer;
  }

  const toMetric = (key: string, layer: ConditioningLayer): ConditioningMetricView => {
    const meta = LAYER_META[key];
    const availableAtLocation =
      layer.status === "available" && layer.value != null && Number.isFinite(layer.value);
    const usedInThisAssessment =
      layer.used_in_inference === true
        ? true
        : layer.used_in_inference === false
          ? false
          : availableAtLocation && layer.source !== "geological_catalogue";
    let usageNote: string;
    if (layer.used_in_inference === false || layer.source === "geological_catalogue") {
      usageNote =
        "Catalogue / overlay analytics only — not injected into the live 13-channel " +
        "Stage 2.5 inference tensor for this assessment.";
    } else if (usedInThisAssessment) {
      usageNote =
        "Present in this assessment feature stack at the sample cell. " +
        "It is a conditioning channel, not a hazard score.";
    } else if (layer.status === "nodata") {
      usageNote =
        "Channel exists in the stack but this cell is NoData — not treated as zero and " +
        "not used as a finite measurement for this location.";
    } else {
      usageNote =
        "Not included in this assessment's feature stack, so it was not used by this " +
        "prediction. Live AOI uses Stage 2.5 v1 (13 channels) unless you assess a schema-v2 offline stack.";
    }
    return {
      key,
      label: meta?.label ?? key,
      status: layer.status,
      valueText: formatValue(layer),
      unit:
        layer.status === "available"
          ? layer.unit ?? meta?.defaultUnit ?? null
          : layer.unit ?? meta?.defaultUnit ?? null,
      reason: layer.reason ?? null,
      supportedInProduct: Boolean(meta) || key.includes("overburden") || key.includes("lineament"),
      availableAtLocation,
      usedInThisAssessment,
      usageNote,
    };
  };

  const overburdenKeys = Object.keys(resolved).filter(
    (k) => LAYER_META[k]?.group === "overburden" || k.includes("overburden"),
  );
  const lineamentKeys = Object.keys(resolved).filter(
    (k) => LAYER_META[k]?.group === "lineaments" || k.includes("lineament"),
  );

  return [
    {
      id: "overburden",
      title: "Overburden thickness",
      subtitle:
        "Supported in SSRI schema v2. Thickness only when available. Depth-to-interface is not auto-converted and is never shown as zero when missing.",
      metrics: overburdenKeys.map((k) => toMetric(k, resolved[k])),
    },
    {
      id: "lineaments",
      title: "Lineaments",
      subtitle:
        "Supported in SSRI schema v2 (density and distance). Live AOI acquisition (v1) does not download lineaments.",
      metrics: lineamentKeys.map((k) => toMetric(k, resolved[k])),
    },
  ];
}

export function conditioningSampleCaption(
  conditioning: ConditioningFeatures,
): string | null {
  if (!conditioning) return null;
  const parts: string[] = [];
  if (conditioning.sample_policy) {
    parts.push(`Sample: ${conditioning.sample_policy}`);
  }
  if (
    conditioning.sample_row != null &&
    conditioning.sample_col != null &&
    Number.isFinite(conditioning.sample_row) &&
    Number.isFinite(conditioning.sample_col)
  ) {
    parts.push(`cell r${conditioning.sample_row} c${conditioning.sample_col}`);
  }
  if (conditioning.schema_channel_count != null) {
    parts.push(`${conditioning.schema_channel_count} channels in stack`);
  }
  return parts.length ? parts.join(" · ") : null;
}

/** Publication-guided magnetic / TMI geological context (not hazard labels). */
export function geologicalContextLines(
  conditioning: ConditioningFeatures,
): string[] {
  const items =
    conditioning?.geological_context ||
    conditioning?.catalogue_overlay?.geological_context ||
    [];
  const lines: string[] = [];
  for (const item of items) {
    const name = item.display_name || item.geo_id || "catalogue dataset";
    if (item.structural_orientation_theme) {
      lines.push(
        `${name}: ${item.structural_orientation_theme} (${item.scientific_validation_status || "NOT_VALIDATED"}; not confirmed faults).`,
      );
    }
    for (const theme of item.published_interpretation_themes || []) {
      if (theme === item.structural_orientation_theme) continue;
      lines.push(`${name}: ${theme}`);
    }
  }
  return lines;
}
