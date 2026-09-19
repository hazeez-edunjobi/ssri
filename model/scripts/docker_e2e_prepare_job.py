"""Create Docker E2E inference fixtures and print JSON payload paths."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ssri_model.architecture import SSRIModelConfig, create_ssri_model
from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES
from ssri_model.ml.statistics_loader import compute_feature_statistics_from_arrays
from ssri_model.training import TrainingConfig
from ssri_model.training.checkpoint import save_checkpoint
from ssri_model.training.history import TrainingHistory
import torch


def main() -> None:
    root = Path("/data/outputs/e2e-job")
    root.mkdir(parents=True, exist_ok=True)
    height = width = 16
    tensor = np.stack(
        [np.full((height, width), float(i + 1), dtype=np.float64) for i in range(CHANNEL_COUNT)],
        axis=0,
    )
    feature = root / "features.npy"
    np.save(feature, tensor)

    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "package_version": "0.1.0",
                "created_at": "2026-09-07T00:00:00+00:00",
                "crs": "EPSG:4326",
                "projection": {
                    "transform": [0.01, 0.0, 3.0, 0.0, -0.01, 7.0],
                    "width": width,
                    "height": height,
                },
                "resolution_m": 30.0,
                "channels": [
                    {"index": i + 1, "name": name} for i, name in enumerate(CHANNEL_NAMES)
                ],
                "tensor_shape": [CHANNEL_COUNT, height, width],
            }
        ),
        encoding="utf-8",
    )

    stats = compute_feature_statistics_from_arrays([tensor])
    statistics = root / "statistics.json"
    statistics.write_text(
        json.dumps(
            {
                "channel_stats": {
                    name: {
                        "min": s.min,
                        "max": s.max,
                        "mean": s.mean,
                        "std": s.std,
                        "valid_count": s.valid_count,
                        "nodata_count": s.nodata_count,
                    }
                    for name, s in stats.channels.items()
                }
            }
        ),
        encoding="utf-8",
    )

    model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    checkpoint = root / "checkpoint.pt"
    save_checkpoint(
        path=checkpoint,
        model=model,
        optimizer=optimizer,
        scheduler=None,
        epoch=1,
        best_metric=0.5,
        best_metric_name="macro_f1",
        best_validation_loss=0.5,
        training_config=TrainingConfig(device="cpu"),
        model_config=model.config,
        history=TrainingHistory(),
        seed=42,
        dataset_manifest={"name": "e2e", "version": "0"},
    )

    payload = {
        "request_id": "docker-e2e-async-1",
        "checkpoint": str(checkpoint),
        "features": str(feature),
        "manifest": str(manifest),
        "statistics": str(statistics),
        "output_dir": str(root / "out"),
        "output_format": "all",
        "scientific_validation_status": "NOT_VALIDATED",
        "scientific_validation_required": False,
    }
    (root / "async_payload.json").write_text(json.dumps(payload), encoding="utf-8")
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
