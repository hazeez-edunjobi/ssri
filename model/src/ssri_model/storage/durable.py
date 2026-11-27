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


# Lagos engineering clips mirrored to the shared production bucket. Keys must
# match the uploaded R2 objects exactly. Digests are the verified local files;
# materialization never uploads or overwrites remote objects.
GEOPHYSICS_PROCESSED_PREFIX = "geophysics/processed/"
REQUIRED_GEOPHYSICS_ASSETS: tuple[dict[str, str | int], ...] = (
    {
        "filename": "lagos_gravity_wgm2012_bouguer.tif",
        "object_key": "geophysics/processed/lagos_gravity_wgm2012_bouguer.tif",
        "expected_sha256": (
            "1dd310bece474230a938002c80f9a78d44a37e0e9eaf677ca0e347a5d8c377a6"
        ),
        "expected_bytes": 14113,
    },
    {
        "filename": "lagos_magnetic_emag2v3_uc4km.tif",
        "object_key": "geophysics/processed/lagos_magnetic_emag2v3_uc4km.tif",
        "expected_sha256": (
            "0d28e751a2d6ffda8f6480ce5e6e20ff2d6ca0b07db38161bd3c7e710b48736d"
        ),
        "expected_bytes": 15166,
    },
)


def geophysics_object_key(filename: str) -> str:
    """Stable object key for a processed geophysics GeoTIFF."""
    name = Path(filename).name
    if not name or ".." in name:
        raise ValueError("unsafe geophysics filename for object key")
    return f"{GEOPHYSICS_PROCESSED_PREFIX}{name}"


def geophysics_processed_dir() -> Path:
    """Local directory for materialized geophysics GeoTIFFs.

    Production contract: ``/data/geophysics/processed`` (same tree as
    ``SSRI_API_OUTPUT_ROOT=/data/outputs``). Relative/dev checkouts fall back
    to ``SSRI_DATA_ROOT`` or the repository ``data/geophysics/processed``.
    """
    explicit = (os.getenv("SSRI_GEOPHYSICS_PROCESSED_DIR") or "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    data_root = (os.getenv("SSRI_DATA_ROOT") or "").strip()
    if data_root:
        return (Path(data_root).expanduser().resolve() / "geophysics" / "processed")
    container = Path("/data/geophysics/processed")
    if Path("/data").is_dir():
        return container
    # model/src/ssri_model/storage/durable.py → repo root is parents[4]
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data" / "geophysics" / "processed"
        if candidate.is_dir() or (parent / "infra").is_dir():
            return candidate
    return container


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


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
    overwrite: bool = True,
) -> dict[str, Any] | None:
    """Upload an immutable file when a remote backend is configured.

    Returns metadata including object key and sha256, or None for local backend.
    When ``overwrite`` is False and the object already exists, the upload is skipped.
    """
    if not is_remote_object_backend():
        return None
    errors = validate_object_storage_configuration()
    if errors:
        raise IncompleteObjectStorageConfigError("; ".join(errors))
    store = storage or build_object_storage_from_env()
    if not overwrite and store.exists(key):
        logger.info("mirror_skip_existing key=%s", key)
        return {
            "object_key": key,
            "sha256": None,
            "bytes": None,
            "backend": object_storage_backend(),
            "content_type": content_type,
            "skipped_existing": True,
        }
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
        "skipped_existing": False,
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


def discover_remote_geological_dataset_ids(
    *,
    storage: ObjectStorage | None = None,
) -> list[str]:
    """List geo_id values that have ``dataset.json`` under the geological object prefix.

    Used so catalogue ``list()`` can materialize metadata after Render restarts
    when the local FS cache is empty but R2/S3 still holds the datasets.
    """
    if not is_remote_object_backend() and storage is None:
        return []
    errors = validate_object_storage_configuration()
    if errors and is_remote_object_backend():
        raise IncompleteObjectStorageConfigError("; ".join(errors))
    store = storage or build_object_storage_from_env()
    prefix = "geological/datasets/"
    ids: set[str] = set()
    for key in store.list_prefix(prefix):
        if not key.startswith(prefix):
            continue
        rest = key[len(prefix) :]
        parts = rest.split("/")
        if len(parts) < 2:
            continue
        geo_id, *tail = parts
        if not geo_id.startswith("geo_"):
            continue
        if tail and tail[-1] == "dataset.json":
            ids.add(geo_id)
        elif len(tail) == 1 and tail[0] == "dataset.json":
            ids.add(geo_id)
    return sorted(ids)


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


def _validate_geophysics_geotiff(path: Path) -> dict[str, Any]:
    """Confirm a materialized file is a single-band GeoTIFF with CRS metadata."""
    import rasterio

    with rasterio.open(path) as dataset:
        if dataset.count < 1:
            raise ValueError(f"{path.name} has no raster bands")
        if dataset.crs is None:
            raise ValueError(f"{path.name} is missing CRS metadata")
        return {
            "bands": int(dataset.count),
            "crs": str(dataset.crs),
            "dtype": str(dataset.dtypes[0]),
            "nodata": (
                float(dataset.nodata) if dataset.nodata is not None else None
            ),
            "width": int(dataset.width),
            "height": int(dataset.height),
        }


def _asset_local_ok(path: Path, *, expected_sha256: str, expected_bytes: int) -> bool:
    if not path.is_file():
        return False
    size = path.stat().st_size
    if expected_bytes and size != int(expected_bytes):
        return False
    return sha256_file(path) == expected_sha256


def ensure_geophysics_assets_local(
    *,
    storage: ObjectStorage | None = None,
    processed_dir: Path | None = None,
) -> dict[str, Any]:
    """Idempotently materialize required geophysics GeoTIFFs under ``/data/geophysics/processed``.

    Downloads missing or digest-mismatched files from object storage. Never
    uploads or overwrites remote objects. Safe to call on every API/worker
    startup and on ``/ready``.
    """
    root = Path(processed_dir) if processed_dir is not None else geophysics_processed_dir()
    root.mkdir(parents=True, exist_ok=True)
    remote = is_remote_object_backend() or storage is not None
    assets: list[dict[str, Any]] = []
    materialized = 0
    errors: list[str] = []

    for spec in REQUIRED_GEOPHYSICS_ASSETS:
        filename = str(spec["filename"])
        object_key = str(spec["object_key"])
        expected_sha = str(spec["expected_sha256"])
        expected_bytes = int(spec["expected_bytes"])
        dest = root / filename
        entry: dict[str, Any] = {
            "filename": filename,
            "object_key": object_key,
            "path_basename": filename,
            "present": False,
            "sha256_ok": False,
            "valid_geotiff": False,
            "materialized": False,
            "bytes": None,
            "detail": "",
        }
        try:
            if _asset_local_ok(
                dest, expected_sha256=expected_sha, expected_bytes=expected_bytes
            ):
                meta = _validate_geophysics_geotiff(dest)
                entry.update(
                    {
                        "present": True,
                        "sha256_ok": True,
                        "valid_geotiff": True,
                        "bytes": dest.stat().st_size,
                        "raster": meta,
                        "detail": "local cache matches expected digest",
                    }
                )
                assets.append(entry)
                continue

            if not remote:
                if dest.is_file():
                    entry["present"] = True
                    entry["bytes"] = dest.stat().st_size
                    entry["detail"] = (
                        "local file present but digest/size mismatch and "
                        "object storage is not configured"
                    )
                    errors.append(f"{filename}: digest mismatch without remote backend")
                else:
                    entry["detail"] = "missing locally; object storage not configured"
                    errors.append(f"{filename}: missing")
                assets.append(entry)
                continue

            # Rematerialize from R2 (read-only). Never put_object.
            materialize_object_to_path(object_key, dest, storage=storage)
            materialized += 1
            entry["materialized"] = True
            entry["present"] = dest.is_file()
            entry["bytes"] = dest.stat().st_size if dest.is_file() else None
            if not _asset_local_ok(
                dest, expected_sha256=expected_sha, expected_bytes=expected_bytes
            ):
                actual = sha256_file(dest) if dest.is_file() else None
                entry["detail"] = (
                    "materialized object digest does not match expected "
                    f"local engineering clip (expected={expected_sha[:12]}… "
                    f"actual={(actual or 'missing')[:12]}…)"
                )
                errors.append(f"{filename}: sha256 mismatch after materialize")
                assets.append(entry)
                continue
            meta = _validate_geophysics_geotiff(dest)
            entry.update(
                {
                    "sha256_ok": True,
                    "valid_geotiff": True,
                    "raster": meta,
                    "detail": "materialized from object storage",
                }
            )
        except FileNotFoundError:
            entry["detail"] = f"object not found in storage: {object_key}"
            errors.append(entry["detail"])
        except Exception as exc:  # noqa: BLE001 — readiness must stay informative
            entry["detail"] = f"{type(exc).__name__}: {exc}"
            errors.append(f"{filename}: {entry['detail']}")
        assets.append(entry)

    available = all(
        a.get("present") and a.get("sha256_ok") and a.get("valid_geotiff") for a in assets
    )
    logger.info(
        "geophysics_assets available=%s materialized=%s root=%s errors=%s",
        available,
        materialized,
        root,
        len(errors),
    )
    return {
        "available": available,
        "processed_dir_configured": str(root),
        "materialized_count": materialized,
        "assets": assets,
        "errors": errors,
        "detail": (
            "Required Lagos gravity and magnetic GeoTIFFs are readable."
            if available
            else (
                "Required geophysics GeoTIFFs are missing or invalid after "
                "durable recovery. "
                + ("; ".join(errors) if errors else "unknown failure")
            )
        ),
    }


def verify_remote_geophysics_objects(
    *,
    storage: ObjectStorage | None = None,
) -> dict[str, Any]:
    """Read-only check that required geophysics objects exist in object storage.

    Compares remote SHA-256 to the verified local engineering-clip digests.
    Never uploads or deletes remote objects.
    """
    if not is_remote_object_backend() and storage is None:
        return {
            "ok": False,
            "backend": object_storage_backend(),
            "assets": [],
            "detail": "object storage backend is not remote",
        }
    errors = validate_object_storage_configuration()
    if errors and is_remote_object_backend() and storage is None:
        raise IncompleteObjectStorageConfigError("; ".join(errors))
    store = storage or build_object_storage_from_env()
    assets: list[dict[str, Any]] = []
    all_ok = True
    for spec in REQUIRED_GEOPHYSICS_ASSETS:
        object_key = str(spec["object_key"])
        expected_sha = str(spec["expected_sha256"])
        expected_bytes = int(spec["expected_bytes"])
        entry: dict[str, Any] = {
            "object_key": object_key,
            "exists": False,
            "bytes": None,
            "sha256": None,
            "sha256_ok": False,
        }
        try:
            if not store.exists(object_key):
                all_ok = False
                entry["detail"] = "missing"
                assets.append(entry)
                continue
            payload = store.get_bytes(object_key)
            digest = sha256_bytes(payload)
            entry.update(
                {
                    "exists": True,
                    "bytes": len(payload),
                    "sha256": digest,
                    "sha256_ok": digest == expected_sha and len(payload) == expected_bytes,
                    "detail": "ok" if digest == expected_sha else "digest_mismatch",
                }
            )
            if not entry["sha256_ok"]:
                all_ok = False
        except Exception as exc:  # noqa: BLE001
            all_ok = False
            entry["detail"] = f"{type(exc).__name__}: {exc}"
        assets.append(entry)
    return {
        "ok": all_ok,
        "backend": object_storage_backend(),
        "assets": assets,
        "detail": (
            "Remote geophysics objects match expected digests."
            if all_ok
            else "One or more remote geophysics objects are missing or mismatched."
        ),
    }


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
                overwrite=False,
            )
    acquisition = assess / "acquisition"
    if acquisition.is_dir():
        mirror_assessment_acquisition_evidence(
            acquisition, assessment_id, storage=storage
        )


def mirror_assessment_acquisition_evidence(
    acquisition_dir: Path,
    assessment_id: str,
    *,
    storage: ObjectStorage | None = None,
) -> dict[str, Any] | None:
    """Mirror acquisition evidence files without overwriting existing R2 objects."""
    root = Path(acquisition_dir)
    if not root.is_dir():
        return None
    if not is_remote_object_backend() and storage is None:
        return None
    uploaded = 0
    skipped = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        rel = path.relative_to(root).as_posix()
        key = f"assessments/{assessment_id}/acquisition/{rel}"
        meta = mirror_file_to_object_storage(
            path,
            key,
            content_type=_content_type_for(path),
            storage=storage,
            overwrite=False,
        )
        if meta and meta.get("skipped_existing"):
            skipped += 1
        elif meta:
            uploaded += 1
    return {
        "assessment_id": assessment_id,
        "uploaded": uploaded,
        "skipped_existing": skipped,
        "backend": object_storage_backend(),
    }


def ensure_assessment_acquisition_evidence_local(
    acquisition_dir: Path,
    assessment_id: str,
    *,
    storage: ObjectStorage | None = None,
) -> int:
    """Materialize acquisition evidence prefix from object storage when missing locally."""
    return materialize_prefix_to_directory(
        f"assessments/{assessment_id}/acquisition",
        Path(acquisition_dir),
        storage=storage,
    )
