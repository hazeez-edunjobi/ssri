"""Register a local Stage 2.5 checkpoint for pipeline testing.

Copies an existing 13-channel Stage 2.5-format ``best.pt`` into
``SSRI_API_OUTPUT_ROOT`` / training registry and optionally activates it.

This does NOT claim scientific validation. Synthetic / rehearsal weights remain
``NOT_VALIDATED``. Prefer owner-trained checkpoints when available.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DEFAULT_SOURCES = [
    ROOT
    / "model/outputs/rehearsal_300k_shell/service-outputs/training/models/ssri-model-153f09d946/best.pt",
    ROOT
    / "model/outputs/upload_cap_shell/service-outputs/training/models/ssri-model-2e91993348/best.pt",
    ROOT
    / "poc/release_shell/outputs/acceptance_tmp/service-outputs/training/models/ssri-model-4c809fca35/best.pt",
]


def _require_torch_load(path: Path) -> dict:
    import torch

    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, dict) or "model_state_dict" not in payload:
        raise SystemExit(f"Not a Stage 2.5 assess checkpoint (missing model_state_dict): {path}")
    cfg = payload.get("model_config") or {}
    channels = int(cfg.get("in_channels") or 0)
    if channels != 13:
        raise SystemExit(
            f"Refuse non-13-channel checkpoint (in_channels={channels}). "
            "Live Stage 2.5 assess requires 13 channels."
        )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Path to a 13-channel Stage 2.5 best.pt (default: first local synthetic found)",
    )
    parser.add_argument(
        "--activate",
        action="store_true",
        help="Write active.json so /api/v1/ready reports checkpoint_available",
    )
    parser.add_argument(
        "--name",
        default="LOCAL-PIPELINE-SYNTHETIC-13CH",
        help="Registry display name (must not imply scientific validation)",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT / "model" / "src"))
    from ssri_model.manual_training.registry import ModelRecord, ModelRegistry
    from ssri_model.manual_training.storage import TrainingStorage

    ckpt = args.checkpoint
    if ckpt is None:
        ckpt = next((p for p in DEFAULT_SOURCES if p.is_file()), None)
    if ckpt is None or not ckpt.is_file():
        raise SystemExit(
            "No 13-channel Stage 2.5 best.pt found. Train locally or pass --checkpoint."
        )

    payload = _require_torch_load(ckpt)
    output_root = Path(
        os.getenv("SSRI_API_OUTPUT_ROOT") or (ROOT / "data" / "outputs")
    ).resolve()
    storage = TrainingStorage(output_root)
    registry = ModelRegistry(storage)

    model_id = f"ssri-model-{uuid.uuid4().hex[:10]}"
    dest_dir = storage.models_dir / model_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "best.pt"
    shutil.copy2(ckpt, dest)

    manifest = payload.get("dataset_manifest") or {}
    dataset_name = (
        manifest.get("name")
        if isinstance(manifest, dict)
        else None
    ) or "SYNTHETIC-local-bootstrap"

    record = ModelRecord(
        model_id=model_id,
        name=args.name,
        created_at=datetime.now(timezone.utc).isoformat(),
        dataset_id="ds_local_bootstrap",
        dataset_name=str(dataset_name),
        checkpoint_path=str(dest.resolve()),
        experiment_dir=str(dest_dir.resolve()),
        job_id=None,
        training_metrics={"source_checkpoint": str(ckpt)},
        evaluation_status="bootstrap_copy_only",
        scientific_validation_status="NOT_VALIDATED",
        active=False,
        notes=(
            "Local bootstrap copy for pipeline testing only. "
            "NOT scientifically validated. Replace with owner-trained Stage 2.5 weights."
        ),
    )
    index = registry._load_index()  # noqa: SLF001 — bootstrap helper
    models = [item for item in index.get("models", []) if item.get("model_id") != model_id]
    models.append(record.to_dict())
    index["models"] = models
    registry._save_index(index)  # noqa: SLF001

    if args.activate:
        registry.activate(model_id)

    print(json.dumps(
        {
            "model_id": model_id,
            "checkpoint_path": str(dest),
            "scientific_validation_status": "NOT_VALIDATED",
            "activated": bool(args.activate),
            "in_channels": 13,
            "source": str(ckpt),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
