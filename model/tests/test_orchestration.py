"""Tests for SSRI orchestration job validation and configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from ssri_model.orchestration import (
    BatchConfig,
    DuplicateJobIdError,
    InvalidBatchConfigError,
    InvalidJobSpecError,
    JobSpec,
    JobValidationError,
    PathTraversalError,
    load_jobs_file,
    sanitize_job_id,
    validate_job_spec,
)
from ssri_model.orchestration.jobs import validate_job_specs
from tests.orchestration_helpers import write_job_dataset, write_jobs_file


class TestJobSpecValidation:
    def test_valid_job(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        output_dir = validate_job_spec(job, output_root=tmp_path / "outputs")
        assert output_dir.name == "aoi-001"

    def test_missing_checkpoint(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        job = JobSpec(
            job_id=job.job_id,
            checkpoint=str(tmp_path / "missing.pt"),
            features=job.features,
            manifest=job.manifest,
            statistics=job.statistics,
        )
        with pytest.raises(JobValidationError, match="Checkpoint"):
            validate_job_spec(job, output_root=tmp_path / "outputs")

    def test_missing_features(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        job = JobSpec(
            job_id=job.job_id,
            checkpoint=job.checkpoint,
            features=str(tmp_path / "missing.npy"),
            manifest=job.manifest,
            statistics=job.statistics,
        )
        with pytest.raises(JobValidationError, match="Feature stack"):
            validate_job_spec(job, output_root=tmp_path / "outputs")

    def test_missing_manifest(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        job = JobSpec(
            job_id=job.job_id,
            checkpoint=job.checkpoint,
            features=job.features,
            manifest=str(tmp_path / "missing.json"),
            statistics=job.statistics,
        )
        with pytest.raises(JobValidationError, match="Manifest"):
            validate_job_spec(job, output_root=tmp_path / "outputs")

    def test_missing_statistics(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        job = JobSpec(
            job_id=job.job_id,
            checkpoint=job.checkpoint,
            features=job.features,
            manifest=job.manifest,
            statistics=str(tmp_path / "missing.json"),
        )
        with pytest.raises(JobValidationError, match="Statistics"):
            validate_job_spec(job, output_root=tmp_path / "outputs")

    def test_empty_job_id(self) -> None:
        with pytest.raises(InvalidJobSpecError):
            JobSpec(
                job_id="   ",
                checkpoint="a.pt",
                features="f.npy",
                manifest="m.json",
                statistics="s.json",
            )

    def test_duplicate_job_ids(self, tmp_path: Path) -> None:
        job_a = write_job_dataset(tmp_path, "aoi-001")
        job_b = write_job_dataset(tmp_path / "copy", "aoi-001")
        with pytest.raises(DuplicateJobIdError):
            validate_job_specs([job_a, job_b], output_root=tmp_path / "outputs")

    def test_path_traversal_job_id(self) -> None:
        with pytest.raises(PathTraversalError):
            sanitize_job_id("../../evil")

    def test_unsafe_job_id_characters(self) -> None:
        with pytest.raises(PathTraversalError):
            sanitize_job_id("bad id")


class TestBatchConfig:
    def test_defaults(self) -> None:
        config = BatchConfig(output_root="outputs")
        assert config.max_workers == 1
        assert config.continue_on_error is True
        assert config.fail_fast is False

    def test_invalid_max_workers(self) -> None:
        with pytest.raises(InvalidBatchConfigError):
            BatchConfig(output_root="outputs", max_workers=0)

    def test_resume_and_overwrite_conflict(self) -> None:
        with pytest.raises(InvalidBatchConfigError):
            BatchConfig(output_root="outputs", resume=True, overwrite=True)


class TestJobsFile:
    def test_load_valid_jobs_file(self, tmp_path: Path) -> None:
        job = write_job_dataset(tmp_path, "aoi-001")
        jobs_path = write_jobs_file(tmp_path / "jobs.json", [job], batch_id="demo-001")
        loaded = load_jobs_file(jobs_path)
        assert loaded.batch_id == "demo-001"
        assert len(loaded.jobs) == 1

    def test_invalid_jobs_file(self, tmp_path: Path) -> None:
        path = tmp_path / "jobs.json"
        path.write_text("{}", encoding="utf-8")
        with pytest.raises(JobValidationError):
            load_jobs_file(path)
