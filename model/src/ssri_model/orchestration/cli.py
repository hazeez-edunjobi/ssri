"""CLI for SSRI batch orchestration."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from ssri_model.orchestration.config import BatchConfig
from ssri_model.orchestration.exceptions import OrchestrationError
from ssri_model.orchestration.jobs import load_jobs_file
from ssri_model.orchestration.manifest import load_batch_manifest
from ssri_model.orchestration.runner import BatchRunner
from ssri_model.orchestration.status import get_batch_status

EXIT_SUCCESS = 0
EXIT_COMPLETED_WITH_ERRORS = 1
EXIT_INVALID_CONFIG = 2
EXIT_FATAL = 3


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SSRI batch inference orchestration.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a batch from jobs.json")
    run_parser.add_argument("--jobs", required=True, help="Path to jobs.json")
    run_parser.add_argument("--output-root", required=True, help="Batch output directory")
    run_parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    run_parser.add_argument("--fail-fast", action="store_true")
    run_parser.add_argument("--no-continue-on-error", action="store_true")
    run_parser.add_argument("--overwrite", action="store_true")

    status_parser = subparsers.add_parser("status", help="Show batch status")
    status_parser.add_argument("--manifest", required=True, help="Path to batch_manifest.json")

    resume_parser = subparsers.add_parser("resume", help="Resume an existing batch")
    resume_parser.add_argument("--manifest", required=True, help="Path to batch_manifest.json")
    resume_parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    resume_parser.add_argument("--fail-fast", action="store_true")
    resume_parser.add_argument("--no-continue-on-error", action="store_true")

    return parser


def cmd_run(args: argparse.Namespace) -> int:
    batch_file = load_jobs_file(args.jobs)
    config = BatchConfig(
        output_root=args.output_root,
        fail_fast=args.fail_fast,
        continue_on_error=not args.no_continue_on_error,
        overwrite=args.overwrite,
        device=args.device,
        batch_id=batch_file.batch_id,
    )
    runner = BatchRunner(config)
    result = runner.run(list(batch_file.jobs), metadata=dict(batch_file.metadata))
    if result.status == "completed_with_errors":
        return EXIT_COMPLETED_WITH_ERRORS
    if result.status == "failed":
        return EXIT_FATAL
    return EXIT_SUCCESS


def cmd_status(args: argparse.Namespace) -> int:
    status = get_batch_status(args.manifest)
    print(json.dumps(status.to_dict(), indent=2))
    if status.status == "completed_with_errors":
        return EXIT_COMPLETED_WITH_ERRORS
    if status.status == "failed":
        return EXIT_FATAL
    return EXIT_SUCCESS


def cmd_resume(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    manifest = load_batch_manifest(manifest_path)
    config = BatchConfig(
        output_root=str(manifest_path.parent),
        resume=True,
        fail_fast=args.fail_fast,
        continue_on_error=not args.no_continue_on_error,
        device=args.device,
        batch_id=manifest.batch_id,
    )
    jobs = [record.to_job_spec() for record in manifest.jobs]
    runner = BatchRunner(config)
    result = runner.run(jobs, batch_id=manifest.batch_id, metadata=manifest.metadata)
    if result.status == "completed_with_errors":
        return EXIT_COMPLETED_WITH_ERRORS
    if result.status == "failed":
        return EXIT_FATAL
    return EXIT_SUCCESS


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    try:
        if args.command == "run":
            return cmd_run(args)
        if args.command == "status":
            return cmd_status(args)
        if args.command == "resume":
            return cmd_resume(args)
    except OrchestrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID_CONFIG
    except Exception as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return EXIT_FATAL
    return EXIT_FATAL


if __name__ == "__main__":
    raise SystemExit(main())
