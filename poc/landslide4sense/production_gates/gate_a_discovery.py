"""Gate A — independent geographic dataset discovery (no fabricated labels)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "production_gates" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

L4S_STUDY_AREAS = ["Iburi (JP)", "Kodagu (IN)", "Gorkha (NP)", "Taiwan"]

CANDIDATES = [
    {
        "name": "Landslide4Sense validation HDF5",
        "path_or_url": "poc/landslide4sense/data/validation",
        "georeferenced": False,
        "labelled": True,
        "bands": "14 L4S packaged",
        "independent_of_l4s_train_geo": False,
        "usable_for_gate_a": False,
        "reason": "Competition chips; no CRS; same geographic family as training (not independent AOI validation).",
    },
    {
        "name": "SSRI usgs_landslide_featurestacks v3",
        "path_or_url": "data/datasets/usgs_landslide_featurestacks/v3",
        "georeferenced": True,
        "labelled": "point/pseudo-absence inventory derived",
        "bands": "13 SSRI CHANNEL_NAMES",
        "independent_of_l4s_train_geo": True,
        "usable_for_gate_a": False,
        "reason": "Wrong feature contract (13-ch SSRI). Cannot map into DeepSlide 14-band without inventing S2 bands.",
    },
    {
        "name": "Hokkaido / Iburi landslide dataset (karstCand)",
        "path_or_url": "https://github.com/karstCand/HokkaidoLandslide_dataset",
        "georeferenced": True,
        "labelled": True,
        "bands": "Sentinel-2 + DEM (repo documents S2+DEM; not verified locally as full B1–B12+slope)",
        "independent_of_l4s_train_geo": False,
        "usable_for_gate_a": False,
        "reason": "Iburi is an L4S study area — spatial leakage vs Landslide4Sense training geography.",
    },
    {
        "name": "Nepal U-Net scars (Zenodo 3688363)",
        "path_or_url": "https://zenodo.org/records/3688363",
        "georeferenced": True,
        "labelled": True,
        "bands": "8-bit RGB GeoTIFF",
        "independent_of_l4s_train_geo": "partial (Nepal; Gorkha also L4S — geographic risk)",
        "usable_for_gate_a": False,
        "reason": "RGB only; not 14-band S2+terrain package for DeepSlide.",
    },
    {
        "name": "Sen12Landslides (paulhoehn/Sen12Landslides)",
        "path_or_url": "https://huggingface.co/datasets/paulhoehn/Sen12Landslides",
        "georeferenced": True,
        "labelled": True,
        "bands": "S2 B02–B12 (10 bands) + DEM; no B01/B10 as in L4S; slope not native",
        "independent_of_l4s_train_geo": "partial (multi-region incl. Italy etc.; overlap with L4S Asia areas unknown without audit)",
        "usable_for_gate_a": False,
        "reason": (
            "Band set incompatible without fabricating missing L4S channels; "
            "full download is multi-100GB; not used in this gate to avoid inventing bands or unpaid massive transfer."
        ),
    },
    {
        "name": "USGS Landslide Inventories v3 (vector)",
        "path_or_url": "https://www.usgs.gov/data/landslide-inventories-across-united-states-ver-30-february-2025",
        "georeferenced": True,
        "labelled": "vector inventory (points/polygons), not raster scars co-registered to S2",
        "bands": "none (inventory only)",
        "independent_of_l4s_train_geo": True,
        "usable_for_gate_a": False,
        "reason": (
            "Would require a new approved construction pipeline: STAC 14-band stacks + "
            "defensible rasterization/temporal alignment. Not available as a ready DeepSlide eval set."
        ),
    },
]

report = {
    "gate": "A",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "l4s_known_study_areas": L4S_STUDY_AREAS,
    "requirement": (
        "Georeferenced landslide/non-landslide labels + constructible/compatible "
        "S2 B1–B12 + slope + DEM inputs, geographically independent of L4S train/val chips, "
        "with spatial-block splits."
    ),
    "candidates_reviewed": CANDIDATES,
    "verdict": "BLOCKED",
    "missing_requirement": (
        "A ready, free, labelled, georeferenced evaluation corpus whose imagery matches the "
        "DeepSlide 14-band L4S contract (B1–B12 + slope + DEM) and whose geography is "
        "independent of Landslide4Sense study areas — OR an approved, completed construction "
        "of such a corpus from USGS (or similar) inventories + STAC with documented "
        "temporal/spatial alignment QA."
    ),
    "not_done": [
        "Did not manufacture labels",
        "Did not treat L4S chip metrics as independent geographic validation",
        "Did not treat Iburi STAC visual coherence as scientific validation",
        "Did not download multi-100GB Sen12Landslides or invent missing bands",
    ],
}

(OUT / "gate_a_discovery.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"verdict": report["verdict"], "n_candidates": len(CANDIDATES)}, indent=2))
