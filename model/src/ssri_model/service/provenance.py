"""Provenance records for SSRI service operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ssri_model import __version__
from ssri_model.scientific.validation import compute_reproducibility_fingerprints
from ssri_model.service.requests import InferenceRequest


@dataclass(frozen=True)
class ProvenanceRecord:
    """Provenance metadata for one service inference operation."""

    request_id: str
    checkpoint_path: str
    features_path: str
    manifest_path: str
    statistics_path: str
    dataset_name: str | None = None
    dataset_version: str | None = None
    dataset_fingerprint: str = ""
    statistics_fingerprint: str = ""
    checkpoint_fingerprint: str = ""
    configuration_fingerprint: str = ""
    combined_fingerprint: str = ""
    inference_configuration: dict[str, Any] = field(default_factory=dict)
    scientific_validation_status: str = "NOT_VALIDATED"
    service_name: str = "ssri-inference"
    service_version: str = __version__
    auth_key_id: str | None = None
    auth_role: str | None = None
    auth_method: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ProvenanceRecord:
        return cls(
            request_id=str(payload["request_id"]),
            checkpoint_path=str(payload["checkpoint_path"]),
            features_path=str(payload["features_path"]),
            manifest_path=str(payload["manifest_path"]),
            statistics_path=str(payload["statistics_path"]),
            dataset_name=payload.get("dataset_name"),
            dataset_version=payload.get("dataset_version"),
            dataset_fingerprint=str(payload.get("dataset_fingerprint", "")),
            statistics_fingerprint=str(payload.get("statistics_fingerprint", "")),
            checkpoint_fingerprint=str(payload.get("checkpoint_fingerprint", "")),
            configuration_fingerprint=str(payload.get("configuration_fingerprint", "")),
            combined_fingerprint=str(payload.get("combined_fingerprint", "")),
            inference_configuration=dict(payload.get("inference_configuration", {})),
            scientific_validation_status=str(
                payload.get("scientific_validation_status", "NOT_VALIDATED")
            ),
            service_name=str(payload.get("service_name", "ssri-inference")),
            service_version=str(payload.get("service_version", __version__)),
            auth_key_id=payload.get("auth_key_id"),
            auth_role=payload.get("auth_role"),
            auth_method=payload.get("auth_method"),
            created_at=str(payload.get("created_at", datetime.now(timezone.utc).isoformat())),
        )


def build_provenance_record(
    request: InferenceRequest,
    *,
    service_name: str,
    service_version: str,
    inference_configuration: Mapping[str, Any],
    scientific_validation_status: str = "NOT_VALIDATED",
    dataset_name: str | None = None,
    dataset_version: str | None = None,
    auth_key_id: str | None = None,
    auth_role: str | None = None,
    auth_method: str | None = None,
) -> ProvenanceRecord:
    """Build a provenance record using Stage 2.9 fingerprint utilities."""
    manifest_path = Path(request.manifest)
    statistics_path = Path(request.statistics)
    checkpoint_path = Path(request.checkpoint)

    fingerprints = compute_reproducibility_fingerprints(
        manifest_path=manifest_path,
        statistics_path=statistics_path,
        checkpoint_path=checkpoint_path,
    )

    return ProvenanceRecord(
        request_id=request.request_id,
        checkpoint_path=str(checkpoint_path),
        features_path=request.features,
        manifest_path=str(manifest_path),
        statistics_path=str(statistics_path),
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        dataset_fingerprint=fingerprints.get("dataset_fingerprint", ""),
        statistics_fingerprint=fingerprints.get("statistics_fingerprint", ""),
        checkpoint_fingerprint=fingerprints.get("checkpoint_fingerprint", ""),
        configuration_fingerprint=fingerprints.get("configuration_fingerprint", ""),
        combined_fingerprint=fingerprints.get("combined_fingerprint", ""),
        inference_configuration=dict(inference_configuration),
        scientific_validation_status=scientific_validation_status,
        service_name=service_name,
        service_version=service_version,
        auth_key_id=auth_key_id,
        auth_role=auth_role,
        auth_method=auth_method,
    )
