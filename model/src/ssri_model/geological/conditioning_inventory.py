"""Conditioning-factor availability and provenance catalogue (honest states)."""

from __future__ import annotations

from typing import Any

FACTORS: list[dict[str, Any]] = [
    {
        "id": "elevation",
        "name": "Elevation",
        "implemented": True,
        "in_stage25_channels": True,
        "channel_hint": "dem / topography stack",
        "used_in_inference": True,
        "typical_source": "DEM acquisition for Stage 2.5 feature stacks",
        "scientific_notes": "Terrain elevation; not overburden thickness.",
    },
    {
        "id": "slope",
        "name": "Slope",
        "implemented": True,
        "in_stage25_channels": True,
        "used_in_inference": True,
        "typical_source": "Derived from DEM",
        "scientific_notes": "Primary landslide conditioning factor.",
    },
    {
        "id": "terrain_derivatives",
        "name": "Terrain derivatives",
        "implemented": True,
        "in_stage25_channels": True,
        "used_in_inference": True,
        "typical_source": "DEM derivatives (aspect, curvature, TWI, etc.)",
        "scientific_notes": "See CHANNEL_NAMES / feature engineering docs.",
    },
    {
        "id": "magnetics_emag2",
        "name": "Regional magnetics (EMAG2 Stage 2.5 channel)",
        "implemented": True,
        "in_stage25_channels": True,
        "used_in_inference": True,
        "typical_source": "EMAG2-derived Stage 2.5 magnetics channel",
        "scientific_notes": (
            "Distinct from client TMI catalogue sheets. Do not confuse with "
            "Abeokuta sheet-260 TMI processing products."
        ),
    },
    {
        "id": "client_tmi",
        "name": "Client / catalogue TMI (Abeokuta sheet 260)",
        "implemented": True,
        "in_stage25_channels": False,
        "used_in_inference": False,
        "typical_source": "Geological catalogue total_magnetic_intensity CSVs",
        "scientific_notes": (
            "Z is nT intensity, never elevation or overburden. Context + magnetic "
            "derivatives + candidate lineaments only."
        ),
    },
    {
        "id": "lineament_density",
        "name": "Lineament density",
        "implemented": True,
        "in_stage25_channels": False,
        "used_in_inference": False,
        "typical_source": (
            "Uploaded vector lineaments or candidate magnetic lineament extraction"
        ),
        "scientific_notes": (
            "Candidates ≠ confirmed faults. Schema-v2 offline stacks may include "
            "density; live 13-ch assess does not inject it."
        ),
    },
    {
        "id": "lineament_distance",
        "name": "Distance to lineaments",
        "implemented": True,
        "in_stage25_channels": False,
        "used_in_inference": False,
        "typical_source": "Same as lineament_density",
        "scientific_notes": "Metres in working CRS; unavailable when no vectors cover AOI.",
    },
    {
        "id": "overburden_thickness",
        "name": "Overburden thickness",
        "implemented": True,
        "in_stage25_channels": False,
        "used_in_inference": False,
        "typical_source": "Point-grid CSV with measurement_type=overburden_thickness",
        "scientific_notes": (
            "Never aliased from depth_to_bedrock or TMI Z. Abeokuta currently has "
            "no thickness inventory."
        ),
    },
    {
        "id": "lithology",
        "name": "Lithology",
        "implemented": False,
        "in_stage25_channels": False,
        "used_in_inference": False,
        "typical_source": None,
        "scientific_notes": "Not implemented as a catalogue layer in SSRI yet.",
    },
    {
        "id": "geological_boundaries",
        "name": "Geological boundaries",
        "implemented": False,
        "in_stage25_channels": False,
        "used_in_inference": False,
        "typical_source": None,
        "scientific_notes": "Not implemented.",
    },
    {
        "id": "confirmed_faults_fractures",
        "name": "Confirmed faults and fractures",
        "implemented": False,
        "in_stage25_channels": False,
        "used_in_inference": False,
        "typical_source": "Would require authoritative structural GIS",
        "scientific_notes": (
            "Magnetic candidate lineaments must not be labelled as confirmed faults."
        ),
    },
    {
        "id": "soil_properties",
        "name": "Soil properties",
        "implemented": False,
        "in_stage25_channels": False,
        "used_in_inference": False,
        "typical_source": None,
        "scientific_notes": "Not implemented as a dedicated conditioning layer.",
    },
    {
        "id": "groundwater",
        "name": "Groundwater conditions",
        "implemented": False,
        "in_stage25_channels": False,
        "used_in_inference": False,
        "typical_source": None,
        "scientific_notes": "Not implemented.",
    },
]


def conditioning_factor_inventory() -> dict[str, Any]:
    implemented = [f for f in FACTORS if f["implemented"]]
    missing = [f for f in FACTORS if not f["implemented"]]
    inference = [f for f in FACTORS if f.get("used_in_inference")]
    context_only = [
        f for f in FACTORS if f["implemented"] and not f.get("used_in_inference")
    ]
    return {
        "scientific_validation_status": "NOT_VALIDATED",
        "factors": FACTORS,
        "summary": {
            "implemented_count": len(implemented),
            "missing_count": len(missing),
            "used_in_live_inference_count": len(inference),
            "context_or_offline_only_count": len(context_only),
        },
        "live_assess_rule": (
            "Live map assess uses the Stage 2.5 13-channel contract. Catalogue "
            "overlays remain used_in_inference=false unless a separately approved "
            "model integration exists."
        ),
    }
