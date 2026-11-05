"""Configurable upload size limits (rows and bytes).

``SSRI_UPLOAD_MAX_ROWS``
    Optional positive integer. Empty / unset = no row limit (default).

``SSRI_UPLOAD_MAX_BYTES``
    Maximum upload payload size in bytes. Default ``1073741824`` (1 GiB).
"""

from __future__ import annotations

import os

# Default byte ceiling: generous enough for large Stage 2.5 / CSV uploads,
# but prevents unbounded disk/memory fill. Override with SSRI_UPLOAD_MAX_BYTES.
DEFAULT_UPLOAD_MAX_BYTES = 1 * 1024 * 1024 * 1024  # 1 GiB


def upload_max_rows() -> int | None:
    """Return the CSV row cap, or ``None`` when unlimited."""
    raw = os.environ.get("SSRI_UPLOAD_MAX_ROWS", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(
            f"SSRI_UPLOAD_MAX_ROWS must be a positive integer, got {raw!r}."
        ) from exc
    if value < 1:
        raise ValueError("SSRI_UPLOAD_MAX_ROWS must be at least 1.")
    return value


def upload_max_bytes() -> int:
    """Return the upload byte ceiling (default 1 GiB)."""
    raw = os.environ.get("SSRI_UPLOAD_MAX_BYTES", "").strip()
    if not raw:
        return DEFAULT_UPLOAD_MAX_BYTES
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(
            f"SSRI_UPLOAD_MAX_BYTES must be a positive integer, got {raw!r}."
        ) from exc
    if value < 1:
        raise ValueError("SSRI_UPLOAD_MAX_BYTES must be at least 1.")
    return value


def reject_if_upload_too_large(size: int) -> None:
    """Raise ``ManualTrainingError`` with code ``UPLOAD_TOO_LARGE`` when over the byte cap."""
    from ssri_model.manual_training.exceptions import ManualTrainingError

    limit = upload_max_bytes()
    if size > limit:
        limit_mb = max(1, limit // (1024 * 1024))
        size_mb = max(1, size // (1024 * 1024))
        raise ManualTrainingError(
            f"That file is too large ({size_mb} MB). "
            f"The maximum upload size is {limit_mb} MB. "
            "Split the dataset or raise SSRI_UPLOAD_MAX_BYTES if you intend a larger upload.",
            code="UPLOAD_TOO_LARGE",
        )
