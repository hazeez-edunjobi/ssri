"""Ingest zip archives or register existing Stage 2.5 dataset directories."""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

from ssri_model.manual_training.exceptions import (
    DatasetValidationFailed,
    ManualTrainingError,
    UnsafePathError,
)
from ssri_model.manual_training.storage import DatasetRecord, TrainingStorage
from ssri_model.manual_training.validation import DatasetPreview, validate_training_dataset

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MiB
ALLOWED_ZIP_SUFFIXES = {".zip"}


def _safe_extract_zip(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for info in archive.infolist():
        if info.is_dir():
            continue
        # Block absolute paths and traversal
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or name.startswith("\\") or ".." in Path(name).parts:
            raise UnsafePathError(
                f"Zip entry '{info.filename}' uses an unsafe path and was rejected."
            )
        target = (destination / name).resolve()
        try:
            target.relative_to(destination)
        except ValueError as exc:
            raise UnsafePathError(
                f"Zip entry '{info.filename}' would escape the dataset directory."
            ) from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, target.open("wb") as handle:
            shutil.copyfileobj(source, handle)


def _unwrap_single_root(data_root: Path) -> None:
    """If the zip contained one top-level folder, flatten it into data_root."""
    children = [path for path in data_root.iterdir() if path.name != "dataset.json"]
    if len(children) != 1 or not children[0].is_dir():
        return
    nested = children[0]
    # Only unwrap if nested looks like a dataset root
    if not (nested / "manifest.json").exists() and not (nested / "train").exists():
        return
    for item in nested.iterdir():
        shutil.move(str(item), str(data_root / item.name))
    nested.rmdir()


def ingest_zip_bytes(
    storage: TrainingStorage,
    dataset_id: str,
    *,
    filename: str,
    content: bytes,
) -> tuple[DatasetRecord, DatasetPreview]:
    """Extract a Stage 2.5 dataset zip into the dataset data directory."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_ZIP_SUFFIXES:
        raise ManualTrainingError(
            f"Unsupported upload type '{suffix or filename}'. "
            "Upload a .zip containing a Stage 2.5 dataset "
            "(manifest.json, statistics.json, train/, validation/).",
            code="UNSUPPORTED_UPLOAD",
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise ManualTrainingError(
            f"Upload is {len(content)} bytes; maximum allowed is {MAX_UPLOAD_BYTES} bytes.",
            code="UPLOAD_TOO_LARGE",
        )
    if not zipfile.is_zipfile(io.BytesIO(content)):
        raise ManualTrainingError(
            "The uploaded file is not a valid zip archive.",
            code="INVALID_ZIP",
        )

    record = storage.get_dataset(dataset_id)
    data_root = storage.clear_dataset_data(dataset_id)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        _safe_extract_zip(archive, data_root)
    _unwrap_single_root(data_root)

    preview = validate_training_dataset(data_root)
    record.validation_status = preview.validation_status
    record.validation_errors = list(preview.errors)
    record.preview = preview.to_dict()
    record.root_path = str(data_root)
    storage.save_dataset(record)
    return record, preview


def register_existing_path(
    storage: TrainingStorage,
    dataset_id: str,
    *,
    source_path: str,
) -> tuple[DatasetRecord, DatasetPreview]:
    """Point a dataset record at an existing on-disk Stage 2.5 dataset (copied)."""
    source = Path(source_path).expanduser().resolve()
    if not source.exists() or not source.is_dir():
        raise ManualTrainingError(
            f"Dataset path does not exist or is not a directory: {source}",
            code="SOURCE_NOT_FOUND",
        )
    record = storage.get_dataset(dataset_id)
    data_root = storage.clear_dataset_data(dataset_id)
    # Copy so later mutations stay under training storage
    for item in source.iterdir():
        dest = data_root / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    preview = validate_training_dataset(data_root)
    record.validation_status = preview.validation_status
    record.validation_errors = list(preview.errors)
    record.preview = preview.to_dict()
    record.root_path = str(data_root)
    storage.save_dataset(record)
    if preview.validation_status != "passed":
        raise DatasetValidationFailed(
            "Dataset was registered but failed validation.",
            errors=preview.errors,
        )
    return record, preview
