"""Windowed SSRI inference runner."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from ssri_model.evaluation.predictions import logits_to_probabilities
from ssri_model.ml.constants import FEATURE_NODATA, LABEL_NODATA
from ssri_model.ml.normalization import normalize_feature_stack
from ssri_model.training.device import resolve_device
from ssri_model.training.seed import set_seed
from ssri_model.inference.checkpoint import load_inference_checkpoint
from ssri_model.inference.config import InferenceConfig
from ssri_model.inference.exceptions import InferenceError, InvalidInferenceConfigError
from ssri_model.inference.metadata import (
    INFERENCE_JSON_NAME,
    build_inference_metadata,
    write_inference_json,
)
from ssri_model.inference.predictions import (
    save_class_probability_raster,
    save_confidence_raster,
    save_prediction_raster,
    save_probability_raster,
)
from ssri_model.inference.safety import InferenceContext, validate_inference_setup
from ssri_model.inference.tiling import InferenceWindow, generate_windows, uniform_blend_weights


@dataclass(frozen=True)
class InferenceResult:
    """Structured result from an SSRI inference run."""

    prediction: np.ndarray
    confidence: np.ndarray
    probabilities: np.ndarray
    mask: np.ndarray
    prediction_path: Path
    confidence_path: Path
    probabilities_path: Path
    metadata_path: Path
    elapsed_seconds: float


def _open_feature_memmap(feature_path: Path) -> np.memmap:
    loaded = np.load(feature_path, mmap_mode="r")
    if not isinstance(loaded, np.memmap):
        raise InferenceError(f"Expected memmap feature stack at {feature_path}")
    return loaded


def _build_valid_mask(features: np.ndarray) -> np.ndarray:
    mask = np.all(features != FEATURE_NODATA, axis=0)
    return np.asarray(mask, dtype=bool)


def _compute_full_valid_mask(
    features: np.memmap | np.ndarray,
    *,
    chunk_rows: int = 512,
) -> np.ndarray:
    """Compute the full-grid valid mask without loading the entire stack."""
    _, height, width = features.shape
    valid = np.zeros((height, width), dtype=bool)
    for row in range(0, height, chunk_rows):
        row_end = min(row + chunk_rows, height)
        chunk = np.asarray(features[:, row:row_end, :], dtype=np.float64)
        valid[row:row_end, :] = _build_valid_mask(chunk)
    return valid


def _read_window(
    features: np.memmap | np.ndarray,
    window: InferenceWindow,
) -> np.ndarray:
    row_end = window.row + window.height
    col_end = window.col + window.width
    return np.asarray(
        features[:, window.row:row_end, window.col:col_end],
        dtype=np.float32,
    )


def _pad_to_tile(
    features: np.ndarray,
    valid_mask: np.ndarray,
    *,
    tile_size: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Pad a window to ``tile_size`` for batched model inference."""
    channels, height, width = features.shape
    if height == tile_size and width == tile_size:
        return features, valid_mask

    padded_features = np.zeros((channels, tile_size, tile_size), dtype=np.float32)
    padded_mask = np.zeros((tile_size, tile_size), dtype=bool)
    padded_features[:, :height, :width] = features
    padded_mask[:height, :width] = valid_mask
    return padded_features, padded_mask


def _run_model_batch(
    model: torch.nn.Module,
    batch_features: torch.Tensor,
    *,
    device: torch.device,
    mixed_precision: bool,
) -> torch.Tensor:
    logits: torch.Tensor
    if mixed_precision and device.type == "cuda":
        with torch.autocast(device_type="cuda"):
            logits = model(batch_features)
    else:
        logits = model(batch_features)
    return logits


def _infer_windowed(
    model: torch.nn.Module,
    features: np.memmap | np.ndarray,
    *,
    context: InferenceContext,
    config: InferenceConfig,
    device: torch.device,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    _, height, width = context.feature_shape
    windows = generate_windows(
        height,
        width,
        tile_size=config.tile_size,
        overlap=config.overlap,
    )

    prob_sum = np.zeros((3, height, width), dtype=np.float64)
    weight_sum = np.zeros((height, width), dtype=np.float64)

    batch_windows: list[InferenceWindow] = []
    batch_tensors: list[np.ndarray] = []
    batch_masks: list[np.ndarray] = []

    def flush_batch() -> None:
        if not batch_windows:
            return

        feature_batch = torch.from_numpy(np.stack(batch_tensors, axis=0)).to(device)
        with torch.no_grad():
            logits = _run_model_batch(
                model,
                feature_batch,
                device=device,
                mixed_precision=config.mixed_precision,
            )
            probabilities = logits_to_probabilities(logits).cpu().numpy()

        for index, window in enumerate(batch_windows):
            probs = probabilities[index, :, : window.height, : window.width]
            weights = uniform_blend_weights(window.height, window.width)
            row_end = window.row + window.height
            col_end = window.col + window.width
            prob_sum[:, window.row:row_end, window.col:col_end] += probs * weights
            weight_sum[window.row:row_end, window.col:col_end] += weights

        batch_windows.clear()
        batch_tensors.clear()
        batch_masks.clear()

    for window in windows:
        raw = _read_window(features, window)
        valid_mask = _build_valid_mask(raw)
        normalized = normalize_feature_stack(
            raw,
            valid_mask=valid_mask,
            statistics=context.statistics,
            config=context.normalization,
        )
        padded_features, _ = _pad_to_tile(
            normalized,
            valid_mask,
            tile_size=config.tile_size,
        )
        batch_windows.append(window)
        batch_tensors.append(padded_features)
        batch_masks.append(valid_mask)

        if len(batch_windows) >= config.batch_size:
            flush_batch()

    flush_batch()

    probabilities = np.zeros((3, height, width), dtype=np.float32)
    covered = weight_sum > 0.0
    if covered.any():
        probabilities[:, covered] = (
            prob_sum[:, covered] / weight_sum[covered]
        ).astype(np.float32)

    full_valid_mask = _compute_full_valid_mask(features)
    prediction = np.full((height, width), LABEL_NODATA, dtype=np.int64)
    confidence = np.zeros((height, width), dtype=np.float32)

    if full_valid_mask.any():
        valid_probs = probabilities[:, full_valid_mask]
        prediction[full_valid_mask] = np.argmax(valid_probs, axis=0).astype(np.int64)
        confidence[full_valid_mask] = np.max(valid_probs, axis=0).astype(np.float32)

    probabilities[:, ~full_valid_mask] = 0.0
    return prediction, confidence, probabilities, full_valid_mask


class InferenceRunner:
    """Run SSRI geospatial inference from a trained checkpoint."""

    def __init__(self, config: InferenceConfig) -> None:
        self.config = config

    def run(self) -> InferenceResult:
        """Execute the inference pipeline and write geospatial outputs."""
        return run_inference(self.config)


def run_inference(config: InferenceConfig) -> InferenceResult:
    """Run SSRI inference and write prediction artifacts."""
    if config.mixed_precision and config.device == "cpu":
        raise InvalidInferenceConfigError(
            "mixed_precision cannot be enabled when device is cpu"
        )

    set_seed(42)
    started_at = datetime.now(timezone.utc)
    device = resolve_device(config.device)

    expected_identity: dict[str, str] | None = None
    manifest_payload = None
    if config.manifest.exists():
        from ssri_model.inference.metadata import load_manifest_payload

        manifest_payload = load_manifest_payload(config.manifest)
        dataset_name = manifest_payload.get("dataset_name")
        version = manifest_payload.get("version")
        if dataset_name is not None and version is not None:
            expected_identity = {
                "dataset_name": str(dataset_name),
                "version": str(version),
            }

    model, checkpoint_payload = load_inference_checkpoint(
        config.checkpoint,
        device=device,
        expected_dataset_identity=expected_identity,
    )
    context = validate_inference_setup(
        config,
        model=model,
        checkpoint_payload=checkpoint_payload,
    )

    features = _open_feature_memmap(config.features)
    if features.shape != context.feature_shape:
        raise InferenceError(
            "Feature stack shape changed after validation; "
            f"expected {context.feature_shape}, received {tuple(features.shape)}"
        )

    timer_start = time.perf_counter()
    prediction, confidence, probabilities, mask = _infer_windowed(
        model,
        features,
        context=context,
        config=config,
        device=device,
    )
    elapsed_seconds = time.perf_counter() - timer_start
    completed_at = datetime.now(timezone.utc)

    output_dir = config.output_path
    output_dir.mkdir(parents=True, exist_ok=True)

    prediction_path = save_prediction_raster(
        output_dir / "prediction.tif",
        prediction,
        grid=context.grid,
    )
    confidence_path = save_confidence_raster(
        output_dir / "confidence.tif",
        confidence,
        grid=context.grid,
    )
    probabilities_path = save_probability_raster(
        output_dir / "probabilities.tif",
        probabilities,
        grid=context.grid,
    )

    if config.save_individual_probability_bands:
        band_descriptions = (
            "subsidence_probability",
            "landslide_probability",
            "sinkhole_probability",
        )
        band_names = (
            "subsidence_probability.tif",
            "landslide_probability.tif",
            "sinkhole_probability.tif",
        )
        for band_index, (band_name, description) in enumerate(
            zip(band_names, band_descriptions, strict=True)
        ):
            save_class_probability_raster(
                output_dir / band_name,
                probabilities[band_index],
                grid=context.grid,
                description=description,
            )

    metadata_payload = build_inference_metadata(
        checkpoint_path=str(config.checkpoint),
        checkpoint_payload=checkpoint_payload,
        feature_path=str(config.features),
        manifest_path=str(config.manifest),
        statistics_path=str(config.statistics),
        feature_shape=context.feature_shape,
        grid=context.grid,
        config={
            "tile_size": config.tile_size,
            "overlap": config.overlap,
            "batch_size": config.batch_size,
            "mixed_precision": config.mixed_precision,
        },
        outputs={
            "prediction": str(prediction_path),
            "confidence": str(confidence_path),
            "probabilities": str(probabilities_path),
        },
        device=str(device),
        started_at=started_at,
        completed_at=completed_at,
        elapsed_seconds=elapsed_seconds,
    )
    metadata_path = write_inference_json(output_dir / INFERENCE_JSON_NAME, metadata_payload)

    return InferenceResult(
        prediction=prediction,
        confidence=confidence,
        probabilities=probabilities,
        mask=mask,
        prediction_path=prediction_path,
        confidence_path=confidence_path,
        probabilities_path=probabilities_path,
        metadata_path=metadata_path,
        elapsed_seconds=elapsed_seconds,
    )
