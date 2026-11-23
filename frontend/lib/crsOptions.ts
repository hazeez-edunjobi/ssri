/**
 * Recognisable EPSG choices for geological upload / declare.
 * Does not invent a default CRS for undeclared data — the blank option remains.
 */

export type CrsOption = {
  code: string;
  label: string;
  roleHint: "geographic" | "projected" | "other";
};

export const COMMON_CRS_OPTIONS: CrsOption[] = [
  {
    code: "EPSG:4326",
    label: "WGS 84 (geographic lon/lat)",
    roleHint: "geographic",
  },
  {
    code: "EPSG:3857",
    label: "Web Mercator (projected metres)",
    roleHint: "projected",
  },
  {
    code: "EPSG:32631",
    label: "WGS 84 / UTM zone 31N",
    roleHint: "projected",
  },
  {
    code: "EPSG:32632",
    label: "WGS 84 / UTM zone 32N (Abeokuta Sheet 260 source)",
    roleHint: "projected",
  },
  {
    code: "EPSG:26331",
    label: "Minna / UTM zone 31N",
    roleHint: "projected",
  },
  {
    code: "EPSG:26332",
    label: "Minna / UTM zone 32N",
    roleHint: "projected",
  },
];

export function crsOptionLabel(code: string): string {
  const hit = COMMON_CRS_OPTIONS.find((o) => o.code === code);
  return hit ? `${hit.code} — ${hit.label}` : code;
}
