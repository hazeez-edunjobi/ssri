"""Canonical hazard-event sample schema for SSRI source/target catalogs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class DomainRole(str, Enum):
    """Whether a sample belongs to a labelled source or adaptation/eval target."""

    SOURCE = "source"
    TARGET = "target"


class PrdHazard(str, Enum):
    """PRD multi-task hazard vocabulary (canonical).

    Legacy engineering used ``sinkhole`` as the third segmentation class. That is
    **not** scientifically equivalent to liquefaction. Canonical PRD tasks are:

    - landslide
    - subsidence
    - liquefaction

    Legacy ``sinkhole`` remains available only via :class:`LegacyHazard` for
    compatibility with existing FeatureStack segmentation checkpoints.
    """

    LANDSLIDE = "landslide"
    SUBSIDENCE = "subsidence"
    LIQUEFACTION = "liquefaction"


class LegacyHazard(str, Enum):
    """Pre-PRD hazard class retained for checkpoint/API compatibility."""

    SINKHOLE = "sinkhole"


# Missing labels must remain explicit — never coerce to 0/negative.
MISSING_LABEL = None

PRD_HAZARD_ORDER: tuple[PrdHazard, ...] = (
    PrdHazard.LANDSLIDE,
    PrdHazard.SUBSIDENCE,
    PrdHazard.LIQUEFACTION,
)


@dataclass(frozen=True)
class HazardLabelSet:
    """Multi-task labels with explicit missingness.

    Each field is ``1`` (positive), ``0`` (confirmed negative / absence), or
    ``None`` (unknown / not annotated for this inventory).
    """

    landslide: int | None = MISSING_LABEL
    subsidence: int | None = MISSING_LABEL
    liquefaction: int | None = MISSING_LABEL

    def as_dict(self) -> dict[str, int | None]:
        return {
            "landslide": self.landslide,
            "subsidence": self.subsidence,
            "liquefaction": self.liquefaction,
        }

    def available_tasks(self) -> tuple[str, ...]:
        return tuple(
            name for name, value in self.as_dict().items() if value is not None
        )


@dataclass
class CatalogSample:
    """One georeferenced hazard observation or absence record."""

    sample_id: str
    latitude: float
    longitude: float
    dataset_name: str
    dataset_version: str
    source_domain: str
    domain_role: DomainRole
    hazard_type: str
    label: int | None
    labels: HazardLabelSet = field(default_factory=HazardLabelSet)
    geometry_wkt: str | None = None
    timestamp: str | None = None
    target_domain: str | None = None
    feature_availability: dict[str, bool] = field(default_factory=dict)
    quality_flags: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["domain_role"] = self.domain_role.value
        payload["labels"] = self.labels.as_dict()
        return payload


def validate_binary_or_missing(value: int | None, *, field_name: str) -> int | None:
    if value is None:
        return None
    if value not in (0, 1):
        raise ValueError(f"{field_name} must be 0, 1, or None; got {value!r}")
    return value
