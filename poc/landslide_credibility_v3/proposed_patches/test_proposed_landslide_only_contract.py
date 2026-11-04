"""Proposed tests — NOT installed into production path.

Landslide-only contract: sinkhole/subsidence never return a score.
"""
from __future__ import annotations


def build_landslide_only_payload(landslide_score: float) -> dict:
    return {
        "landslide": {
            "availability": "available",
            "score": float(landslide_score),
        },
        "subsidence": {"availability": "not_available", "score": None},
        "sinkhole": {"availability": "not_available", "score": None},
    }


def test_subsidence_sinkhole_not_available():
    p = build_landslide_only_payload(0.42)
    assert p["subsidence"]["availability"] == "not_available"
    assert p["subsidence"]["score"] is None
    assert p["sinkhole"]["availability"] == "not_available"
    assert p["sinkhole"]["score"] is None
    assert p["landslide"]["availability"] == "available"
    assert isinstance(p["landslide"]["score"], float)


def test_never_fabricate_scores_for_unavailable():
    p = build_landslide_only_payload(0.1)
    for key in ("subsidence", "sinkhole"):
        assert p[key]["score"] is None
        assert p[key]["availability"] == "not_available"


if __name__ == "__main__":
    test_subsidence_sinkhole_not_available()
    test_never_fabricate_scores_for_unavailable()
    print("OK: landslide-only contract tests passed")
