"""Filesystem catalogue for geological datasets under ``{output_root}/geological``."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ssri_model.geological.ledger_lock import JsonlAppendLock
from ssri_model.geological.models import GeologicalDatasetRecord
from ssri_model.manual_training.exceptions import DatasetNotFoundError, UnsafePathError

_GEO_ID_RE = re.compile(r"^geo_[a-zA-Z0-9_-]{4,64}$")
_SAFE_FILE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._\-]{0,180}$")


def feature_application_identity(entry: dict[str, Any]) -> tuple[str, str, str, str]:
    """Stable identity for ledger deduplication (not filename-based)."""
    return (
        str(entry.get("application_id") or ""),
        str(entry.get("geo_id") or ""),
        str(entry.get("content_sha256") or ""),
        str(entry.get("target_dataset_id") or ""),
    )


class GeologicalStorage:
    """Immutable-id catalogue; originals are never overwritten."""

    def __init__(self, output_root: Path | str) -> None:
        self.root = Path(output_root).resolve() / "geological"
        self.datasets_dir = self.root / "datasets"
        self.index_path = self.root / "index.jsonl"
        self.feature_applications_path = self.root / "feature_applications.jsonl"
        self.feature_applications_lock_path = self.root / "feature_applications.lock"
        self.datasets_dir.mkdir(parents=True, exist_ok=True)

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def new_geo_id(self) -> str:
        return f"geo_{uuid.uuid4().hex[:12]}"

    def dataset_dir(self, geo_id: str) -> Path:
        if not _GEO_ID_RE.match(geo_id):
            raise DatasetNotFoundError(f"Unknown geological dataset id: {geo_id}")
        return self.datasets_dir / geo_id

    def _meta_path(self, geo_id: str) -> Path:
        return self.dataset_dir(geo_id) / "dataset.json"

    def safe_filename(self, name: str) -> str:
        base = Path(name or "upload.bin").name.replace(" ", "_")
        if not _SAFE_FILE_RE.match(base):
            suffix = Path(base).suffix[:20] if Path(base).suffix else ".bin"
            base = f"upload{suffix}"
        return base

    def create_shell(
        self,
        *,
        display_name: str,
        asset_kind: str = "point_grid_csv",
        description: str = "",
        source_client: str = "",
        notes: str = "",
        created_by_key_id: str | None = None,
    ) -> GeologicalDatasetRecord:
        geo_id = self.new_geo_id()
        root = self.dataset_dir(geo_id)
        (root / "original").mkdir(parents=True, exist_ok=True)
        (root / "working").mkdir(parents=True, exist_ok=True)
        record = GeologicalDatasetRecord(
            geo_id=geo_id,
            display_name=display_name.strip() or geo_id,
            asset_kind=asset_kind,  # type: ignore[arg-type]
            original_filename="",
            uploaded_at="",
            content_sha256="",
            original_relpath="",
            working_relpath="",
            description=description.strip(),
            source_client=source_client.strip(),
            notes=notes.strip(),
            created_by_key_id=created_by_key_id,
        )
        self.save(record)
        self.append_event(
            {
                "event": "created",
                "geo_id": geo_id,
                "at": self._utc_now(),
                "asset_kind": asset_kind,
            }
        )
        return record

    def save(self, record: GeologicalDatasetRecord) -> None:
        meta = self._meta_path(record.geo_id)
        meta.parent.mkdir(parents=True, exist_ok=True)
        tmp = meta.with_suffix(".tmp")
        tmp.write_text(json.dumps(record.to_storage_dict(), indent=2), encoding="utf-8")
        tmp.replace(meta)
        self._mirror_dataset(record.geo_id)

    def get(self, geo_id: str) -> GeologicalDatasetRecord:
        meta = self._meta_path(geo_id)
        if not meta.exists():
            self._materialize_dataset(geo_id)
        if not meta.exists():
            raise DatasetNotFoundError(f"Geological dataset not found: {geo_id}")
        return GeologicalDatasetRecord.from_dict(
            json.loads(meta.read_text(encoding="utf-8"))
        )

    def _mirror_dataset(self, geo_id: str) -> None:
        try:
            from ssri_model.storage.durable import (
                is_remote_object_backend,
                mirror_geological_dataset,
            )

            if not is_remote_object_backend():
                return
            mirror_geological_dataset(self.root, geo_id)
        except Exception:
            # Local catalogue remains authoritative; remote mirror is best-effort
            # unless configuration validation raises at the call site.
            return

    def _materialize_dataset(self, geo_id: str) -> None:
        try:
            from ssri_model.storage.durable import (
                ensure_geological_dataset_local,
                is_remote_object_backend,
            )

            if not is_remote_object_backend():
                return
            ensure_geological_dataset_local(self.root, geo_id)
        except Exception:
            return

    def list(
        self,
        *,
        measurement_type: str | None = None,
        activation_status: str | None = None,
        asset_kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[GeologicalDatasetRecord], int]:
        records: list[GeologicalDatasetRecord] = []
        if not self.datasets_dir.exists():
            return [], 0
        for child in sorted(self.datasets_dir.iterdir()):
            meta = child / "dataset.json"
            if not meta.exists():
                continue
            rec = GeologicalDatasetRecord.from_dict(
                json.loads(meta.read_text(encoding="utf-8"))
            )
            if measurement_type and rec.measurement_type != measurement_type:
                continue
            if activation_status and rec.activation_status != activation_status:
                continue
            if asset_kind and rec.asset_kind != asset_kind:
                continue
            records.append(rec)
        total = len(records)
        return records[offset : offset + limit], total

    def resolve_under(self, geo_id: str, relative: str) -> Path:
        base = self.dataset_dir(geo_id).resolve()
        candidate = (base / relative).resolve()
        try:
            candidate.relative_to(base)
        except ValueError as exc:
            raise UnsafePathError("Path must remain inside the geological dataset directory.") from exc
        return candidate

    def original_path(self, record: GeologicalDatasetRecord) -> Path | None:
        if not record.original_relpath:
            return None
        return self.resolve_under(record.geo_id, record.original_relpath)

    def working_path(self, record: GeologicalDatasetRecord) -> Path | None:
        if not record.working_relpath:
            return None
        return self.resolve_under(record.geo_id, record.working_relpath)

    def write_working_json(self, geo_id: str, name: str, payload: dict[str, Any]) -> Path:
        path = self.dataset_dir(geo_id) / "working" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def append_event(self, event: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")

    def _normalize_feature_application(self, entry: dict[str, Any]) -> dict[str, Any] | None:
        if entry.get("overall") != "PASS":
            return None
        geo_id = entry.get("geo_id")
        if not geo_id or not _GEO_ID_RE.match(str(geo_id)):
            raise UnsafePathError("Invalid geo_id for feature application provenance.")
        return {
            "application_id": str(entry.get("application_id") or ""),
            "geo_id": str(geo_id),
            "content_sha256": str(entry.get("content_sha256") or ""),
            "target_dataset_id": str(entry.get("target_dataset_id") or ""),
            "measurement_type": entry.get("measurement_type"),
            "channels": list(entry.get("channels") or []),
            "window_m": entry.get("window_m"),
            "processing_parameters": dict(entry.get("processing_parameters") or {}),
            "at": entry.get("at") or self._utc_now(),
            "overall": "PASS",
            "used_in_inference": False,
        }

    def record_feature_application(self, entry: dict[str, Any]) -> bool:
        """Append a successful offline feature-application provenance record.

        Identity: ``application_id`` + ``geo_id`` + ``content_sha256`` +
        ``target_dataset_id``. Duplicate identities are skipped (idempotent).
        Filename alone is never used as proof of application.
        Returns True when a new ledger line was written.
        """
        payload = self._normalize_feature_application(entry)
        if payload is None:
            return False
        identity = feature_application_identity(payload)
        self.root.mkdir(parents=True, exist_ok=True)
        with JsonlAppendLock(self.feature_applications_lock_path):
            existing = {
                feature_application_identity(row)
                for row in self._read_feature_application_rows()
            }
            if identity in existing:
                return False
            with self.feature_applications_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload) + "\n")
                handle.flush()
        self.append_event(
            {
                "event": "feature_application",
                "geo_id": payload["geo_id"],
                "at": payload["at"],
                "target_dataset_id": payload["target_dataset_id"],
                "content_sha256": payload["content_sha256"],
                "application_id": payload["application_id"],
            }
        )
        return True

    def _read_feature_application_rows(self) -> list[dict[str, Any]]:
        path = self.feature_applications_path
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def list_feature_applications(
        self,
        *,
        geo_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return persisted successful offline apply records (survives restart)."""
        rows: list[dict[str, Any]] = []
        for row in self._read_feature_application_rows():
            if row.get("overall") != "PASS":
                continue
            if geo_id and row.get("geo_id") != geo_id:
                continue
            rows.append(row)
        return rows

    def recover_feature_applications_from_report(
        self,
        report: dict[str, Any] | Path | str,
    ) -> dict[str, Any]:
        """Reconcile ledger entries from a durable PASS apply report.

        Only recovers when ``overall == PASS``. Never invents success from partial
        stack writes without a PASS report. Idempotent via application identity.
        Always forces ``used_in_inference`` to false on recovered rows.
        """
        if isinstance(report, (str, Path)):
            path = Path(report)
            if not path.exists():
                return {
                    "recovered": 0,
                    "skipped": 0,
                    "reason": "report_missing",
                    "used_in_inference": False,
                }
            payload = json.loads(path.read_text(encoding="utf-8"))
        else:
            payload = report

        if not isinstance(payload, dict) or payload.get("overall") != "PASS":
            return {
                "recovered": 0,
                "skipped": 0,
                "reason": "report_not_pass",
                "used_in_inference": False,
            }

        application_id = str(payload.get("application_id") or "")
        target_dataset_id = str(payload.get("target_dataset_id") or "")
        applied_at = str(payload.get("at") or self._utc_now())
        recovered = 0
        skipped = 0
        for step in payload.get("steps") or []:
            if not isinstance(step, dict):
                skipped += 1
                continue
            entry = {
                "application_id": application_id,
                "geo_id": step.get("geo_id"),
                "content_sha256": step.get("content_sha256"),
                "target_dataset_id": target_dataset_id,
                "measurement_type": step.get("measurement_type")
                or (step.get("channel") and "overburden_thickness"),
                "channels": list(
                    step.get("channels")
                    or ([step["channel"]] if step.get("channel") else [])
                ),
                "window_m": step.get("window_m"),
                "processing_parameters": {
                    "crs": step.get("crs"),
                    "column_mapping": step.get("column_mapping"),
                    "units_conversion": step.get("units_conversion"),
                    "recovered_from_report": True,
                },
                "at": applied_at,
                "overall": "PASS",
                "used_in_inference": False,
            }
            try:
                wrote = self.record_feature_application(entry)
            except UnsafePathError:
                skipped += 1
                continue
            if wrote:
                recovered += 1
            else:
                skipped += 1
        return {
            "recovered": recovered,
            "skipped": skipped,
            "application_id": application_id,
            "target_dataset_id": target_dataset_id,
            "used_in_inference": False,
            "reason": "ok",
        }

    def feature_application_status(self, record: GeologicalDatasetRecord) -> dict[str, Any]:
        """Derive used_in_feature_application from persisted provenance + sha256."""
        apps = self.list_feature_applications(geo_id=record.geo_id)
        if not apps:
            return {
                "used_in_feature_application": False,
                "feature_application_count": 0,
                "feature_applications": [],
                "feature_application_status": "never_applied",
            }
        matching = [
            a
            for a in apps
            if a.get("content_sha256")
            and record.content_sha256
            and a.get("content_sha256") == record.content_sha256
        ]
        # Prefer sha256-matched applications; fall back to geo_id history if sha empty.
        chosen = matching if matching else (
            apps if not record.content_sha256 else matching
        )
        return {
            "used_in_feature_application": bool(chosen),
            "feature_application_count": len(chosen),
            "feature_applications": chosen,
            "feature_application_status": (
                "applied" if chosen else "never_applied_for_current_bytes"
            ),
            "latest_feature_application_at": chosen[-1].get("at") if chosen else None,
            "latest_target_dataset_id": (
                chosen[-1].get("target_dataset_id") if chosen else None
            ),
        }
