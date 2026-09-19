"""Tests for SSRI Stage 3.0 service contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ssri_model.inference import InferenceConfig
from ssri_model.orchestration import BatchConfig, JobSpec
from ssri_model.service import (
    BatchExecutionStatus,
    BatchInferenceRequest,
    BatchInferenceResponse,
    InferenceExecutionStatus,
    InferenceRequest,
    InferenceResponse,
    OutputFormat,
    ProvenanceRecord,
    ServiceConfig,
    build_provenance_record,
    can_serve_prediction,
    enforce_scientific_gate,
    output_artifacts_for_format,
    resolve_under_output_root,
    sanitize_request_id,
    validate_batch_request,
    validate_inference_request,
    validate_output_format,
    validate_service_config,
)
from ssri_model.service.exceptions import (
    InvalidServiceConfigError,
    InvalidServiceRequestError,
    OutputFormatError,
    PathSafetyError,
    ScientificGateError,
)
from ssri_model.service.validation import (
    ensure_output_under_root,
    reject_null_bytes,
    reject_path_traversal,
)
from tests.inference_helpers import build_inference_inputs
from tests.scientific_helpers import write_evaluation_dataset_with_manifest


@pytest.fixture
def service_config(tmp_path: Path) -> ServiceConfig:
    return ServiceConfig(output_root=str(tmp_path / "service-outputs"))


@pytest.fixture
def inference_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "inference-inputs"
    feature, manifest, statistics, checkpoint, _ = build_inference_inputs(root)
    return feature, manifest, statistics, checkpoint


class TestServiceConfig:
    def test_valid_defaults(self) -> None:
        config = ServiceConfig()
        assert config.max_concurrent_jobs == 1
        assert config.allow_unvalidated_predictions is True

    def test_invalid_tile_overlap(self) -> None:
        with pytest.raises(InvalidServiceConfigError):
            ServiceConfig(default_inference_overlap=512, default_inference_tile_size=512)

    def test_serialization_roundtrip(self) -> None:
        config = ServiceConfig(service_name="test-service", environment="staging")
        restored = ServiceConfig.from_dict(config.to_dict())
        assert restored.service_name == "test-service"
        assert restored.environment.value == "staging"

    def test_validate_service_config(self) -> None:
        config = ServiceConfig()
        assert validate_service_config(config) is config


class TestInferenceRequest:
    def test_serialization_roundtrip(self, inference_inputs: tuple[Path, ...]) -> None:
        feature, manifest, statistics, checkpoint = inference_inputs
        request = InferenceRequest(
            request_id="req-001",
            checkpoint=str(checkpoint),
            features=str(feature),
            manifest=str(manifest),
            statistics=str(statistics),
            output_format=OutputFormat.ALL,
            tile_size=256,
            overlap=32,
            batch_size=2,
        )
        restored = InferenceRequest.from_dict(request.to_dict())
        assert restored.request_id == "req-001"
        assert restored.output_format == OutputFormat.ALL

    def test_to_inference_config_adapter(
        self,
        inference_inputs: tuple[Path, ...],
        tmp_path: Path,
    ) -> None:
        feature, manifest, statistics, checkpoint = inference_inputs
        request = InferenceRequest(
            request_id="req-adapter",
            checkpoint=str(checkpoint),
            features=str(feature),
            manifest=str(manifest),
            statistics=str(statistics),
        )
        config = request.to_inference_config(
            output_dir=tmp_path / "out",
            tile_size=128,
            overlap=16,
            batch_size=1,
        )
        assert isinstance(config, InferenceConfig)
        assert config.tile_size == 128
        assert config.overlap == 16


class TestBatchInferenceRequest:
    def test_serialization_roundtrip(self, tmp_path: Path) -> None:
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps({"batch_id": "b1", "jobs": []}), encoding="utf-8")
        request = BatchInferenceRequest(
            request_id="batch-req-1",
            jobs_file=str(jobs_file),
            output_root=str(tmp_path / "batch-out"),
            resume=True,
        )
        restored = BatchInferenceRequest.from_dict(request.to_dict())
        assert restored.resume is True

    def test_to_batch_config_adapter(self, tmp_path: Path) -> None:
        request = BatchInferenceRequest(
            request_id="batch-req-2",
            jobs_file=str(tmp_path / "jobs.json"),
            output_root=str(tmp_path / "batch-out"),
        )
        config = request.to_batch_config(device="cpu")
        assert isinstance(config, BatchConfig)
        assert config.device == "cpu"


class TestResponses:
    def test_inference_response_roundtrip(self) -> None:
        response = InferenceResponse(
            request_id="req-1",
            status=InferenceExecutionStatus.COMPLETED,
            prediction_path="/out/prediction.tif",
            scientific_validation_status="NOT_VALIDATED",
        )
        restored = InferenceResponse.from_dict(response.to_dict())
        assert restored.status == InferenceExecutionStatus.COMPLETED

    def test_batch_response_roundtrip(self) -> None:
        response = BatchInferenceResponse(
            request_id="batch-1",
            batch_id="demo-batch",
            status=BatchExecutionStatus.COMPLETED,
            total_jobs=3,
            completed_jobs=3,
        )
        restored = BatchInferenceResponse.from_dict(response.to_dict())
        assert restored.total_jobs == 3


class TestOutputFormat:
    def test_valid_formats(self) -> None:
        assert validate_output_format("geotiff") == OutputFormat.GEOTIFF
        assert validate_output_format("all") == OutputFormat.ALL

    def test_invalid_format(self) -> None:
        with pytest.raises(OutputFormatError):
            validate_output_format("png")

    def test_artifact_mapping(self) -> None:
        artifacts = output_artifacts_for_format(OutputFormat.ALL)
        assert "prediction.tif" in artifacts
        assert "inference.json" in artifacts


class TestPathSafety:
    def test_sanitize_request_id(self) -> None:
        assert sanitize_request_id("req-001") == "req-001"

    def test_reject_path_traversal_request_id(self) -> None:
        with pytest.raises(PathSafetyError):
            sanitize_request_id("../evil")

    def test_reject_null_bytes(self) -> None:
        with pytest.raises(PathSafetyError):
            reject_null_bytes("bad\x00id", field_name="request_id")

    def test_reject_path_traversal(self) -> None:
        with pytest.raises(PathSafetyError):
            reject_path_traversal("../../etc/passwd", field_name="checkpoint")

    def test_resolve_under_output_root(self, tmp_path: Path) -> None:
        root = tmp_path / "outputs"
        root.mkdir()
        resolved = resolve_under_output_root(root, "requests", "req-001")
        assert str(resolved).startswith(str(root.resolve()))

    def test_resolve_rejects_escape(self, tmp_path: Path) -> None:
        root = tmp_path / "outputs"
        root.mkdir()
        with pytest.raises(PathSafetyError):
            resolve_under_output_root(root, "..", "escape")

    def test_ensure_output_under_root(self, tmp_path: Path) -> None:
        root = tmp_path / "outputs"
        child = root / "requests" / "req-1"
        child.mkdir(parents=True)
        assert ensure_output_under_root(child, output_root=root) == child.resolve()


class TestScientificGate:
    def test_required_blocks_unvalidated(self) -> None:
        assert (
            can_serve_prediction(
                "NOT_VALIDATED",
                allow_unvalidated_predictions=True,
                scientific_validation_required=True,
            )
            is False
        )

    def test_required_allows_human_validated(self) -> None:
        assert (
            can_serve_prediction(
                "SCIENTIFICALLY_VALIDATED",
                allow_unvalidated_predictions=False,
                scientific_validation_required=True,
            )
            is True
        )

    def test_never_upgrades_status(self) -> None:
        assert (
            can_serve_prediction(
                "DATASET_AUDITED",
                allow_unvalidated_predictions=True,
                scientific_validation_required=True,
            )
            is False
        )

    def test_disallow_unvalidated_when_not_required(self) -> None:
        assert (
            can_serve_prediction(
                "NOT_VALIDATED",
                allow_unvalidated_predictions=False,
                scientific_validation_required=False,
            )
            is False
        )
        assert (
            can_serve_prediction(
                "SPATIALLY_VALIDATED",
                allow_unvalidated_predictions=False,
                scientific_validation_required=False,
            )
            is True
        )

    def test_enforce_gate_raises(self) -> None:
        with pytest.raises(ScientificGateError):
            enforce_scientific_gate(
                "NOT_VALIDATED",
                allow_unvalidated_predictions=False,
                scientific_validation_required=True,
            )


class TestValidateInferenceRequest:
    def test_valid_request(
        self,
        service_config: ServiceConfig,
        inference_inputs: tuple[Path, ...],
    ) -> None:
        feature, manifest, statistics, checkpoint = inference_inputs
        request = InferenceRequest(
            request_id="req-valid",
            checkpoint=str(checkpoint),
            features=str(feature),
            manifest=str(manifest),
            statistics=str(statistics),
        )
        output_dir = validate_inference_request(request, service_config)
        assert str(output_dir).startswith(str(Path(service_config.output_root).resolve()))

    def test_missing_checkpoint(
        self,
        service_config: ServiceConfig,
        inference_inputs: tuple[Path, ...],
    ) -> None:
        feature, manifest, statistics, _ = inference_inputs
        request = InferenceRequest(
            request_id="req-missing",
            checkpoint=str(service_config.output_root) + "/missing.pt",
            features=str(feature),
            manifest=str(manifest),
            statistics=str(statistics),
        )
        with pytest.raises(InvalidServiceRequestError):
            validate_inference_request(request, service_config)

    def test_invalid_overlap(
        self,
        service_config: ServiceConfig,
        inference_inputs: tuple[Path, ...],
    ) -> None:
        feature, manifest, statistics, checkpoint = inference_inputs
        request = InferenceRequest(
            request_id="req-overlap",
            checkpoint=str(checkpoint),
            features=str(feature),
            manifest=str(manifest),
            statistics=str(statistics),
            tile_size=64,
            overlap=64,
        )
        with pytest.raises(InvalidServiceRequestError):
            validate_inference_request(request, service_config)


class TestValidateBatchRequest:
    def test_valid_batch_request(
        self,
        service_config: ServiceConfig,
        tmp_path: Path,
    ) -> None:
        output_root = Path(service_config.output_root)
        output_root.mkdir(parents=True)
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text('{"batch_id":"b1","jobs":[]}', encoding="utf-8")
        request = BatchInferenceRequest(
            request_id="batch-valid",
            jobs_file=str(jobs_file),
            output_root=str(output_root / "batch-001"),
        )
        validated = validate_batch_request(request, service_config)
        assert validated.is_dir() or validated.parent.exists()

    def test_missing_jobs_file(self, service_config: ServiceConfig, tmp_path: Path) -> None:
        request = BatchInferenceRequest(
            request_id="batch-missing",
            jobs_file=str(tmp_path / "missing.json"),
            output_root=str(Path(service_config.output_root) / "batch"),
        )
        with pytest.raises(InvalidServiceRequestError):
            validate_batch_request(request, service_config)


class TestProvenance:
    def test_provenance_serialization(self) -> None:
        record = ProvenanceRecord(
            request_id="req-prov",
            checkpoint_path="/ckpt.pt",
            features_path="/f.npy",
            manifest_path="/m.json",
            statistics_path="/s.json",
            combined_fingerprint="abc",
        )
        restored = ProvenanceRecord.from_dict(record.to_dict())
        assert restored.combined_fingerprint == "abc"

    def test_build_provenance_preserves_fingerprints(
        self,
        inference_inputs: tuple[Path, ...],
    ) -> None:
        feature, manifest, statistics, checkpoint = inference_inputs
        request = InferenceRequest(
            request_id="req-fp",
            checkpoint=str(checkpoint),
            features=str(feature),
            manifest=str(manifest),
            statistics=str(statistics),
        )
        record = build_provenance_record(
            request,
            service_name="ssri",
            service_version="0.1.0",
            inference_configuration={"tile_size": 512},
        )
        assert record.dataset_fingerprint
        assert record.checkpoint_fingerprint
        assert record.combined_fingerprint


class TestBackwardCompatibility:
    def test_stage27_inference_config_unchanged(
        self,
        inference_inputs: tuple[Path, ...],
        tmp_path: Path,
    ) -> None:
        feature, manifest, statistics, checkpoint = inference_inputs
        config = InferenceConfig(
            checkpoint_path=str(checkpoint),
            feature_path=str(feature),
            manifest_path=str(manifest),
            statistics_path=str(statistics),
            output_dir=str(tmp_path / "out"),
        )
        assert config.tile_size == 512

    def test_stage28_job_spec_unchanged(self, inference_inputs: tuple[Path, ...]) -> None:
        feature, manifest, statistics, checkpoint = inference_inputs
        job = JobSpec(
            job_id="aoi-001",
            checkpoint=str(checkpoint),
            features=str(feature),
            manifest=str(manifest),
            statistics=str(statistics),
        )
        assert job.job_id == "aoi-001"

    def test_stage29_fingerprints_reused(
        self,
        tmp_path: Path,
    ) -> None:
        manifest_path, statistics_path = write_evaluation_dataset_with_manifest(
            tmp_path / "dataset"
        )
        from ssri_model.scientific import compute_reproducibility_fingerprints

        fingerprints = compute_reproducibility_fingerprints(
            manifest_path=manifest_path,
            statistics_path=statistics_path,
        )
        assert "combined_fingerprint" in fingerprints
