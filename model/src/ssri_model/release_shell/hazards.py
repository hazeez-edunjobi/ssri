"""Hazard class registry (configuration, not a hard-coded switchboard).

This task keeps the three Stage 2.5 hazards. Adding a hazard later is a
registry entry plus labelled data — not a code fork.
"""

from __future__ import annotations

from dataclasses import dataclass

from ssri_model.ml.labels import LabelClass, label_class_names


@dataclass(frozen=True)
class HazardSpec:
    name: str
    class_id: int
    enabled_by_default: bool = True


def default_hazard_registry() -> tuple[HazardSpec, ...]:
    # Class ids follow Stage 2.5 order: subsidence=0, landslide=1, sinkhole=2.
    return tuple(
        HazardSpec(name=label.value, class_id=index)
        for index, label in enumerate(LabelClass)
    )


def hazard_names() -> tuple[str, ...]:
    return tuple(label_class_names())


def hazard_id_by_name() -> dict[str, int]:
    return {h.name: h.class_id for h in default_hazard_registry()}
