"""SSRI data ingestion for source/target hazard catalogs."""

from ssri_model.ingestion.schema import (
    PRD_HAZARD_ORDER,
    CatalogSample,
    DomainRole,
    HazardLabelSet,
    LegacyHazard,
    PrdHazard,
    validate_binary_or_missing,
)
from ssri_model.ingestion.usgs_landslide import (
    USGS_DATASET_NAME,
    USGS_DATASET_VERSION,
    USGS_DOI,
    USGS_LICENSE,
    USGS_SCIENCEBASE_ITEM,
    convert_usgs_csv_row,
    ingest_usgs_csv,
    write_catalog_jsonl,
)

__all__ = [
    "PRD_HAZARD_ORDER",
    "CatalogSample",
    "DomainRole",
    "HazardLabelSet",
    "LegacyHazard",
    "PrdHazard",
    "USGS_DATASET_NAME",
    "USGS_DATASET_VERSION",
    "USGS_DOI",
    "USGS_LICENSE",
    "USGS_SCIENCEBASE_ITEM",
    "convert_usgs_csv_row",
    "ingest_usgs_csv",
    "validate_binary_or_missing",
    "write_catalog_jsonl",
]
