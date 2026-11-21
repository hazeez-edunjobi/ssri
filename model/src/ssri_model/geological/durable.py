"""Geological catalogue persistence strategy helpers.

The live ``GeologicalStorage`` implementation is a **local filesystem** catalogue
under ``{SSRI_API_OUTPUT_ROOT}/geological``. That design requires a durable
mount (Compose volume or Render persistent disk) for production survival across
redeploys.

Existing ``ObjectStorage`` (local / S3 / R2) is used for assess GeoTIFF artifacts
and only recently gained ``get_bytes``. It still lacks:

* prefix listing for catalogue discovery
* atomic compare-and-swap / conditional writes for ``dataset.json``
* append-safe JSONL ledgers with distributed locks
* path-based ``FileResponse`` / offline-apply readers used by the API and worker

Storing only original CSVs in R2 while leaving ``dataset.json``, ``index.jsonl``,
and ``feature_applications.jsonl`` on ephemeral disk is **unsafe** and is
explicitly refused.

Supported production path today: ``SSRI_GEOLOGICAL_STORAGE_BACKEND=filesystem``
(default) with a durable ``SSRI_API_OUTPUT_ROOT`` shared by API and worker.
"""

from __future__ import annotations

import os
from pathlib import Path

from ssri_model.geological.storage import GeologicalStorage
from ssri_model.service.exceptions import InvalidServiceConfigError

SUPPORTED_BACKENDS = frozenset({"filesystem", "local", "fs", ""})
REFUSED_OBJECT_BACKENDS = frozenset({"r2", "s3", "minio", "object", "objects"})


def geological_storage_backend() -> str:
    return os.getenv("SSRI_GEOLOGICAL_STORAGE_BACKEND", "filesystem").strip().lower()


def write_bytes_atomic(path: Path | str, content: bytes) -> Path:
    """Write bytes via a same-directory temp file then ``replace`` (atomic on POSIX)."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(f".{destination.name}.tmp")
    tmp.write_bytes(content)
    tmp.replace(destination)
    return destination


def build_geological_storage(output_root: Path | str) -> GeologicalStorage:
    """Construct catalogue storage or refuse incomplete object-backend modes."""
    backend = geological_storage_backend()
    if backend in REFUSED_OBJECT_BACKENDS:
        raise InvalidServiceConfigError(
            "SSRI_GEOLOGICAL_STORAGE_BACKEND="
            f"{backend!r} is not supported yet. "
            "A complete R2/S3 geological catalogue needs list_prefix, get_bytes, "
            "conditional metadata writes, and distributed ledger locks — beyond "
            "the current ObjectStorage contract used for assess artifacts. "
            "Use filesystem mode with a durable SSRI_API_OUTPUT_ROOT "
            "(Render persistent disk shared by API and worker), or leave "
            "SSRI_GEOLOGICAL_STORAGE_BACKEND unset."
        )
    if backend not in SUPPORTED_BACKENDS:
        raise InvalidServiceConfigError(
            f"Unknown SSRI_GEOLOGICAL_STORAGE_BACKEND={backend!r}. "
            "Supported: filesystem (default)."
        )
    return GeologicalStorage(output_root)
