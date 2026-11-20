"""Safe resolution of offline apply destinations under training storage."""

from __future__ import annotations

from pathlib import Path

from ssri_model.manual_training.exceptions import ManualTrainingError, UnsafePathError
from ssri_model.manual_training.storage import TrainingStorage


def resolve_offline_apply_target(
    training: TrainingStorage,
    *,
    target_dataset_id: str | None,
    target_dataset_root: str | None = None,
) -> tuple[str, Path]:
    """Resolve offline apply destination inside the training storage root.

    Requires a registered ``target_dataset_id``. Arbitrary host paths are rejected.
    Optional ``target_dataset_root`` is accepted only when it resolves to the same
    registered dataset data directory (compat check) — never as a free-form write path.
    """
    if not target_dataset_id or not str(target_dataset_id).strip():
        raise ManualTrainingError(
            "Provide target_dataset_id for a registered Stage 2.5 training dataset. "
            "Arbitrary filesystem destinations are not accepted.",
            code="APPLY_TARGET_ID_REQUIRED",
        )
    dataset_id = str(target_dataset_id).strip()
    if (
        ".." in dataset_id
        or "/" in dataset_id
        or "\\" in dataset_id
        or Path(dataset_id).is_absolute()
    ):
        raise UnsafePathError(
            "target_dataset_id must be a registered dataset id, not a filesystem path."
        )

    ds = training.get_dataset(dataset_id)
    target_root = training.resolve_under_training(ds.root_path)

    datasets_root = training.datasets_dir.resolve()
    try:
        target_root.relative_to(datasets_root)
    except ValueError as exc:
        raise UnsafePathError(
            "Resolved apply target must remain under the training datasets directory."
        ) from exc

    if target_dataset_root:
        candidate = training.resolve_under_training(target_dataset_root)
        if candidate != target_root:
            raise UnsafePathError(
                "target_dataset_root does not match the registered dataset path "
                "for target_dataset_id. Use target_dataset_id only."
            )

    return dataset_id, target_root
