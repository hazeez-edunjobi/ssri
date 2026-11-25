"""Durable artefact helpers shared by API and worker.

Local development keeps filesystem paths under ``SSRI_API_OUTPUT_ROOT``.
S3-compatible backends (including Cloudflare R2 / MinIO) store blobs under
stable object keys so separate Render services can share artefacts without a
shared disk.

When ``SSRI_OBJECT_STORAGE_BACKEND`` is ``r2``/``s3``/``minio``, write paths
mirror geological trees, training datasets, registry JSON, checkpoints and
assessment artefacts. Readers materialize missing local files from object
storage (backward compatible with filesystem-only records).
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any

from ssri_model.storage import ObjectStorage, build_object_storage_from_env

logger = logging.getLogger(__name__)


class IncompleteObjectStorageConfigError(ValueError):
    """Raised when R2/S3 configuration is incomplete or unsafe."""


def object_storage_backend() -> str:
    return (os.getenv("SSRI_OBJECT_STORAGE_BACKEND") or "local").strip().lower()


def is_remote_object_backend(backend: str | None = None) -> bool:
    return (backend or object_storage_backend()) in {"s3", "minio", "r2"}


def validate_object_storage_configuration(
    environ: dict[str, str] | None = None,
) -> list[str]:
    """Return actionable configuration errors (empty = OK). Never logs secrets."""
    env = environ if environ is not None else dict(os.environ)
    backend = (env.get("SSRI_OBJECT_STORAGE_BACKEND") or "local").strip().lower()
    errors: list[str] = []
    if backend == "local":
        return errors
    if backend not in {"s3", "minio", "r2"}:
        errors.append(
            f"Unsupported SSRI_OBJECT_STORAGE_BACKEND={backend!r}. "
            "Use local, s3, minio, or r2."
        )
        return errors
    if not (env.get("SSRI_OBJECT_STORAGE_BUCKET") or "").strip():
        errors.append(
            "SSRI_OBJECT_STORAGE_BUCKET is required when "
            f"SSRI_OBJECT_STORAGE_BACKEND={backend}."
        )
    if backend in {"r2", "minio"} and not (env.get("SSRI_OBJECT_STORAGE_ENDPOINT") or "").strip():
        errors.append(
            "SSRI_OBJECT_STORAGE_ENDPOINT is required for "
            f"{backend} (Cloudflare R2 S3 API URL or MinIO endpoint)."
        )
    access = (env.get("SSRI_OBJECT_STORAGE_ACCESS_KEY") or "").strip()
    secret = (env.get("SSRI_OBJECT_STORAGE_SECRET_KEY") or "").strip()
    if bool(access) ^ bool(secret):
        errors.append(
            "SSRI_OBJECT_STORAGE_ACCESS_KEY and SSRI_OBJECT_STORAGE_SECRET_KEY "
            "must both be set, or both left empty to use the ambient AWS credential chain."
        )
    return errors


def checkpoint_object_key(model_id: str, filename: str = "best.pt") -> str:
    safe_model = model_id.replace("\\", "/").strip("/")
    if ".." in safe_model.split("/"):
        raise ValueError("unsafe model_id for object key")
    safe_name = Path(filename).name
    return f"training/models/{safe_model}/{safe_name}"


def assessment_object_key(assessment_id: str, filename: str) -> str:
    return f"assessments/{assessment_id}/{Path(filename).name}"


def geological_dataset_prefix(geo_id: str) -> str:
    safe = geo_id.replace("\\", "/").strip("/")
    if ".." in safe.split("/"):
        raise ValueError("unsafe geo_id for object key")
    return f"geological/datasets/{safe}/"


def geological_ledger_key(name: str) -> str:
    return f"geological/{Path(name).name}"


def training_dataset_prefix(dataset_id: str) -> str:
    safe = dataset_id.replace("\\", "/").strip("/")
    if ".." in safe.split("/"):
        raise ValueError("unsafe dataset_id for object key")
    return f"training/datasets/{safe}/"


def registry_object_key(filename: str) -> str:
    return f"training/models/{Path(filename).name}"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _content_type_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    suffix = path.suffix.lower()
    if suffix in {".tif", ".tiff"}:
        return "image/tiff"
    if suffix == ".npy":
        return "application/octet-stream"
    if suffix == ".pt":
        return "application/octet-stream"
    if suffix == ".json":
        return "application/json"
    if suffix == ".jsonl":
        return "application/x-ndjson"
    if suffix == ".csv":
        return "text/csv"
    return "application/octet-stream"


def mirror_file_to_object_storage(
    path: Path,
    key: str,
    *,
    content_type: str,
    storage: ObjectStorage | None = None,
) -> dict[str, Any] | None:
    """Upload an immutable file when a remote backend is configured.

    Returns metadata including object key and sha256, or None for local backend.
    """
    if not is_remote_object_backend():
        return None
    errors = validate_object_storage_configuration()
    if errors:
        raise IncompleteObjectStorageConfigError("; ".join(errors))
    store = storage or build_object_storage_from_env()
    payload = path.read_bytes()
    digest = sha256_bytes(payload)
    stored_key = store.put_bytes(key, payload, content_type=content_type)
    logger.info(
        "mirrored_artefact key=%s bytes=%s sha256=%s",
        stored_key,
        len(payload),
        digest,
    )
    return {
        "object_key": stored_key,
        "sha256": digest,
        "bytes": len(payload),
        "backend": object_storage_backend(),
        "content_type": content_type,
    }


def materialize_object_to_path(
    key: str,
    destination: Path,
    *,
    storage: ObjectStorage | None = None,
) -> Path:
    """Download an object key to a local path (API/worker temp or registry cache)."""
    errors = validate_object_storage_configuration()
    if errors and is_remote_object_backend():
        raise IncompleteObjectStorageConfigError("; ".join(errors))
    store = storage or build_object_storage_from_env()
    payload = store.get_bytes(key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return destination


def resolve_checkpoint_path(
    *,
    local_path: str | Path | None,
    object_key: str | None = None,
    cache_dir: Path | None = None,
    storage: ObjectStorage | None = None,
) -> Path:
    """Resolve a checkpoint for inference: local file first, then object storage.

    Backward compatible with filesystem-only registry records.
    """
    if local_path:
        path = Path(local_path)
        if path.is_file():
            return path
    if object_key and (storage is not None or is_remote_object_backend()):
        cache = cache_dir or Path(tempfile.gettempdir()) / "ssri_checkpoints"
        dest = cache / object_key.replace("/", "_")
        if dest.is_file():
            return dest
        return materialize_object_to_path(object_key, dest, storage=storage)
    if local_path:
        raise FileNotFoundError(f"Checkpoint not found: {local_path}")
    raise FileNotFoundError("No checkpoint local path or object_key was provided")


def mirror_tree_to_object_storage(
    local_root: Path,
    key_prefix: str,
    *,
    storage: ObjectStorage | None = None,
) -> dict[str, Any] | None:
    """Recursively upload files under ``local_root`` to ``key_prefix/``."""
    if not is_remote_object_backend():
        return None
    errors = validate_object_storage_configuration()
    if errors:
        raise IncompleteObjectStorageConfigError("; ".join(errors))
    if not local_root.is_dir():
        return None
    store = storage or build_object_storage_from_env()
    prefix = key_prefix.replace("\\", "/").rstrip("/") + "/"
    uploaded = 0
    total_bytes = 0
    for path in sorted(local_root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        rel = path.relative_to(local_root).as_posix()
        key = f"{prefix}{rel}"
        payload = path.read_bytes()
        store.put_bytes(key, payload, content_type=_content_type_for(path))
        uploaded += 1
        total_bytes += len(payload)
    logger.info(
        "mirrored_tree prefix=%s files=%s bytes=%s",
        prefix,
        uploaded,
        total_bytes,
    )
    return {
        "prefix": prefix,
        "files": uploaded,
        "bytes": total_bytes,
        "backend": object_storage_backend(),
    }


def materialize_prefix_to_directory(
    key_prefix: str,
    local_root: Path,
    *,
    storage: ObjectStorage | None = None,
) -> int:
    """Download all objects under ``key_prefix`` into ``local_root``."""
    if not is_remote_object_backend() and storage is None:
        return 0
    errors = validate_object_storage_configuration()
    if errors and is_remote_object_backend():
        raise IncompleteObjectStorageConfigError("; ".join(errors))
    store = storage or build_object_storage_from_env()
    prefix = key_prefix.replace("\\", "/").rstrip("/") + "/"
    keys = store.list_prefix(prefix)
    count = 0
    for key in keys:
        if not key.startswith(prefix):
            continue
        rel = key[len(prefix) :]
        if not rel or ".." in rel.split("/"):
            continue
        dest = local_root / rel
        if dest.is_file():
            continue
        materialize_object_to_path(key, dest, storage=store)
        count += 1
    return count


def mirror_geological_dataset(
    geological_root: Path,
    geo_id: str,
    *,
    storage: ObjectStorage | None = None,
) -> dict[str, Any] | None:
    """Mirror one geological dataset tree plus catalogue ledgers when remote."""
    dataset_dir = Path(geological_root) / "datasets" / geo_id
    meta = mirror_tree_to_object_storage(
        dataset_dir, geological_dataset_prefix(geo_id), storage=storage
    )
    for ledger in ("index.jsonl", "feature_applications.jsonl"):
        path = Path(geological_root) / ledger
        if path.is_file():
            mirror_file_to_object_storage(
                path,
                geological_ledger_key(ledger),
                content_type="application/x-ndjson",
                storage=storage,
            )
    return meta


def ensure_geological_dataset_local(
    geological_root: Path,
    geo_id: str,
    *,
    storage: ObjectStorage | None = None,
) -> Path:
    """Ensure dataset.json exists locally, materializing from object storage if needed."""
    dataset_dir = Path(geological_root) / "datasets" / geo_id
    meta = dataset_dir / "dataset.json"
    if meta.is_file():
        return dataset_dir
    if not is_remote_object_backend() and storage is None:
        return dataset_dir
    materialize_prefix_to_directory(
        geological_dataset_prefix(geo_id), dataset_dir, storage=storage
    )
    return dataset_dir


def mirror_training_dataset(
    dataset_root: Path,
    dataset_id: str,
    *,
    storage: ObjectStorage | None = None,
) -> dict[str, Any] | None:
    return mirror_tree_to_object_storage(
        Path(dataset_root),
        training_dataset_prefix(dataset_id),
        storage=storage,
    )


def ensure_training_dataset_local(
    dataset_root: Path,
    dataset_id: str,
    *,
    storage: ObjectStorage | None = None,
) -> Path:
    root = Path(dataset_root)
    if (root / "manifest.json").is_file() or (root / "dataset.json").is_file():
        return root
    if not is_remote_object_backend() and storage is None:
        return root
    materialize_prefix_to_directory(
        training_dataset_prefix(dataset_id), root, storage=storage
    )
    return root


def mirror_registry_metadata(
    models_dir: Path,
    *,
    storage: ObjectStorage | None = None,
) -> None:
    """Mirror registry.json and active.json for split-host activation."""
    for name in ("registry.json", "active.json"):
        path = Path(models_dir) / name
        if path.is_file():
            mirror_file_to_object_storage(
                path,
                registry_object_key(name),
                content_type="application/json",
                storage=storage,
            )


def ensure_registry_metadata_local(
    models_dir: Path,
    *,
    storage: ObjectStorage | None = None,
) -> None:
    models = Path(models_dir)
    models.mkdir(parents=True, exist_ok=True)
    if not is_remote_object_backend() and storage is None:
        return
    for name in ("registry.json", "active.json"):
        dest = models / name
        if dest.is_file():
            continue
        key = registry_object_key(name)
        try:
            materialize_object_to_path(key, dest, storage=storage)
        except FileNotFoundError:
            continue


def mirror_assessment_payload(
    assess_dir: Path,
    assessment_id: str,
    *,
    storage: ObjectStorage | None = None,
) -> None:
    """Mirror assess_response.json and any GeoTIFF artefacts under the assessment."""
    assess = Path(assess_dir)
    if not assess.is_dir():
        return
    for path in assess.iterdir():
        if path.is_file() and path.suffix.lower() in {".json", ".tif", ".tiff"}:
            mirror_file_to_object_storage(
                path,
                assessment_object_key(assessment_id, path.name),
                content_type=_content_type_for(path),
                storage=storage,
            )
