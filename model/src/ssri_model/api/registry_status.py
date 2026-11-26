"""Public readiness helpers for the training model registry.

Exposes whether a promoted Stage 2.5 checkpoint is configured without revealing
server filesystem paths to anonymous clients.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ssri_model.manual_training.exceptions import ModelNotFoundError, UnsafePathError
from ssri_model.manual_training.registry import ModelRegistry
from ssri_model.manual_training.storage import TrainingStorage


def active_model_registry_status(output_root: str | Path) -> dict[str, Any]:
    """Return a safe summary of the promoted (active) training model."""
    storage = TrainingStorage(str(output_root))
    registry = ModelRegistry(storage)
    model_id = registry.get_active_model_id()
    if not model_id:
        return {
            "active_model_id": None,
            "checkpoint_available": False,
            "scientific_validation_status": None,
            "detail": "No promoted Stage 2.5 model is configured in the training registry.",
        }
    try:
        record = registry.get_model(model_id)
        checkpoint = Path(record.checkpoint_path)
        available = checkpoint.is_file()
        if not available and getattr(record, "object_storage_key", None):
            try:
                from ssri_model.storage.durable import resolve_checkpoint_path

                recovered = resolve_checkpoint_path(
                    local_path=checkpoint,
                    object_key=record.object_storage_key,
                    cache_dir=storage.models_dir / model_id / ".object_cache",
                )
                available = recovered.is_file()
            except Exception:
                available = False
        return {
            "active_model_id": model_id,
            "checkpoint_available": available,
            "scientific_validation_status": record.scientific_validation_status,
            "dataset_name": record.dataset_name,
            "detail": (
                "Promoted registry checkpoint is readable."
                if available
                else "Promoted model is selected but its checkpoint file is unavailable."
            ),
        }
    except (ModelNotFoundError, UnsafePathError, OSError, ValueError) as exc:
        return {
            "active_model_id": model_id,
            "checkpoint_available": False,
            "scientific_validation_status": None,
            "detail": f"Active registry entry could not be resolved ({type(exc).__name__}).",
        }
