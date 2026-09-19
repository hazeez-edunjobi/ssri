"""Tests for SSRI scientific validation core."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ssri_model.scientific import (
    ScientificReviewRecord,
    ScientificValidationConfig,
    attach_review,
    audit_dataset,
    compute_reproducibility_fingerprints,
    run_scientific_validation,
)
from ssri_model.scientific.cli import EXIT_INVALID_CONFIG, EXIT_SUCCESS, EXIT_WARNINGS, main
from ssri_model.scientific.exceptions import ReviewValidationError
from ssri_model.scientific.report import ScientificValidationReport
from tests.scientific_helpers import write_evaluation_dataset_with_manifest


class TestDatasetAudit:
    def test_valid_dataset(self, tmp_path: Path) -> None:
        manifest_path, statistics_path = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        result = audit_dataset(manifest_path=manifest_path, statistics_path=statistics_path)
        assert result.status == "PASS"
        assert result.sample_count == 5
        assert result.feature_statistics_present is True

    def test_missing_sample(self, tmp_path: Path) -> None:
        manifest_path, statistics_path = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        sample_dir = tmp_path / "dataset" / "train" / "train-a"
        (sample_dir / "feature_stack.npy").unlink()
        result = audit_dataset(manifest_path=manifest_path, statistics_path=statistics_path)
        assert result.status == "FAIL"
        assert result.missing_files

    def test_duplicate_ids_in_manifest_edit(self, tmp_path: Path) -> None:
        manifest_path, statistics_path = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["splits"]["test"].append("train-a")
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        from ssri_model.scientific.leakage import validate_dataset_independence

        report = validate_dataset_independence(manifest_path.parent, payload)
        assert report.independent is False

    def test_missing_statistics(self, tmp_path: Path) -> None:
        manifest_path, _ = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        result = audit_dataset(
            manifest_path=manifest_path,
            statistics_path=tmp_path / "missing.json",
        )
        assert result.feature_statistics_present is False
        assert result.status == "WARNING"


class TestReproducibility:
    def test_identical_fingerprints(self, tmp_path: Path) -> None:
        manifest_path, statistics_path = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        first = compute_reproducibility_fingerprints(
            manifest_path=manifest_path,
            statistics_path=statistics_path,
        )
        second = compute_reproducibility_fingerprints(
            manifest_path=manifest_path,
            statistics_path=statistics_path,
        )
        assert first["combined_fingerprint"] == second["combined_fingerprint"]

    def test_changed_dataset_fingerprint(self, tmp_path: Path) -> None:
        manifest_path, statistics_path = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        first = compute_reproducibility_fingerprints(
            manifest_path=manifest_path,
            statistics_path=statistics_path,
        )
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["version"] = "0.2.0"
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        second = compute_reproducibility_fingerprints(
            manifest_path=manifest_path,
            statistics_path=statistics_path,
        )
        assert first["dataset_fingerprint"] != second["dataset_fingerprint"]

    def test_changed_configuration_fingerprint(self, tmp_path: Path) -> None:
        manifest_path, statistics_path = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        first = compute_reproducibility_fingerprints(
            manifest_path=manifest_path,
            statistics_path=statistics_path,
            config=ScientificValidationConfig(random_seed=42),
        )
        second = compute_reproducibility_fingerprints(
            manifest_path=manifest_path,
            statistics_path=statistics_path,
            config=ScientificValidationConfig(random_seed=99),
        )
        assert first["configuration_fingerprint"] != second["configuration_fingerprint"]


class TestReviewGate:
    def test_incomplete_review_rejected(self) -> None:
        with pytest.raises(ReviewValidationError):
            ScientificReviewRecord(
                reviewer="",
                reviewed_at="2026-01-01T00:00:00+00:00",
                decision="accepted",
                notes="",
            )

    def test_valid_review_accepted(self) -> None:
        report = ScientificValidationReport()
        review = ScientificReviewRecord(
            reviewer="domain.expert",
            reviewed_at="2026-01-01T00:00:00+00:00",
            decision="accepted",
            notes="Reviewed against independent evidence.",
            report_fingerprint="abc123",
        )
        updated = attach_review(report, review)
        assert updated.scientific_validation_status == "SCIENTIFICALLY_VALIDATED"

    def test_report_fingerprint_mismatch_rejected(self) -> None:
        report = ScientificValidationReport(fingerprints={"combined_fingerprint": "expected"})
        review = ScientificReviewRecord(
            reviewer="domain.expert",
            reviewed_at="2026-01-01T00:00:00+00:00",
            decision="accepted",
            notes="Review notes",
            report_fingerprint="wrong",
        )
        with pytest.raises(ReviewValidationError):
            attach_review(report, review, expected_fingerprint="expected")


class TestScientificCLI:
    def test_cli_audit(self, tmp_path: Path) -> None:
        manifest_path, statistics_path = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        code = main(
            [
                "audit",
                "--manifest",
                str(manifest_path),
                "--statistics",
                str(statistics_path),
            ]
        )
        assert code == EXIT_SUCCESS

    def test_cli_report(self, tmp_path: Path) -> None:
        manifest_path, statistics_path = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        output = tmp_path / "report"
        code = main(
            [
                "report",
                "--manifest",
                str(manifest_path),
                "--statistics",
                str(statistics_path),
                "--output",
                str(output),
            ]
        )
        assert code in (EXIT_SUCCESS, EXIT_WARNINGS)
        assert (output / "scientific_validation.json").exists()
        assert (output / "scientific_validation.md").exists()
        payload = json.loads((output / "scientific_validation.json").read_text(encoding="utf-8"))
        assert payload["scientific_validation_status"] != "SCIENTIFICALLY_VALIDATED"

    def test_cli_invalid_arguments(self) -> None:
        code = main(["audit"])
        assert code == EXIT_INVALID_CONFIG

    def test_automated_report_never_self_validates(self, tmp_path: Path) -> None:
        manifest_path, statistics_path = write_evaluation_dataset_with_manifest(tmp_path / "dataset")
        report = run_scientific_validation(
            manifest_path=manifest_path,
            statistics_path=statistics_path,
            output_dir=tmp_path / "out",
        )
        assert report.scientific_validation_status != "SCIENTIFICALLY_VALIDATED"
