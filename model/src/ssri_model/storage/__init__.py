# Object storage abstraction (local + S3-compatible)

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import quote


class ObjectStorage(Protocol):
    def put_bytes(self, key: str, payload: bytes, *, content_type: str) -> str: ...

    def signed_url(self, key: str, *, expires_seconds: int = 3600) -> str: ...

    def delete(self, key: str) -> None: ...


def _safe_key(key: str) -> str:
    safe = key.replace("\\", "/").lstrip("/")
    if ".." in safe.split("/"):
        raise ValueError("unsafe object key")
    if not safe:
        raise ValueError("object key must be non-empty")
    return safe


@dataclass
class LocalObjectStorage:
    """Filesystem-backed storage for local/dev; not a public CDN."""

    root: Path
    public_base_url: str = "file://"

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, key: str, payload: bytes, *, content_type: str) -> str:
        _ = content_type
        safe = _safe_key(key)
        path = self.root / safe
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return safe

    def signed_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        _ = expires_seconds
        safe = _safe_key(key)
        base = self.public_base_url
        if base.startswith("file:"):
            # Keep file:/// style roots; Path-like local refs for operators.
            root = str(self.root.resolve()).replace("\\", "/")
            return f"file:///{root}/{safe}".replace("\\", "/")
        return f"{base.rstrip('/')}/{quote(safe)}"

    def delete(self, key: str) -> None:
        path = self.root / _safe_key(key)
        if path.exists():
            path.unlink()


@dataclass
class S3CompatibleObjectStorage:
    """S3-compatible object storage using boto3 (AWS, MinIO, R2, etc.)."""

    bucket: str
    endpoint_url: str | None = None
    region_name: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None
    public_base_url: str | None = None

    def __post_init__(self) -> None:
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "boto3 is required for S3-compatible storage. "
                "Install with: poetry add boto3"
            ) from exc
        session_kwargs: dict[str, str] = {}
        if self.access_key_id and self.secret_access_key:
            session_kwargs["aws_access_key_id"] = self.access_key_id
            session_kwargs["aws_secret_access_key"] = self.secret_access_key
        if self.region_name:
            session_kwargs["region_name"] = self.region_name
        session = boto3.session.Session(**session_kwargs)
        client_kwargs: dict[str, object] = {}
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url
        self._client = session.client("s3", **client_kwargs)

    def put_bytes(self, key: str, payload: bytes, *, content_type: str) -> str:
        safe = _safe_key(key)
        self._client.put_object(
            Bucket=self.bucket,
            Key=safe,
            Body=payload,
            ContentType=content_type,
        )
        return safe

    def signed_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        safe = _safe_key(key)
        if expires_seconds <= 0:
            raise ValueError("expires_seconds must be positive")
        return str(
            self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": safe},
                ExpiresIn=int(expires_seconds),
            )
        )

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=_safe_key(key))


def build_object_storage_from_env() -> ObjectStorage:
    backend = os.getenv("SSRI_OBJECT_STORAGE_BACKEND", "local").lower()
    if backend == "local":
        default_root = os.getenv("SSRI_API_OUTPUT_ROOT", "outputs")
        root = Path(
            os.getenv("SSRI_OBJECT_STORAGE_ROOT", str(Path(default_root) / "objects"))
        )
        return LocalObjectStorage(root=root)
    if backend in {"s3", "minio", "r2"}:
        bucket = os.getenv("SSRI_OBJECT_STORAGE_BUCKET")
        if not bucket:
            raise ValueError("SSRI_OBJECT_STORAGE_BUCKET is required for S3 backend")
        return S3CompatibleObjectStorage(
            bucket=bucket,
            endpoint_url=os.getenv("SSRI_OBJECT_STORAGE_ENDPOINT"),
            region_name=os.getenv("SSRI_OBJECT_STORAGE_REGION"),
            access_key_id=os.getenv("SSRI_OBJECT_STORAGE_ACCESS_KEY"),
            secret_access_key=os.getenv("SSRI_OBJECT_STORAGE_SECRET_KEY"),
            public_base_url=os.getenv("SSRI_OBJECT_STORAGE_PUBLIC_BASE_URL"),
        )
    raise ValueError(
        f"Unsupported SSRI_OBJECT_STORAGE_BACKEND={backend!r}. "
        "Use 'local', 's3', 'minio', or 'r2'."
    )
