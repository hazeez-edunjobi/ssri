"""Geological catalogue persistence strategy helpers.

The live ``GeologicalStorage`` implementation is a **filesystem working cache**
under ``{SSRI_API_OUTPUT_ROOT}/geological``.

When ``SSRI_OBJECT_STORAGE_BACKEND`` is ``r2`` / ``s3`` / ``minio``, dataset
trees and ledgers are mirrored to object storage after writes and materialized
on read when the local cache is empty — enabling API and worker hosts to share
catalogue artefacts without a shared disk.

``SSRI_GEOLOGICAL_STORAGE_BACKEND=r2|s3|minio|object`` remains refused: those
values would imply a pure object catalogue without the FS working cache and
JSONL append locks. Use filesystem (default) plus a remote ``SSRI_OBJECT_STORAGE_*``
backend for durable split-host deployments.
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
            f"{backend!r} is not supported. "
            "Keep filesystem mode and set SSRI_OBJECT_STORAGE_BACKEND=r2|s3|minio "
            "so GeologicalStorage mirrors dataset trees and ledgers to object storage."
        )
    if backend not in SUPPORTED_BACKENDS:
        raise InvalidServiceConfigError(
            f"Unknown SSRI_GEOLOGICAL_STORAGE_BACKEND={backend!r}. "
            "Supported: filesystem (default)."
        )
    return GeologicalStorage(output_root)
