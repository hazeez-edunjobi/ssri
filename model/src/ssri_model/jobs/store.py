"""Filesystem-backed durable job store."""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from ssri_model.jobs.exceptions import JobNotFoundError
from ssri_model.jobs.models import JobRecord
from ssri_model.service.validation import reject_path_traversal, sanitize_request_id


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


class FileJobStore:
    """Persist job records under a configured root directory."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        return self._root

    def job_dir(self, job_id: str) -> Path:
        safe_id = sanitize_request_id(job_id)
        destination = (self._root / safe_id).resolve()
        try:
            destination.relative_to(self._root)
        except ValueError as exc:
            raise JobNotFoundError("Job not found") from exc
        return destination

    def job_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "job.json"

    def save(self, record: JobRecord) -> None:
        reject_path_traversal(record.job_id, field_name="job_id")
        _atomic_write_json(self.job_path(record.job_id), record.to_dict())

    def load(self, job_id: str) -> JobRecord:
        path = self.job_path(job_id)
        if not path.is_file():
            raise JobNotFoundError("Job not found")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return JobRecord.from_dict(payload)

    def save_result(self, job_id: str, result: dict[str, object]) -> None:
        _atomic_write_json(self.job_dir(job_id) / "result.json", result)

    def load_result(self, job_id: str) -> dict[str, object]:
        path = self.job_dir(job_id) / "result.json"
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return dict(payload) if isinstance(payload, dict) else {}

    @staticmethod
    def generate_job_id() -> str:
        return f"job-{secrets.token_hex(8)}"


# Backward-compatible alias used by Stage 3.3 code paths.
JobStore = FileJobStore
