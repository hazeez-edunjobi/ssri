"""Filesystem layout for manual training datasets, runs, and models."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ssri_model.manual_training.exceptions import DatasetNotFoundError, UnsafePathError

_DATASET_ID_RE = re.compile(r"^ds_[a-zA-Z0-9_-]{4,64}$")
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,120}$")


@dataclass
class DatasetRecord:
    dataset_id: str
    name: str
    description: str
    hazard_notes: str
    geographic_area: str
    data_source: str
    notes: str
    created_at: str
    root_path: str
    validation_status: str = "pending"
    validation_errors: list[str] = field(default_factory=list)
    preview: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DatasetRecord:
        return cls(
            dataset_id=str(payload["dataset_id"]),
            name=str(payload["name"]),
            description=str(payload.get("description", "")),
            hazard_notes=str(payload.get("hazard_notes", "")),
            geographic_area=str(payload.get("geographic_area", "")),
            data_source=str(payload.get("data_source", "")),
            notes=str(payload.get("notes", "")),
            created_at=str(payload["created_at"]),
            root_path=str(payload["root_path"]),
            validation_status=str(payload.get("validation_status", "pending")),
            validation_errors=list(payload.get("validation_errors") or []),
            preview=dict(payload.get("preview") or {}),
        )


class TrainingStorage:
    """Keeps uploaded datasets, run artifacts, and model registry under output_root."""

    def __init__(self, output_root: Path | str) -> None:
        self.root = Path(output_root).resolve() / "training"
        self.datasets_dir = self.root / "datasets"
        self.runs_dir = self.root / "runs"
        self.models_dir = self.root / "models"
        self.uploads_dir = self.root / "uploads"
        for path in (
            self.datasets_dir,
            self.runs_dir,
            self.models_dir,
            self.uploads_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _new_dataset_id(self) -> str:
        return f"ds_{uuid.uuid4().hex[:12]}"

    def _dataset_meta_path(self, dataset_id: str) -> Path:
        return self.datasets_dir / dataset_id / "dataset.json"

    def create_dataset(
        self,
        *,
        name: str,
        description: str = "",
        hazard_notes: str = "",
        geographic_area: str = "",
        data_source: str = "",
        notes: str = "",
    ) -> DatasetRecord:
        clean_name = name.strip()
        if not clean_name or not _SAFE_NAME_RE.match(clean_name.replace(" ", "-")):
            # Allow spaces in display name but require non-empty
            if not clean_name or len(clean_name) > 120:
                raise UnsafePathError("Dataset name must be 1–120 characters.")
        dataset_id = self._new_dataset_id()
        dataset_root = self.datasets_dir / dataset_id / "data"
        dataset_root.mkdir(parents=True, exist_ok=True)
        record = DatasetRecord(
            dataset_id=dataset_id,
            name=clean_name,
            description=description.strip(),
            hazard_notes=hazard_notes.strip(),
            geographic_area=geographic_area.strip(),
            data_source=data_source.strip(),
            notes=notes.strip(),
            created_at=self._utc_now(),
            root_path=str(dataset_root),
        )
        self.save_dataset(record)
        return record

    def save_dataset(self, record: DatasetRecord) -> None:
        meta = self._dataset_meta_path(record.dataset_id)
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")

    def get_dataset(self, dataset_id: str) -> DatasetRecord:
        if not _DATASET_ID_RE.match(dataset_id):
            raise DatasetNotFoundError(f"Unknown dataset id: {dataset_id}")
        meta = self._dataset_meta_path(dataset_id)
        if not meta.exists():
            raise DatasetNotFoundError(f"Dataset not found: {dataset_id}")
        return DatasetRecord.from_dict(json.loads(meta.read_text(encoding="utf-8")))

    def list_datasets(self) -> list[DatasetRecord]:
        records: list[DatasetRecord] = []
        if not self.datasets_dir.exists():
            return records
        for child in sorted(self.datasets_dir.iterdir()):
            meta = child / "dataset.json"
            if meta.exists():
                records.append(
                    DatasetRecord.from_dict(json.loads(meta.read_text(encoding="utf-8")))
                )
        return records

    def resolve_under_training(self, path: Path | str) -> Path:
        """Resolve a path and ensure it stays inside the training root."""
        candidate = Path(path).resolve()
        root = self.root.resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise UnsafePathError(
                "Path must remain inside the SSRI training storage directory."
            ) from exc
        return candidate

    def run_dir(self, run_id: str) -> Path:
        path = self.runs_dir / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def progress_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "progress.json"

    def write_progress(self, run_id: str, payload: dict[str, Any]) -> None:
        path = self.progress_path(run_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    def read_progress(self, run_id: str) -> dict[str, Any] | None:
        path = self.progress_path(run_id)
        if not path.exists():
            return None
        try:
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                return None
            return json.loads(text)
        except (json.JSONDecodeError, OSError):
            return None

    def clear_dataset_data(self, dataset_id: str) -> Path:
        record = self.get_dataset(dataset_id)
        data_root = Path(record.root_path)
        if data_root.exists():
            shutil.rmtree(data_root)
        data_root.mkdir(parents=True, exist_ok=True)
        return data_root
