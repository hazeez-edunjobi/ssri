"""Configurable upload size limits (rows, bytes, ZIP expansion).

``SSRI_UPLOAD_MAX_ROWS``
    Optional positive integer. Empty / unset = no row limit (default).

``SSRI_UPLOAD_MAX_BYTES``
    Optional positive integer payload ceiling. Empty / unset = **no application-level
    byte cap** (default). Infrastructure (proxies, disk) may still limit uploads —
    set this when you need an explicit app-level backstop.

``SSRI_UPLOAD_MAX_UNCOMPRESSED_BYTES``
    Maximum total uncompressed ZIP payload. Default ``53687091200`` (50 GiB).
    Guards ZIP bombs even when the compressed upload has no byte cap.

``SSRI_UPLOAD_MAX_ZIP_FILES``
    Maximum number of files inside a ZIP. Default ``100000``.

``SSRI_UPLOAD_MAX_COMPRESSION_RATIO``
    Reject ZIPs whose uncompressed/compressed ratio exceeds this. Default ``200``.
"""

from __future__ import annotations

import os

# ZIP expansion safeguards (not an arbitrary "file must be < 1 GiB" product rule).
DEFAULT_UPLOAD_MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024 * 1024  # 50 GiB
DEFAULT_UPLOAD_MAX_ZIP_FILES = 100_000
DEFAULT_UPLOAD_MAX_COMPRESSION_RATIO = 200.0


def _positive_int_env(name: str, default: int | None) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer, got {raw!r}.") from exc
    if value < 1:
        raise ValueError(f"{name} must be at least 1.")
    return value


def upload_max_rows() -> int | None:
    """Return the CSV row cap, or ``None`` when unlimited."""
    return _positive_int_env("SSRI_UPLOAD_MAX_ROWS", None)


def upload_max_bytes() -> int | None:
    """Return the upload byte ceiling, or ``None`` when no application-level cap."""
    return _positive_int_env("SSRI_UPLOAD_MAX_BYTES", None)


def upload_max_uncompressed_bytes() -> int:
    """Return the ZIP uncompressed-byte ceiling (ZIP-bomb guard)."""
    value = _positive_int_env(
        "SSRI_UPLOAD_MAX_UNCOMPRESSED_BYTES", DEFAULT_UPLOAD_MAX_UNCOMPRESSED_BYTES
    )
    assert value is not None
    return value


def upload_max_zip_files() -> int:
    value = _positive_int_env("SSRI_UPLOAD_MAX_ZIP_FILES", DEFAULT_UPLOAD_MAX_ZIP_FILES)
    assert value is not None
    return value


def upload_max_compression_ratio() -> float:
    raw = os.environ.get("SSRI_UPLOAD_MAX_COMPRESSION_RATIO", "").strip()
    if not raw:
        return DEFAULT_UPLOAD_MAX_COMPRESSION_RATIO
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(
            f"SSRI_UPLOAD_MAX_COMPRESSION_RATIO must be a positive number, got {raw!r}."
        ) from exc
    if value < 1.0:
        raise ValueError("SSRI_UPLOAD_MAX_COMPRESSION_RATIO must be at least 1.")
    return value


def reject_if_upload_too_large(size: int) -> None:
    """Raise ``ManualTrainingError`` with code ``UPLOAD_TOO_LARGE`` when over the byte cap.

    No-op when ``SSRI_UPLOAD_MAX_BYTES`` is unset (no application-level cap).
    """
    from ssri_model.manual_training.exceptions import ManualTrainingError

    limit = upload_max_bytes()
    if limit is None:
        return
    if size > limit:
        limit_mb = max(1, limit // (1024 * 1024))
        size_mb = max(1, size // (1024 * 1024))
        raise ManualTrainingError(
            f"That file is too large ({size_mb} MB). "
            f"The configured maximum upload size is {limit_mb} MB "
            f"(SSRI_UPLOAD_MAX_BYTES). "
            "Split the dataset, free disk, or raise the configured limit.",
            code="UPLOAD_TOO_LARGE",
        )


def reject_if_zip_expansion_unsafe(
    *,
    compressed_size: int,
    uncompressed_size: int,
    file_count: int,
) -> None:
    """Reject ZIP bombs / runaway expansion while allowing large legitimate archives."""
    from ssri_model.manual_training.exceptions import ManualTrainingError

    if file_count > upload_max_zip_files():
        raise ManualTrainingError(
            f"That zip contains {file_count} files; the maximum allowed is "
            f"{upload_max_zip_files()}.",
            code="ZIP_TOO_MANY_FILES",
        )
    max_uncomp = upload_max_uncompressed_bytes()
    if uncompressed_size > max_uncomp:
        uncomp_gb = uncompressed_size / (1024**3)
        limit_gb = max_uncomp / (1024**3)
        raise ManualTrainingError(
            f"That zip expands to about {uncomp_gb:.1f} GiB of data; "
            f"the maximum allowed expanded size is {limit_gb:.1f} GiB "
            f"(SSRI_UPLOAD_MAX_UNCOMPRESSED_BYTES).",
            code="ZIP_TOO_LARGE_EXPANDED",
        )
    if compressed_size > 0:
        ratio = uncompressed_size / float(compressed_size)
        max_ratio = upload_max_compression_ratio()
        if ratio > max_ratio:
            raise ManualTrainingError(
                f"That zip expands by about {ratio:.0f}×, which exceeds the "
                f"safe compression ratio of {max_ratio:.0f}× "
                f"(SSRI_UPLOAD_MAX_COMPRESSION_RATIO). "
                "This usually means a malicious or corrupt archive.",
                code="ZIP_BOMB",
            )
