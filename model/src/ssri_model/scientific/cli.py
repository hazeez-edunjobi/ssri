"""CLI for SSRI scientific validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ssri_model.scientific.config import ScientificValidationConfig
from ssri_model.scientific.exceptions import ScientificValidationError
from ssri_model.scientific.report import (
    ScientificReviewRecord,
    attach_review,
    save_scientific_validation_json,
)
from ssri_model.scientific.validation import (
    audit_dataset_only,
    audit_features_only,
    audit_labels_only,
    audit_spatial_only,
    run_scientific_validation,
)

EXIT_SUCCESS = 0
EXIT_WARNINGS = 1
EXIT_FAILURE = 2
EXIT_INVALID_CONFIG = 3

DISCLAIMER = (
    "Automated validation does not establish geological truth or operational hazard accuracy."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SSRI scientific validation and dataset integrity audits.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit", help="Audit dataset integrity")
    audit_parser.add_argument("--manifest", required=True)
    audit_parser.add_argument("--statistics")
    audit_parser.add_argument("--output")

    spatial_parser = subparsers.add_parser("spatial", help="Audit spatial splits")
    spatial_parser.add_argument("--manifest", required=True)
    spatial_parser.add_argument("--spatial-buffer-m", type=float, default=0.0)
    spatial_parser.add_argument("--output")

    labels_parser = subparsers.add_parser("labels", help="Audit labels")
    labels_parser.add_argument("--manifest", required=True)
    labels_parser.add_argument("--output")

    features_parser = subparsers.add_parser("features", help="Audit features")
    features_parser.add_argument("--manifest", required=True)
    features_parser.add_argument("--output")

    report_parser = subparsers.add_parser("report", help="Generate full validation report")
    report_parser.add_argument("--manifest", required=True)
    report_parser.add_argument("--statistics")
    report_parser.add_argument("--checkpoint")
    report_parser.add_argument("--output", required=True)
    report_parser.add_argument("--spatial-buffer-m", type=float, default=0.0)

    review_parser = subparsers.add_parser("review", help="Attach human review metadata")
    review_parser.add_argument("--report", required=True)
    review_parser.add_argument("--reviewer", required=True)
    review_parser.add_argument("--decision", choices=("accepted", "rejected"), required=True)
    review_parser.add_argument("--notes", required=True)
    review_parser.add_argument("--dataset-version", default="")
    review_parser.add_argument("--fingerprint", default="")

    return parser


def _write_output(output: Path | None, payload: dict[str, object]) -> None:
    text = json.dumps(payload, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text)


def _status_exit(status: str, warnings: list[str]) -> int:
    if status == "FAIL":
        return EXIT_FAILURE
    if status == "WARNING" or warnings:
        return EXIT_WARNINGS
    return EXIT_SUCCESS


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return EXIT_INVALID_CONFIG
    print(DISCLAIMER, file=sys.stderr)

    try:
        if args.command == "audit":
            result = audit_dataset_only(
                manifest_path=args.manifest,
                statistics_path=args.statistics,
            )
            _write_output(
                Path(args.output) if args.output else None,
                {
                    "status": result.status,
                    "dataset_name": result.dataset_name,
                    "dataset_version": result.dataset_version,
                    "sample_count": result.sample_count,
                    "warnings": result.warnings,
                    "scientific_validation_status": "NOT_VALIDATED",
                },
            )
            return _status_exit(result.status, result.warnings)

        if args.command == "spatial":
            config = ScientificValidationConfig(spatial_buffer_m=args.spatial_buffer_m)
            spatial_result = audit_spatial_only(manifest_path=args.manifest, config=config)
            _write_output(
                Path(args.output) if args.output else None,
                {
                    "status": spatial_result.status,
                    "overlapping_samples": spatial_result.overlapping_samples,
                    "buffered_samples": spatial_result.buffered_samples,
                    "minimum_distance_m": spatial_result.minimum_distance_m,
                    "maximum_distance_m": spatial_result.maximum_distance_m,
                    "messages": spatial_result.messages,
                    "scientific_validation_status": "NOT_VALIDATED",
                },
            )
            return _status_exit(spatial_result.status, spatial_result.messages)

        if args.command == "labels":
            label_result = audit_labels_only(manifest_path=args.manifest)
            _write_output(
                Path(args.output) if args.output else None,
                {
                    "status": label_result.status,
                    "valid_pixels": label_result.valid_pixels,
                    "per_class_pixels": label_result.per_class_pixels,
                    "warnings": label_result.warnings,
                    "scientific_validation_status": "NOT_VALIDATED",
                },
            )
            return _status_exit(label_result.status, label_result.warnings)

        if args.command == "features":
            feature_result = audit_features_only(manifest_path=args.manifest)
            _write_output(
                Path(args.output) if args.output else None,
                {
                    "status": feature_result.status,
                    "channels": [
                        {
                            "channel_name": channel.channel_name,
                            "valid_count": channel.valid_count,
                            "nodata_fraction": channel.nodata_fraction,
                            "constant_value": channel.constant_value,
                            "warnings": channel.warnings,
                            "status": channel.status,
                        }
                        for channel in feature_result.channels
                    ],
                    "warnings": feature_result.warnings,
                    "scientific_validation_status": "NOT_VALIDATED",
                },
            )
            return _status_exit(feature_result.status, feature_result.warnings)

        if args.command == "report":
            config = ScientificValidationConfig(spatial_buffer_m=args.spatial_buffer_m)
            report = run_scientific_validation(
                manifest_path=args.manifest,
                statistics_path=args.statistics,
                output_dir=args.output,
                config=config,
                checkpoint_path=args.checkpoint,
            )
            print(
                json.dumps(
                    {
                        "status": report.status,
                        "scientific_validation_status": report.scientific_validation_status,
                        "output_dir": str(args.output),
                    },
                    indent=2,
                )
            )
            if report.status == "NOT_VALIDATED" and report.failures:
                return EXIT_FAILURE
            if report.warnings:
                return EXIT_WARNINGS
            return EXIT_SUCCESS

        if args.command == "review":
            report_path = Path(args.report)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            from ssri_model.scientific.report import ScientificValidationReport

            report = ScientificValidationReport(
                status=payload.get("status", "NOT_VALIDATED"),
                scientific_validation_status=payload.get(
                    "scientific_validation_status", "NOT_VALIDATED"
                ),
                dataset=dict(payload.get("dataset", {})),
                audits=dict(payload.get("audits", {})),
                warnings=list(payload.get("warnings", [])),
                fingerprints=dict(payload.get("fingerprints", {})),
            )
            review = ScientificReviewRecord(
                reviewer=args.reviewer,
                reviewed_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
                decision=args.decision,
                notes=args.notes,
                dataset_version=args.dataset_version,
                report_fingerprint=args.fingerprint
                or report.fingerprints.get("combined_fingerprint", ""),
            )
            updated = attach_review(
                report,
                review,
                expected_fingerprint=args.fingerprint or None,
            )
            save_scientific_validation_json(report_path, updated)
            print(json.dumps(updated.to_dict(), indent=2))
            return EXIT_SUCCESS

    except ScientificValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID_CONFIG
    except Exception as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return EXIT_FAILURE

    return EXIT_INVALID_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())
