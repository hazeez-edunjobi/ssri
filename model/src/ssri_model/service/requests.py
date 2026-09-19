"""Service request contracts for SSRI inference."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from ssri_model.inference.config import InferenceConfig
from ssri_model.orchestration.config import BatchConfig
from ssri_model.service.schemas import OutputFormat


@dataclass(frozen=True)
class InferenceRequest:
    """Typed single-inference request for future service consumption."""

    request_id: str
    checkpoint: str
    features: str
    manifest: str
    statistics: str
    output_format: OutputFormat = OutputFormat.ALL
    tile_size: int | None = None
    overlap: int | None = None
    batch_size: int | None = None
    scientific_validation_required: bool = False
    output_dir: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["output_format"] = self.output_format.value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> InferenceRequest:
        output_format = payload.get("output_format", OutputFormat.ALL.value)
        if isinstance(output_format, OutputFormat):
            fmt = output_format
        else:
            fmt = OutputFormat(str(output_format))
        return cls(
            request_id=str(payload["request_id"]),
            checkpoint=str(payload["checkpoint"]),
            features=str(payload["features"]),
            manifest=str(payload["manifest"]),
            statistics=str(payload["statistics"]),
            output_format=fmt,
            tile_size=payload.get("tile_size"),
            overlap=payload.get("overlap"),
            batch_size=payload.get("batch_size"),
            scientific_validation_required=bool(
                payload.get("scientific_validation_required", False)
            ),
            output_dir=str(payload.get("output_dir", "")),
        )

    def to_inference_config(
        self,
        *,
        output_dir: Path | str,
        tile_size: int,
        overlap: int,
        batch_size: int,
    ) -> InferenceConfig:
        """Adapt this request to a Stage 2.7 InferenceConfig."""
        return InferenceConfig(
            checkpoint_path=self.checkpoint,
            feature_path=self.features,
            manifest_path=self.manifest,
            statistics_path=self.statistics,
            output_dir=str(output_dir),
            tile_size=tile_size,
            overlap=overlap,
            batch_size=batch_size,
        )


@dataclass(frozen=True)
class BatchInferenceRequest:
    """Typed batch inference request for future service consumption."""

    request_id: str
    jobs_file: str
    output_root: str
    resume: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> BatchInferenceRequest:
        return cls(
            request_id=str(payload["request_id"]),
            jobs_file=str(payload["jobs_file"]),
            output_root=str(payload["output_root"]),
            resume=bool(payload.get("resume", False)),
        )

    def to_batch_config(self, *, device: str = "auto") -> BatchConfig:
        """Adapt this request to a Stage 2.8 BatchConfig."""
        return BatchConfig(
            output_root=self.output_root,
            resume=self.resume,
            device=device,  # type: ignore[arg-type]
        )
