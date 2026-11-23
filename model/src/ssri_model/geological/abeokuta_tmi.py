"""Abeokuta Sheet 260 TMI survey — publication-guided metadata.

Publication reference:
  "Qualitative Interpretation of High Resolution Aeromagnetic Data of
   Abeokuta Metropolis for Geological Characterisation"

Authoritative column meanings (do not re-prompt):
  X = Easting, Y = Northing, Z = Total Magnetic Intensity (TMI)

CRS roles (publication-supported):
  - Source / original CSV CRS: EPSG:32632 (UTM Zone 32N)
  - Processing CRS: EPSG:32631 (UTM Zone 31N) — publication reprojected here
  - Display CRS: EPSG:4326 (WGS84)

An earlier owner declaration of EPSG:4326 for the raw CSV was a misunderstanding
of projected easting/northing values. That declaration is retained in metadata
history and superseded by the publication-supported source CRS.

Z is geophysical TMI — not elevation, overburden, depth, or a hazard label.
Must not be fed directly into the 13-channel Stage 2.5 model.
"""

from __future__ import annotations

from typing import Any

from ssri_model.geological.models import MEASUREMENT_TOTAL_MAGNETIC_INTENSITY

ABEOKUTA_TMI_PRESET_ID = "abeokuta_tmi_sheet260_utm"

# Publication geomagnetic / filter parameters (explicit, configurable overrides).
ABEOKUTA_PUBLICATION_MAGNETIC_PARAMS: dict[str, Any] = {
    "inclination_deg": 11.04,
    "declination_deg": 3.52,
    "average_igrf_nT": 32576.0,
    "gaussian_central_wavelength_m": 2000.0,
    "gaussian_std": 0.5,
    "source": (
        "Qualitative Interpretation of High Resolution Aeromagnetic Data of "
        "Abeokuta Metropolis for Geological Characterisation"
    ),
}

# Expected WGS84 extent after verified 32632→4326 transform (Sheet 260 block).
# Verified against repository CSV: lon≈[3.0, 3.5], lat≈[7.0, 7.5].
ABEOKUTA_EXPECTED_WGS84_BOUNDS = {
    "lon_min": 2.85,
    "lon_max": 3.65,
    "lat_min": 6.85,
    "lat_max": 7.65,
}

AUTHORITATIVE_ABEOKUTA_TMI: dict[str, Any] = {
    "preset_id": ABEOKUTA_TMI_PRESET_ID,
    "display_name": "Abeokuta Sheet 260 TMI (publication-guided)",
    "measurement_type": MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
    "measurement_description": (
        "Total Magnetic Intensity (TMI) aeromagnetic point survey (Sheet 260). "
        "Not elevation, terrain height, depth, overburden thickness, or a "
        "geological hazard score."
    ),
    # Catalogue ``crs`` = source CRS of the uploaded CSV coordinates.
    "crs": "EPSG:32632",
    "crs_name": "WGS 84 / UTM zone 32N",
    "source_crs": "EPSG:32632",
    "processing_crs": "EPSG:32631",
    "display_crs": "EPSG:4326",
    "working_crs": "EPSG:32631",
    "x_column": "X",
    "y_column": "Y",
    "z_column": "Z",
    "x_meaning": "easting",
    "y_meaning": "northing",
    "z_meaning": "total_magnetic_intensity",
    "units": "nT",
    "geographic_coverage": (
        "Abeokuta metropolis / Sheet 260 aeromagnetic survey area (Nigeria)"
    ),
    "scientific_validation_status": "NOT_VALIDATED",
    "stage25_channel_injection": False,
    "publication": ABEOKUTA_PUBLICATION_MAGNETIC_PARAMS["source"],
    "publication_magnetic_params": dict(ABEOKUTA_PUBLICATION_MAGNETIC_PARAMS),
    "crs_roles": {
        "original_owner_declaration": {
            "crs": "EPSG:4326",
            "x_meaning": "longitude",
            "y_meaning": "latitude",
            "status": "superseded",
            "note": (
                "Earlier declaration treated CSV X/Y as WGS84 lon/lat. "
                "Publication and coordinate magnitudes show projected UTM easting/northing."
            ),
        },
        "publication_source_crs": "EPSG:32632",
        "processing_crs": "EPSG:32631",
        "display_crs": "EPSG:4326",
        "publication_note": (
            "Publication states original data were transformed from UTM Zone 32N "
            "to UTM Zone 31N before geophysical processing."
        ),
    },
    "notes": (
        "Publication-guided Sheet 260 metadata. Apply without re-asking for column "
        "meanings. Verify EPSG:32632→32631→4326 before accepting the transform. "
        "Keep original CSV immutable. Do not inject into Stage 2.5."
    ),
}


def looks_like_abeokuta_filename(filename: str | None) -> bool:
    name = (filename or "").lower()
    return "abeokuta" in name or "sheet 260" in name or "sheet_260" in name


def apply_abeokuta_tmi_defaults(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge publication-guided Abeokuta TMI fields into a declare payload."""
    src = dict(body or {})
    preset = AUTHORITATIVE_ABEOKUTA_TMI
    out = dict(src)

    def _fill(key: str, value: Any) -> None:
        cur = out.get(key)
        if cur is None or (isinstance(cur, str) and not str(cur).strip()):
            out[key] = value

    _fill("measurement_type", preset["measurement_type"])
    _fill("measurement_description", preset["measurement_description"])
    _fill("crs", preset["crs"])
    _fill("working_crs", preset["working_crs"])
    _fill("x_column", preset["x_column"])
    _fill("y_column", preset["y_column"])
    _fill("z_column", preset["z_column"])
    _fill("units", preset["units"])
    _fill("geographic_coverage", preset["geographic_coverage"])

    prov = dict(out.get("provenance") or {})
    prov.setdefault("abeokuta_tmi_preset_id", ABEOKUTA_TMI_PRESET_ID)
    prov.setdefault("x_meaning", preset["x_meaning"])
    prov.setdefault("y_meaning", preset["y_meaning"])
    prov.setdefault("z_meaning", preset["z_meaning"])
    prov.setdefault("crs_name", preset["crs_name"])
    prov.setdefault("source_crs", preset["source_crs"])
    prov.setdefault("processing_crs", preset["processing_crs"])
    prov.setdefault("display_crs", preset["display_crs"])
    prov.setdefault("crs_roles", preset["crs_roles"])
    prov.setdefault(
        "publication_magnetic_params", dict(ABEOKUTA_PUBLICATION_MAGNETIC_PARAMS)
    )
    prov.setdefault(
        "stage25_note",
        "TMI catalogue asset only — not a Stage 2.5 13-channel feature stack.",
    )
    prov.setdefault("publication", preset["publication"])
    # Preserve history of the superseded geographic declaration.
    history = list(prov.get("crs_declaration_history") or [])
    if not any(h.get("status") == "superseded" for h in history):
        history.append(dict(preset["crs_roles"]["original_owner_declaration"]))
    history.append(
        {
            "crs": preset["source_crs"],
            "x_meaning": "easting",
            "y_meaning": "northing",
            "status": "publication_source",
            "at_role": "active_source_crs",
        }
    )
    prov["crs_declaration_history"] = history
    out["provenance"] = prov
    out["abeokuta_tmi_preset_applied"] = True
    return out


def authoritative_schema_block() -> dict[str, Any]:
    """Echo block for validation / inspect reports."""
    return {
        "preset_id": ABEOKUTA_TMI_PRESET_ID,
        "source_crs": AUTHORITATIVE_ABEOKUTA_TMI["source_crs"],
        "processing_crs": AUTHORITATIVE_ABEOKUTA_TMI["processing_crs"],
        "display_crs": AUTHORITATIVE_ABEOKUTA_TMI["display_crs"],
        "columns": {
            "X": "easting",
            "Y": "northing",
            "Z": "total_magnetic_intensity",
        },
        "scientific_validation_status": "NOT_VALIDATED",
        "stage25_injection_forbidden": True,
        "crs_roles": AUTHORITATIVE_ABEOKUTA_TMI["crs_roles"],
    }
