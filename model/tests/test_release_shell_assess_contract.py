"""Assess contract: not_available / outside_training_region / no score leaks."""

from __future__ import annotations

from ssri_model.release_shell.assess_contract import resolve_hazard_entry
from ssri_model.release_shell.gates import (
    STATUS_EVALUATED,
    STATUS_NO_SKILL,
    STATUS_NOT_AVAILABLE,
    STATUS_OUTSIDE_REGION,
    STATUS_UNCONFIRMED,
    aggregate_seed_gates,
)


def _meta(**hazard_overrides):
    base = {
        "training_region": {
            "blocks": ["35_-120", "40_-120"],
            "extent": {
                "lat_min": 35.0,
                "lat_max": 42.0,
                "lon_min": -122.0,
                "lon_max": -118.0,
            },
        },
        "hazards": {
            "landslide": {
                "disabled_at_validation": False,
                "has_positive_labels": True,
                "gate_status": STATUS_EVALUATED,
            },
            "subsidence": {
                "disabled_at_validation": True,
                "has_positive_labels": False,
                "gate_status": "insufficient labelled data",
                "reason": "insufficient labelled data",
                "status": "DISABLED",
            },
            "sinkhole": {
                "disabled_at_validation": False,
                "has_positive_labels": False,
                "gate_status": STATUS_NO_SKILL,
            },
        },
    }
    base["hazards"].update(hazard_overrides)
    return base


def test_disabled_hazard_not_available_no_score():
    entry = resolve_hazard_entry(
        "subsidence",
        shell_meta=_meta(),
        query_lat=37.0,
        query_lon=-120.0,
        raw_score=0.9,
    )
    assert entry["status"] == STATUS_NOT_AVAILABLE
    assert entry["score"] is None
    assert "DISABLED" in entry["reason"] or "insufficient" in entry["reason"].lower()


def test_no_positive_labels_not_available():
    entry = resolve_hazard_entry(
        "sinkhole",
        shell_meta=_meta(),
        query_lat=37.0,
        query_lon=-120.0,
        raw_score=0.8,
    )
    assert entry["status"] == STATUS_NOT_AVAILABLE
    assert entry["score"] is None
    assert "positive" in entry["reason"].lower()


def test_failed_gate_floor_not_available():
    meta = _meta(
        landslide={
            "disabled_at_validation": False,
            "has_positive_labels": True,
            "gate_status": STATUS_NO_SKILL,
        }
    )
    entry = resolve_hazard_entry(
        "landslide",
        shell_meta=meta,
        query_lat=37.0,
        query_lon=-120.0,
        raw_score=0.77,
    )
    assert entry["status"] == STATUS_NOT_AVAILABLE
    assert entry["score"] is None
    assert entry["gate_status"] == STATUS_NO_SKILL


def test_unconfirmed_seeds_not_available():
    meta = _meta(
        landslide={
            "disabled_at_validation": False,
            "has_positive_labels": True,
            "gate_status": STATUS_UNCONFIRMED,
        }
    )
    entry = resolve_hazard_entry(
        "landslide",
        shell_meta=meta,
        query_lat=37.0,
        query_lon=-120.0,
        raw_score=0.5,
    )
    assert entry["status"] == STATUS_NOT_AVAILABLE
    assert entry["score"] is None


def test_outside_training_region():
    entry = resolve_hazard_entry(
        "landslide",
        shell_meta=_meta(),
        query_lat=10.0,
        query_lon=10.0,
        raw_score=0.9,
    )
    assert entry["status"] == STATUS_OUTSIDE_REGION
    assert entry["score"] is None


def test_evaluated_inside_region_returns_score():
    entry = resolve_hazard_entry(
        "landslide",
        shell_meta=_meta(),
        query_lat=37.0,
        query_lon=-120.0,
        raw_score=0.42,
    )
    assert entry["status"] == "available"
    assert entry["score"] == 0.42
    assert entry["gate_status"] == STATUS_EVALUATED


def test_aggregate_seed_gates_requires_two_of_three():
    assert (
        aggregate_seed_gates([STATUS_EVALUATED, STATUS_EVALUATED, STATUS_NO_SKILL])
        == STATUS_EVALUATED
    )
    assert (
        aggregate_seed_gates([STATUS_EVALUATED, STATUS_NO_SKILL, STATUS_NO_SKILL])
        == STATUS_UNCONFIRMED
    )
    assert (
        aggregate_seed_gates([STATUS_NO_SKILL, STATUS_NO_SKILL, STATUS_NO_SKILL])
        == STATUS_NO_SKILL
    )
