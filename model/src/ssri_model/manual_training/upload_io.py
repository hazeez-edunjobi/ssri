"""Disk-backed upload helpers — avoid holding entire payloads in RAM."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO

from ssri_model.manual_training.upload_limits import reject_if_upload_too_large


async def spool_upload_to_temp(
    upload: BinaryIO,
    *,
    suffix: str = "",
    chunk_size: int = 1024 * 1024,
) -> tuple[Path, int]:
    """Stream an UploadFile / file-like object to a NamedTemporaryFile on disk.

    Returns ``(path, bytes_written)``. Caller must delete the path when done.
    Enforces ``SSRI_UPLOAD_MAX_BYTES`` while streaming (stops early on overflow).
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    path = Path(tmp.name)
    written = 0
    try:
        while True:
            chunk = upload.read(chunk_size)
            if hasattr(chunk, "__await__"):
                chunk = await chunk  # type: ignore[misc]
            if not chunk:
                break
            written += len(chunk)
            reject_if_upload_too_large(written)
            tmp.write(chunk)
        tmp.flush()
    except Exception:
        tmp.close()
        path.unlink(missing_ok=True)
        raise
    else:
        tmp.close()
    return path, written


def copy_path_bytes(path: Path) -> bytes:
    """Read a spooled file into memory only when a caller still requires bytes."""
    return path.read_bytes()


def cleanup_temp(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def move_into(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
