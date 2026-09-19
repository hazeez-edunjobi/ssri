"""Label definitions for SSRI geohazard prediction."""

from __future__ import annotations

from enum import Enum


class LabelClass(str, Enum):
    """Supported geohazard prediction targets."""

    SUBSIDENCE = "subsidence"
    LANDSLIDE = "landslide"
    SINKHOLE = "sinkhole"


def label_class_names() -> tuple[str, ...]:
    """Return supported label class names in enum definition order."""
    return tuple(label.value for label in LabelClass)


def is_supported_label(name: str) -> bool:
    """Return True when ``name`` is a supported label class."""
    return name in LabelClass._value2member_map_
