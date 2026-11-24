"""Subsidence validation harness — refuses metrics without real ground truth."""

from __future__ import annotations

from ssri_model.evaluation.subsidence_validation import (
    GROUND_TRUTH_SCHEMA_VERSION,
    GroundTruthRecord,
    assess_inventory_quality,
    evaluate_subsidence_scores,
    ground_truth_schema,
    missing_ground_truth_report,
    parse_ground_truth_rows,
    write_schema_stub,
)


def test_missing_ground_truth_is_blocked_not_validated():
    report = missing_ground_truth_report(checkpoint_id="ssri-model-e7af3afcd0")
    assert report["scientific_validation_status"] == "NOT_VALIDATED"
    assert report["readiness"] == "BLOCKED_BY_MISSING_DATA"
    assert report["metrics_computed"] is False
    assert report["ground_truth_schema"]["schema"] == GROUND_TRUTH_SCHEMA_VERSION


def test_schema_stub_empty(tmp_path):
    path = write_schema_stub(tmp_path / "subsidence_ground_truth.json")
    assert path.is_file()
    assert "records" in path.read_text(encoding="utf-8")


def test_underpowered_inventory_flags_quality():
    rows = [
        {
            "longitude": 3.2 + i * 0.01,
            "latitude": 7.2,
            "label": 1 if i < 5 else 0,
            "source": "unit-test-synthetic-not-real",
            "observed_date": "2020-01-01",
        }
        for i in range(10)
    ]
    records = parse_ground_truth_rows(rows)
    quality = assess_inventory_quality(records)
    assert quality["underpowered"] is True
    assert quality["n_positives"] == 5


def test_evaluate_with_toy_scores_still_not_validated():
    records = [
        GroundTruthRecord(
            longitude=3.0 + i * 0.6,
            latitude=7.0 + (i % 3) * 0.6,
            label=1 if i % 2 == 0 else 0,
            source="unit-test-synthetic-not-real",
            observed_date="2020-01-01",
        )
        for i in range(40)
    ]
    scores = [0.8 if r.label == 1 else 0.2 for r in records]
    report = evaluate_subsidence_scores(
        records, scores, checkpoint_id="ssri-model-e7af3afcd0"
    )
    assert report["scientific_validation_status"] == "NOT_VALIDATED"
    assert report["metrics"]["metrics_computed"] is True
    assert report["metrics"]["roc_auc"] > 0.9
    assert "probability" not in report["score_interpretation"].lower() or "not" in report[
        "score_interpretation"
    ].lower()


def test_ground_truth_schema_forbids_synthetic_as_truth():
    schema = ground_truth_schema()
    blob = " ".join(schema["forbidden"]).lower()
    assert "synthetic" in blob
    assert "tmi" in blob
