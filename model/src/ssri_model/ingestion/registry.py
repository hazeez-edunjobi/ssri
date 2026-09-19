"""Registry of PRD source/target datasets and acquisition status."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DatasetRegistryEntry:
    """Machine-readable status for one PRD-required inventory."""

    dataset_id: str
    provider: str
    role: str  # source | target
    hazards: tuple[str, ...]
    url: str
    license: str
    status: str
    blocker: str | None = None
    local_path: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DATASET_REGISTRY: tuple[DatasetRegistryEntry, ...] = (
    DatasetRegistryEntry(
        dataset_id="usgs_landslide_inventories_us_v3",
        provider="USGS",
        role="source",
        hazards=("landslide",),
        url="https://doi.org/10.5066/P14AJF8I",
        license="CC0-1.0",
        status="INGESTED",
        local_path="data/catalogs/usgs_landslide_v3/",
        notes=(
            "Manual ScienceBase CSV placed on disk; ingested to catalog.jsonl "
            "(251344 samples, confidence>=5). FeatureStacks: "
            "data/datasets/usgs_landslide_featurestacks/v2 (80 samples)."
        ),
    ),
    DatasetRegistryEntry(
        dataset_id="bgs_mass_movement_uk",
        provider="British Geological Survey",
        role="source",
        hazards=("landslide", "subsidence"),
        url="https://www.bgs.ac.uk/datasets/",
        license="UNKNOWN_REQUIRES_REVIEW",
        status="BLOCKED",
        blocker=(
            "BGS national mass-movement / GeoSure products typically require "
            "account registration and license acceptance; automated anonymous "
            "download is not available. Manual acquisition + license review required."
        ),
    ),
    DatasetRegistryEntry(
        dataset_id="iffi_italian_landslide_inventory",
        provider="ISPRA / IFFI",
        role="source",
        hazards=("landslide",),
        url="https://www.projectiffi.isprambiente.it/",
        license="UNKNOWN_REQUIRES_REVIEW",
        status="BLOCKED",
        blocker=(
            "IFFI access is portal-mediated; bulk redistribution terms must be "
            "confirmed before automated ingest. No anonymous bulk dump wired yet."
        ),
    ),
    DatasetRegistryEntry(
        dataset_id="uglc_global_landslide_catalogue",
        provider="UGLC / Zenodo (Mancino et al.)",
        role="target",
        hazards=("landslide",),
        url="https://doi.org/10.5281/zenodo.18643456",
        license="OPEN_ZENODO_CONFIRM_FILE_TERMS",
        status="BLOCKED",
        blocker=(
            "Zenodo API HTTP 504 from this environment (2026-09-09). "
            "Manual CSV download + `python -m ssri_model.scripts.ingest_uglc_africa --local-csv`."
        ),
        notes=(
            "Primary African/Nigerian labelled target candidate. "
            "See docs/AFRICAN_TARGET_DATA_STATUS.md."
        ),
    ),
    DatasetRegistryEntry(
        dataset_id="nasa_coolr_global_landslide_catalog",
        provider="NASA GSFC / COOLR",
        role="target",
        hazards=("landslide",),
        url="https://maps.nccs.nasa.gov/resilience/landslides.html",
        license="CHECK_PROVIDER_TERMS",
        status="CANDIDATE",
        blocker=(
            "Automated FeatureServer query to "
            "gis.earthdata.nasa.gov/.../COOLR_Events_Points returned HTTP 404 "
            "(2026-09-09). Manual GLC/COOLR export or alternate endpoint required."
        ),
        notes=(
            "Global Landslide Catalog / COOLR is a candidate African-subset "
            "transfer evaluation source. Ingest script scaffold: "
            "ssri_model.scripts.ingest_coolr_africa"
        ),
    ),
    DatasetRegistryEntry(
        dataset_id="lagos_insar_ohenhen_shirzaei",
        provider="Figshare DOI 10.7294/19738957",
        role="target",
        hazards=("subsidence",),
        url="https://doi.org/10.7294/19738957",
        license="CC0-1.0 (dataset v1; confirm version)",
        status="BENCHMARK_ONLY",
        blocker=(
            "Qualified as BENCHMARK-ONLY continuous VLM / risk codes — not SSRI "
            "multi-class {landslide,subsidence,liquefaction} label.tif without an "
            "approved scientific mapping protocol."
        ),
    ),
)


def registry_as_dicts() -> list[dict[str, Any]]:
    return [entry.to_dict() for entry in DATASET_REGISTRY]
